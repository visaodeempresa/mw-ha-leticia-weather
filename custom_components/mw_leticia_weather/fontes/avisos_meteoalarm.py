"""Avisos oficiais do MeteoAlarm (Europa), pelo feed CAP/Atom por país.

O MeteoAlarm publica por REGIÃO administrativa, não por ponto: a integração
casa pelo código de região EMMA quando ele estiver configurado, e senão avisa
que não deu para decidir — em vez de devolver silêncio, que se confunde com
«não há aviso».
"""

from __future__ import annotations

from datetime import datetime

BASE = "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-{pais}"

NIVEL = {"1": "potencial", "2": "potencial", "3": "perigo", "4": "grande_perigo"}
CAP_PARA_SEVERIDADE = {
    "minor": "potencial",
    "moderate": "perigo",
    "severe": "grande_perigo",
    "extreme": "grande_perigo",
}

TIPO = {
    "wind": "vento_forte",
    "rain": "chuva_forte",
    "flood": "chuva_forte",
    "thunderstorm": "tempestade",
    "high-temperature": "calor",
    "low-temperature": "frio",
    "forest-fire": "clima_seco",
}


def url(pais: str) -> str:
    return BASE.format(pais=(pais or "").strip().lower())


def _quando(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


def interpretar(itens: list[dict], regiao: str | None = None) -> list[dict]:
    """`itens` já é a lista de avisos CAP normalizada pelo coordinator (o feed
    é Atom; quem faz o parse do XML é quem tem a sessão HTTP)."""
    saida: list[dict] = []
    for item in itens:
        if regiao and item.get("regiao") and regiao not in str(item["regiao"]):
            continue
        tipo_bruto = str(item.get("awareness_type") or item.get("event") or "")
        saida.append(
            {
                "tipo": next(
                    (v for k, v in TIPO.items() if k in tipo_bruto.lower()), "outro"
                ),
                "severidade": NIVEL.get(
                    str(item.get("awareness_level") or "")[:1],
                    CAP_PARA_SEVERIDADE.get(
                        str(item.get("severity", "")).lower(), "potencial"
                    ),
                ),
                "titulo": item.get("titulo") or tipo_bruto or "Aviso meteorológico",
                "descricao": (item.get("descricao") or "").strip(),
                "fonte": "MeteoAlarm (Europa)",
                "oficial": True,
                "inicio": _quando(item.get("inicio")),
                "fim": _quando(item.get("fim")),
                "instrucoes": (item.get("instrucoes") or "").strip() or None,
                "id": item.get("id"),
            }
        )
    return saida
