"""MW Letícia Weather — temperatura e previsão confiáveis, por fusão de modelos.

═════════════════════════════════════════════════════════════════════════════
POR QUE ESTA INTEGRAÇÃO EXISTE
═════════════════════════════════════════════════════════════════════════════
Em 2026-09-09, 00:45, cinco fontes olhando o MESMO ponto (Águas Claras,
Brasília, 1200 m) divergiram em 4 °C: iPhone 20, Android 22, weather.com 19,
met.no 19, Open-Meteo 18,7. Nenhuma com defeito — são modelos diferentes,
resolvidos em pontos de grade diferentes.

Trocar de provedor não resolve isso: escolhe outro número, com a mesma
autoridade e a mesma solidão. O que resolve é **fundir vários modelos e
publicar a discórdia**. Aqui o número principal é uma mediana ponderada com
peso aprendido, e junto dele sai o `spread` — a largura do desacordo. Um número
sozinho mente por omissão.

═════════════════════════════════════════════════════════════════════════════
O QUE ESTA INTEGRAÇÃO **NÃO** FAZ
═════════════════════════════════════════════════════════════════════════════
Não substitui órgão oficial. Os alertas derivados são cálculo nosso a partir da
previsão e são rotulados como derivados na tela e na fala, sempre. Alerta com
autoridade é o do INMET, NWS ou MeteoAlarm — e onde eles não alcançam, o
silêncio deles não vira "não há risco".

Não corrige a temperatura pelo sensor da casa por padrão. A calibração local
existe, é opcional e nasce DESLIGADA (decisão do dono, 2026-09-09): quando
ligada, publica entidade separada e nunca sobrescreve o número fundido em
silêncio.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import servicos
from .const import DOMAIN, PLATAFORMAS
from .coordinator import CoordenadorClima

type MWWeatherEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordenador = CoordenadorClima(hass, entry)
    await coordenador.async_carregar_pesos()
    await coordenador.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordenador
    await servicos.registrar(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATAFORMAS)
    entry.async_on_unload(entry.add_update_listener(_ao_mudar_opcoes))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    descarregou = await hass.config_entries.async_unload_platforms(entry, PLATAFORMAS)
    if descarregou:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        servicos.remover(hass)
    return descarregou


async def _ao_mudar_opcoes(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recarrega ao mudar opção. Modelo, intervalo e local mudam o que o
    coordinator busca — remendar o objeto vivo deixaria metade da integração
    com a configuração velha."""
    await hass.config_entries.async_reload(entry.entry_id)
