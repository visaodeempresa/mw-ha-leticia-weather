"""Diagnóstico — com coordenada REDIGIDA.

O arquivo de diagnóstico é o que a pessoa anexa num issue público. A coordenada
da casa é o dado mais sensível desta integração inteira; sai daqui.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

REDIGIR = {"latitude", "longitude", "latitude_grade", "longitude_grade", "ibge", "nome"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordenador = hass.data[DOMAIN][entry.entry_id]
    retrato = coordenador.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), REDIGIR),
            "options": async_redact_data(dict(entry.options), REDIGIR),
        },
        "coordenador": {
            "modelos": coordenador.modelos,
            "pesos": coordenador.pesos,
            "intervalo_s": coordenador.update_interval.total_seconds()
            if coordenador.update_interval
            else None,
            "ultimo_sucesso": coordenador.last_update_success,
        },
        "retrato": None
        if not retrato
        else {
            "temperatura": retrato.agora.temperatura,
            "spread": retrato.agora.spread,
            "por_modelo": retrato.agora.por_modelo,
            "descartados": retrato.agora.descartados,
            "codigo": retrato.agora.codigo,
            "dias": len(retrato.dias),
            "horas": len(retrato.horas),
            "alertas": [a.como_dicionario() for a in retrato.alertas],
            "ar": retrato.ar,
            "meta": async_redact_data(dict(retrato.meta), REDIGIR),
        },
    }
