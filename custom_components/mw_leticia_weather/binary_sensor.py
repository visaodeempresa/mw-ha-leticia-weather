"""Um binário por tipo de alerta: é o que automação e planta baixa consomem.

Sensor de contagem serve para a tela; para «se ficar seco, ligue o umidificador»
o que serve é um `binary_sensor` com `device_class` de segurança, que já entra
vermelho na interface sem `card_mod` nenhum.
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entidade import EntidadeClima

TIPOS = (
    ("clima_seco", "mdi:water-percent-alert"),
    ("calor", "mdi:thermometer-alert"),
    ("frio", "mdi:snowflake-alert"),
    ("chuva_forte", "mdi:weather-pouring"),
    ("tempestade", "mdi:weather-lightning"),
    ("vento_forte", "mdi:weather-windy"),
    ("uv", "mdi:sun-wireless"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordenador = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AlertaBinario(
            coordenador,
            BinarySensorEntityDescription(
                key=tipo,
                translation_key=tipo,
                device_class=BinarySensorDeviceClass.SAFETY,
                icon=icone,
            ),
        )
        for tipo, icone in TIPOS
    )


class AlertaBinario(EntidadeClima, BinarySensorEntity):
    def __init__(self, coordenador, descricao: BinarySensorEntityDescription) -> None:
        super().__init__(coordenador)
        self.entity_description = descricao
        self._attr_unique_id = f"{coordenador.entry.entry_id}_alerta_{descricao.key}"

    def _meus(self):
        if not self.retrato:
            return []
        return [
            a for a in self.retrato.alertas if a.tipo == self.entity_description.key
        ]

    @property
    def is_on(self) -> bool | None:
        if not self.retrato:
            return None
        return bool(self._meus())

    @property
    def extra_state_attributes(self) -> dict | None:
        meus = self._meus()
        if not meus:
            return None
        primeiro = meus[0]
        return {
            "severidade": primeiro.severidade,
            "severidade_rotulo": primeiro.rotulo_severidade,
            "cor": primeiro.cor,
            "titulo": primeiro.titulo,
            "descricao": primeiro.descricao,
            "instrucoes": primeiro.instrucoes,
            "fonte": primeiro.fonte,
            "oficial": primeiro.oficial,
            "inicio": primeiro.inicio.isoformat() if primeiro.inicio else None,
            "fim": primeiro.fim.isoformat() if primeiro.fim else None,
        }
