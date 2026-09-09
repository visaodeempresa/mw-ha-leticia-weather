"""Códigos WMO → condição do Home Assistant, texto em pt-BR e desenho do céu.

Módulo puro de propósito: NÃO importa `homeassistant`. Assim os testes e os
scripts de `tools/` usam a mesma fonte da verdade sem HA instalado — o mesmo
truque de `catalogo.py`/`ingestao.py` no MW Letícia Health.

As condições do HA são o vocabulário fechado de `weather.condition`; inventar
uma faz o card nativo desenhar nada e não dá erro.
"""

from __future__ import annotations

# código WMO: (condição HA de dia, texto pt-BR, desenho do céu)
# O desenho do céu é o que o card e o fundo do cabeçalho usam: limpo, nuvem,
# chuva, neve, tempestade, nevoeiro.
_WMO: dict[int, tuple[str, str, str]] = {
    0: ("sunny", "céu limpo", "limpo"),
    1: ("sunny", "céu quase limpo", "limpo"),
    2: ("partlycloudy", "parcialmente nublado", "nuvem"),
    3: ("cloudy", "nublado", "nuvem"),
    45: ("fog", "nevoeiro", "nevoeiro"),
    48: ("fog", "nevoeiro com geada", "nevoeiro"),
    51: ("rainy", "garoa fraca", "chuva"),
    53: ("rainy", "garoa", "chuva"),
    55: ("rainy", "garoa forte", "chuva"),
    56: ("snowy-rainy", "garoa congelante", "chuva"),
    57: ("snowy-rainy", "garoa congelante forte", "chuva"),
    61: ("rainy", "chuva fraca", "chuva"),
    63: ("rainy", "chuva", "chuva"),
    65: ("pouring", "chuva forte", "chuva"),
    66: ("snowy-rainy", "chuva congelante", "chuva"),
    67: ("snowy-rainy", "chuva congelante forte", "chuva"),
    71: ("snowy", "neve fraca", "neve"),
    73: ("snowy", "neve", "neve"),
    75: ("snowy", "neve forte", "neve"),
    77: ("snowy", "grãos de neve", "neve"),
    80: ("rainy", "pancadas fracas", "chuva"),
    81: ("rainy", "pancadas de chuva", "chuva"),
    82: ("pouring", "pancadas fortes", "chuva"),
    85: ("snowy", "pancadas de neve", "neve"),
    86: ("snowy", "pancadas de neve fortes", "neve"),
    95: ("lightning-rainy", "tempestade", "tempestade"),
    96: ("hail", "tempestade com granizo", "tempestade"),
    99: ("hail", "tempestade com granizo forte", "tempestade"),
}

_DESCONHECIDO = ("exceptional", "condição não catalogada", "nuvem")


def _entrada(codigo: int | float | None) -> tuple[str, str, str]:
    try:
        return _WMO[int(codigo)]  # type: ignore[arg-type]
    except (TypeError, ValueError, KeyError):
        return _DESCONHECIDO


def condicao(codigo: int | float | None, *, dia: bool = True) -> str:
    """Condição do HA. À noite, `sunny` vira `clear-night` — é o único par que
    o frontend trata de forma diferente, e errar isso deixa um sol desenhado
    à meia-noite."""
    cond = _entrada(codigo)[0]
    if not dia and cond == "sunny":
        return "clear-night"
    return cond


def texto(codigo: int | float | None) -> str:
    """Texto em pt-BR, minúsculo, pronto para entrar no meio de uma frase que
    a Letícia vai falar."""
    return _entrada(codigo)[1]


def ceu(codigo: int | float | None) -> str:
    """O desenho que o card e o fundo do cabeçalho devem pintar."""
    return _entrada(codigo)[2]


def codigos_conhecidos() -> list[int]:
    return sorted(_WMO)
