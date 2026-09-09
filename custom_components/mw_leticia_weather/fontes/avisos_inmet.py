"""Avisos oficiais do INMET (Brasil), por polígono.

Endpoint verificado em 2026-09-09: `https://apiprevmet3.inmet.gov.br/avisos/ativos`
devolve `{"hoje": [...], "futuro": [...]}` com `severidade` («Perigo Potencial»,
«Perigo», «Grande Perigo»), `descricao` («Baixa Umidade», «Chuvas Intensas»),
`riscos`, `instrucoes`, janela de validade e um `poligono` GeoJSON em STRING —
que é a pegadinha: vem como texto JSON dentro do JSON.

O aviso é regional, então a pergunta certa não é «tem aviso no Brasil?» e sim
«este ponto está dentro do polígono?». Ponto-em-polígono por lançamento de raio,
em Python puro: trazer `shapely` para dentro de uma integração de HA por causa
de trinta linhas seria imposto de dependência.
"""

from __future__ import annotations

import json
from datetime import datetime

URL = "https://apiprevmet3.inmet.gov.br/avisos/ativos"

# O INMET fala em português; a integração fala em três degraus (alertas.py).
SEVERIDADE = {
    "perigo potencial": "potencial",
    "perigo": "perigo",
    "grande perigo": "grande_perigo",
}

# `descricao` → o tipo canônico, para o alerta oficial poder desbancar o
# derivado do mesmo assunto (alertas.deduplicar).
TIPO = {
    "baixa umidade": "clima_seco",
    "chuvas intensas": "chuva_forte",
    "acumulado de chuva": "chuva_forte",
    "tempestade": "tempestade",
    "vendaval": "vento_forte",
    "ventos costeiros": "vento_forte",
    "onda de calor": "calor",
    "temperatura elevada": "calor",
    "declínio de temperatura": "frio",
    "onda de frio": "frio",
    "geada": "frio",
}


def _texto(bruto) -> str:
    """`riscos` e `instrucoes` vêm ora como string, ora como LISTA de strings
    (medido em 2026-09-09, no mesmo endpoint, em avisos do mesmo dia). Quem
    assumir string leva `AttributeError: 'list' object has no attribute
    'strip'` só no dia em que houver aviso — ou seja, no pior dia."""
    if bruto is None:
        return ""
    if isinstance(bruto, (list, tuple)):
        return " ".join(_texto(x) for x in bruto).strip()
    return str(bruto).strip()


def _tipo(descricao: str) -> str:
    d = (descricao or "").strip().lower()
    for chave, valor in TIPO.items():
        if chave in d:
            return valor
    return "outro"


def _severidade(bruta: str) -> str:
    return SEVERIDADE.get((bruta or "").strip().lower(), "potencial")


def ponto_no_poligono(lat: float, lon: float, anel: list[list[float]]) -> bool:
    """Lançamento de raio. O anel do INMET vem como [[lon, lat], ...] (ordem
    GeoJSON: X antes de Y — trocar isso é o erro clássico e silencioso)."""
    dentro = False
    n = len(anel)
    for i in range(n):
        x1, y1 = anel[i][0], anel[i][1]
        x2, y2 = anel[(i + 1) % n][0], anel[(i + 1) % n][1]
        if (y1 > lat) != (y2 > lat):
            corte = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lon < corte:
                dentro = not dentro
    return dentro


def _aneis(poligono) -> list[list[list[float]]]:
    """Aceita o polígono como string JSON (é como o INMET manda) ou já
    decodificado, e cobre Polygon e MultiPolygon."""
    if not poligono:
        return []
    if isinstance(poligono, str):
        try:
            poligono = json.loads(poligono)
        except (ValueError, TypeError):
            return []
    tipo = poligono.get("type")
    coords = poligono.get("coordinates") or []
    if tipo == "Polygon":
        return [anel for anel in coords if anel]
    if tipo == "MultiPolygon":
        return [anel for parte in coords for anel in parte if anel]
    return []


