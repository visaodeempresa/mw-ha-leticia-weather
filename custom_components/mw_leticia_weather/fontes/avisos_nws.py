"""Avisos oficiais do National Weather Service (Estados Unidos).

CAP em JSON, sem chave, mas com `User-Agent` obrigatório e identificável — a
NOAA bloqueia agente genérico. Consulta por ponto: `?point=lat,lon`.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

BASE = "https://api.weather.gov/alerts/active"

CAP_PARA_SEVERIDADE = {
    "minor": "potencial",
    "moderate": "perigo",
    "severe": "grande_perigo",
    "extreme": "grande_perigo",
    "unknown": "potencial",
}

# Evento CAP → tipo canônico, para o oficial poder desbancar o derivado.
TIPO = {
    "heat": "calor",
    "cold": "frio",
    "freeze": "frio",
    "frost": "frio",
    "wind": "vento_forte",
    "thunderstorm": "tempestade",
    "tornado": "tempestade",
    "flood": "chuva_forte",
    "rain": "chuva_forte",
    "fire weather": "clima_seco",
    "red flag": "clima_seco",
}


def url(latitude: float, longitude: float) -> str:
    return f"{BASE}?" + urlencode(
        {"point": f"{latitude:.4f},{longitude:.4f}", "status": "actual"}
    )


def _tipo(evento: str) -> str:
    e = (evento or "").lower()
    for chave, valor in TIPO.items():
        if chave in e:
            return valor
    return "outro"


def _quando(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor))
    except ValueError:
        return None


def interpretar(dados: dict) -> list[dict]:
    saida: list[dict] = []
    for item in dados.get("features") or []:
        p = item.get("properties") or {}
        evento = p.get("event") or "Weather alert"
        saida.append(
            {
                "tipo": _tipo(evento),
                "severidade": CAP_PARA_SEVERIDADE.get(
                    str(p.get("severity", "")).lower(), "potencial"
                ),
                "titulo": evento,
                "descricao": (
                    p.get("headline") or p.get("description") or evento
                ).strip(),
                "fonte": "NWS (EUA)",
                "oficial": True,
                "inicio": _quando(p.get("onset") or p.get("effective")),
                "fim": _quando(p.get("ends") or p.get("expires")),
                "instrucoes": (p.get("instruction") or "").strip() or None,
                "id": p.get("id"),
            }
        )
    return saida
