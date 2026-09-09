"""Geocodificação: é o que destrava «como está o tempo em Lisboa?».

Open-Meteo Geocoding, sem chave. A resposta é pobre de propósito — nome,
país, coordenada, fuso e população — e é tudo que a Letícia precisa para
responder por qualquer cidade do planeta.

O resultado É CACHEADO no `Store` do HA: nome de cidade não muda de
coordenada, e cada consulta economizada é uma consulta a menos na conta de
cortesia do provedor.
"""

from __future__ import annotations

import unicodedata
from urllib.parse import urlencode

BASE = "https://geocoding-api.open-meteo.com/v1/search"


def url(nome: str, *, idioma: str = "pt", quantidade: int = 5) -> str:
    return f"{BASE}?" + urlencode(
        {
            "name": nome,
            "count": max(1, min(int(quantidade), 10)),
            "language": idioma,
            "format": "json",
        }
    )


def chave(nome: str) -> str:
    """Chave de cache tolerante: «são paulo», «Sao Paulo» e «SÃO  PAULO» são a
    mesma pergunta, e a Letícia recebe as três."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", nome) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sem_acento.lower().split())


def interpretar(dados: dict) -> list[dict]:
    saida = []
    for item in dados.get("results") or []:
        saida.append(
            {
                "nome": item.get("name"),
                "regiao": item.get("admin1"),
                "pais": item.get("country"),
                "pais_codigo": item.get("country_code"),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "altitude": item.get("elevation"),
                "fuso": item.get("timezone"),
                "populacao": item.get("population"),
            }
        )
    return saida


def melhor(resultados: list[dict]) -> dict | None:
    """A cidade mais populosa entre as homônimas. «Não achei» é resposta; achar
    a errada em silêncio, não."""
    if not resultados:
        return None
    return max(resultados, key=lambda r: r.get("populacao") or 0)


def rotulo(lugar: dict) -> str:
    partes = [lugar.get("nome")]
    if lugar.get("regiao") and lugar["regiao"] != lugar.get("nome"):
        partes.append(lugar["regiao"])
    if lugar.get("pais"):
        partes.append(lugar["pais"])
    return ", ".join(p for p in partes if p)
