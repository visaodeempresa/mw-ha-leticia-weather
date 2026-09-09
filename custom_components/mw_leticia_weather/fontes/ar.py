"""Qualidade do ar e índice UV (Open-Meteo Air Quality — endpoint separado).

Verificado em 2026-09-09: `european_aqi` 47, `us_aqi` 52, `pm2_5` 13,5 µg/m³
para o ponto da casa — coerente com o «IQA Ruim (56)» que o app do Android
mostrava no mesmo minuto (o app usa a escala americana).

Este endpoint **não** aceita `models=`: aqui não há conjunto, há uma fonte só,
e isso se declara em vez de fingir consenso.
"""

from __future__ import annotations

from urllib.parse import urlencode

BASE = "https://air-quality-api.open-meteo.com/v1/air-quality"

HORARIAS = (
    "pm2_5",
    "pm10",
    "european_aqi",
    "us_aqi",
    "uv_index",
    "dust",
)


def url(latitude: float, longitude: float, *, dias: int = 3, fuso: str = "auto") -> str:
    return f"{BASE}?" + urlencode(
        {
            "latitude": f"{latitude:.5f}",
            "longitude": f"{longitude:.5f}",
            "hourly": ",".join(HORARIAS),
            "forecast_days": str(max(1, min(int(dias), 7))),
            "timezone": fuso,
            "timeformat": "unixtime",
        }
    )


# A escala de PM2.5 é a da regra global 90 (0 / 12 / 35 µg/m³) — a mesma que a
# seção QUALIDADE DO AR dos dashboards da casa já usa. Não se inventa outra.
PM25_FAIXAS = ((12.0, "bom"), (35.0, "atenção"), (float("inf"), "ruim"))


def faixa_pm25(valor: float | None) -> str | None:
    if valor is None:
        return None
    for limite, rotulo in PM25_FAIXAS:
        if float(valor) <= limite:
            return rotulo
    return "ruim"


def interpretar(dados: dict, indice: int) -> dict:
    bloco = dados.get("hourly") or {}
    saida: dict[str, float | None] = {}
    for variavel in HORARIAS:
        coluna = bloco.get(variavel)
        saida[variavel] = coluna[indice] if coluna and indice < len(coluna) else None
    saida["pm2_5_faixa"] = faixa_pm25(saida.get("pm2_5"))  # type: ignore[assignment]
    return saida


def eixo_tempo(dados: dict) -> list[float]:
    return [float(t) for t in (dados.get("hourly") or {}).get("time", [])]


def maximo_do_dia(dados: dict, variavel: str, inicio: int, fim: int) -> float | None:
    """Máximo de UV no dia — a entrada do alerta derivado de radiação."""
    coluna = (dados.get("hourly") or {}).get(variavel) or []
    janela = [v for v in coluna[inicio:fim] if v is not None]
    return max(janela) if janela else None