def _quando(data: str | None, hora: str | None) -> datetime | None:
    """Duas armadilhas numa linha só, ambas medidas em 2026-09-09.

    1. A hora vem SEPARADA, em `hora_inicio`/`hora_fim`; `data_inicio` traz
       `00:00`. Quem usar só a data marca todo aviso como válido à meia-noite.
    2. `data_inicio` termina em **Z**, mas o horário é **local de Brasília** —
       o mesmo aviso que a API diz terminar «23:59Z» aparece no celular do dono
       como «em vigor até 11:59PM BRT». Tratar como UTC empurra o aviso 3 horas
       para frente. Por isso devolvemos datetime INGÊNUO (sem fuso) e quem
       localiza é o HA, com o fuso da casa.
    """
    if not data:
        return None
    try:
        base = datetime.fromisoformat(str(data).replace("Z", "+00:00"))
    except ValueError:
        return None
    base = base.replace(tzinfo=None)
    if hora:
        try:
            h, m = str(hora).split(":")[:2]
            base = base.replace(hour=int(h), minute=int(m))
        except (ValueError, TypeError):
            pass
    return base


def _no_municipio(aviso: dict, ibge: str | None) -> bool | None:
    """Pertencimento pela LISTA DE MUNICÍPIOS, que é o que o INMET considera
    oficial — o polígono é o desenho, a lista é a lei.

    Formato medido em 2026-09-09: `municipios` é uma STRING única,
    «Abadia dos Dourados - MG (3100104),Abaeté - MG (3100203),…», e há também
    `geocodes`. Devolve None quando não dá para decidir (sem código IBGE
    configurado ou sem lista no aviso), e aí o polígono decide.
    """
    if not ibge:
        return None
    codigo = str(ibge).strip()
    geocodes = aviso.get("geocodes")
    if geocodes:
        texto = (
            geocodes
            if isinstance(geocodes, str)
            else ",".join(str(g) for g in geocodes)
        )
        if codigo in texto:
            return True
    municipios = aviso.get("municipios")
    if isinstance(municipios, str) and municipios:
        return f"({codigo})" in municipios
    return None


def interpretar(
    dados: dict,
    latitude: float,
    longitude: float,
    *,
    ibge: str | None = None,
) -> list[dict]:
    """Só os avisos que alcançam este ponto. Devolve dicionários no formato
    que `alertas.Alerta` consome.

    Ordem de decisão: código IBGE (a lista oficial) e, se ele não estiver
    configurado, o polígono. Conferido em 2026-09-09: o aviso de Tempestade
    daquele dia cobria meio Brasil no desenho e **não** incluía Brasília na
    lista — as duas leituras concordaram, e é assim que se descobre que o
    algoritmo está certo.
    """
    saida: list[dict] = []
    for grupo in ("hoje", "futuro"):
        for aviso in dados.get(grupo) or []:
            por_municipio = _no_municipio(aviso, ibge)
            if por_municipio is False:
                continue
            if por_municipio is None:
                aneis = _aneis(aviso.get("poligono"))
                if not any(
                    ponto_no_poligono(latitude, longitude, anel) for anel in aneis
                ):
                    continue
            descricao = aviso.get("descricao") or "Aviso meteorológico"
            saida.append(
                {
                    "tipo": _tipo(descricao),
                    "severidade": _severidade(aviso.get("severidade")),
                    "titulo": descricao,
                    "descricao": _texto(aviso.get("riscos")) or descricao,
                    "fonte": "INMET",
                    "oficial": True,
                    "inicio": _quando(
                        aviso.get("data_inicio"), aviso.get("hora_inicio")
                    ),
                    "fim": _quando(aviso.get("data_fim"), aviso.get("hora_fim")),
                    "instrucoes": _texto(aviso.get("instrucoes")) or None,
                    "id": aviso.get("id_aviso"),
                }
            )
    return saida
