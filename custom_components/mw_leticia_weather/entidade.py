"""Base das entidades: um dispositivo por local, e nada de `should_poll`."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATRIBUICAO, DOMAIN, FABRICANTE, NOME
from .coordinator import CoordenadorClima


class EntidadeClima(CoordinatorEntity[CoordenadorClima]):
    """Todas as entidades de um local penduram no MESMO dispositivo.

    Um dispositivo por LOCAL (e não um por grandeza): a tela de dispositivos
    fica com «Tempo — Águas Claras» e as entidades dentro, em vez de vinte
    caixas soltas. Quem tem dois locais tem dois dispositivos, que é o
    agrupamento que a pessoa realmente pensa.
    """

    _attr_has_entity_name = True
    _attr_attribution = ATRIBUICAO

    def __init__(self, coordenador: CoordenadorClima) -> None:
        super().__init__(coordenador)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordenador.entry.entry_id)},
            name=f"Tempo — {coordenador.lugar}",
            manufacturer=FABRICANTE,
            model=NOME,
            configuration_url="homeassistant://config/integrations/integration/"
            + DOMAIN,
        )

    @property
    def retrato(self):
        return self.coordinator.data

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None
