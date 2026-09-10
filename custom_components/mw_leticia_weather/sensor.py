"""Sensores: o número, a discórdia, o ar — e a fala pronta para a Letícia."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfDensity,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CALIBRAR, DOMAIN, MODELOS_ROTULO, SECAO_CALIBRACAO
from .entidade import EntidadeClima
from .montagem import Retrato


@dataclass(frozen=True, kw_only=True)
class DescricaoClima(SensorEntityDescription):
    valor: Callable[[Retrato], float | str | None]
    atributos: Callable[[Retrato], dict] | None = None


def _hoje(r: Retrato):
    if not r.dias:
        return None
    alvo = r.atualizado_em.date() if r.atualizado_em else None
    return next((d for d in r.dias if alvo and d.data == alvo), r.dias[0])


SENSORES: tuple[DescricaoClima, ...] = (
    DescricaoClima(
        key="temperatura",
        translation_key="temperatura",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        valor=lambda r: r.agora.temperatura,
        atributos=lambda r: {
            "p10": r.agora.temperatura_p10,
            "p90": r.agora.temperatura_p90,
            "por_modelo": {m: round(v, 1) for m, v in r.agora.por_modelo.items()},
            "descartados": r.agora.descartados,
        },
    ),
    DescricaoClima(
        key="sensacao",
        translation_key="sensacao",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        valor=lambda r: r.agora.sensacao,
    ),
    DescricaoClima(
        key="confianca",
        translation_key="confianca",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:arrow-expand-vertical",
        valor=lambda r: r.agora.spread,
        atributos=lambda r: {
            # Frase que cabe DENTRO da fala da Letícia ("...e agora eles estão
            # {leitura}"), não um rótulo solto: rótulo bom de tela vira frase
            # torta na voz.
            "leitura": (
                "de acordo"
                if (r.agora.spread or 0) < 1
                else "discordando um pouco"
                if (r.agora.spread or 0) < 2.5
                else "discordando bastante"
            ),
            "modelos": len(r.agora.por_modelo),
        },
    ),
    DescricaoClima(
        key="umidade",
        translation_key="umidade",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        valor=lambda r: r.agora.umidade,
    ),
    DescricaoClima(
        key="pressao",
        translation_key="pressao",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        valor=lambda r: r.agora.pressao_msl,
        # A tendência de 3 h sai como atributo porque é ela, e não o valor
        # absoluto, que o barômetro usa para prever (regra 190).
        atributos=lambda r: {
            "pressao_3h_atras": r.pressao_3h_atras,
            "variacao_3h": (
                round(r.agora.pressao_msl - r.pressao_3h_atras, 2)
                if r.agora.pressao_msl is not None and r.pressao_3h_atras is not None
                else None
            ),
            "referencia": "nível do mar",
            "pressao_estacao": r.agora.pressao_estacao,
        },
    ),
    DescricaoClima(
        key="vento",
        translation_key="vento",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        valor=lambda r: r.agora.vento,
        atributos=lambda r: {
            "rajada": r.agora.rajada,
            "direcao": r.agora.direcao_vento,
        },
    ),
    DescricaoClima(
        key="direcao_vento",
        translation_key="direcao_vento",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        suggested_display_precision=0,
        valor=lambda r: r.agora.direcao_vento,
    ),
    DescricaoClima(
        key="uv",
        translation_key="uv",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-sunny-alert",
        suggested_display_precision=1,
        valor=lambda r: (r.ar or {}).get("uv_index"),
    ),
    DescricaoClima(
        key="pm25",
        translation_key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        valor=lambda r: (r.ar or {}).get("pm2_5"),
        atributos=lambda r: {"faixa": (r.ar or {}).get("pm2_5_faixa")},
    ),
    DescricaoClima(
        key="aqi",
        translation_key="aqi",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        valor=lambda r: (r.ar or {}).get("european_aqi"),
        atributos=lambda r: {"us_aqi": (r.ar or {}).get("us_aqi")},
    ),
    DescricaoClima(
        key="chuva_probabilidade",
        translation_key="chuva_probabilidade",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-rainy",
        suggested_display_precision=0,
        valor=lambda r: r.agora.chuva_probabilidade,
    ),
    DescricaoClima(
        key="alertas",
        translation_key="alertas",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:alert-outline",
        valor=lambda r: len(r.alertas),
        atributos=lambda r: {
            "lista": [a.como_dicionario() for a in r.alertas],
            "mais_grave": r.alertas[0].severidade if r.alertas else None,
            "oficiais": sum(1 for a in r.alertas if a.oficial),
            "fala_alertas": r.falas.get("fala_alertas"),
        },
    ),
    # O sensor que a Letícia consulta. O estado é curto (a frase de agora, que
    # cabe nos 255 caracteres do estado); as demais frases vão nos ATRIBUTOS,
    # que não têm esse limite — e é de lá que o `intent_script` lê, contornando
    # a armadilha do `speech` que não enxerga `response_variable`.
    DescricaoClima(
        key="previsao",
        translation_key="previsao",
        icon="mdi:message-text-outline",
        valor=lambda r: (r.falas.get("fala_agora") or "")[:255],
        atributos=lambda r: {
            **r.falas,
            "lugar": r.lugar,
            "dias": [
                {
                    "data": d.data.isoformat(),
                    "minima": d.minima,
                    "maxima": d.maxima,
                    "codigo": d.codigo,
                    "chuva_probabilidade": d.chuva_probabilidade,
                    "uv_max": d.uv_max,
                    "umidade_min": d.umidade_min,
                }
                for d in r.dias[:8]
            ],
        },
    ),
)

# Diagnóstico: o desvio de cada modelo contra o consenso. É a PROVA da fusão —
# sem isto, "confiável" é adjetivo. Categoria diagnóstico para não poluir a
# tela de quem só quer saber se leva guarda-chuva.
DIAGNOSTICOS = tuple(
    DescricaoClima(
        key=f"desvio_{modelo}",
        name=f"Desvio {rotulo}",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        icon="mdi:delta",
        valor=(
            lambda r, m=modelo: (
                round(r.agora.por_modelo[m] - r.agora.temperatura, 2)
                if m in r.agora.por_modelo and r.agora.temperatura is not None
                else None
            )
        ),
        atributos=(
            lambda r, m=modelo: {
                "valor_do_modelo": r.agora.por_modelo.get(m),
                "peso": round(r.pesos.get(m, 1.0), 3),
                "descartado_neste_ciclo": m in r.agora.descartados,
            }
        ),
    )
    for modelo, rotulo in MODELOS_ROTULO.items()
)


CALIBRADA = DescricaoClima(
    key="temperatura_calibrada",
    translation_key="temperatura_calibrada",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
    icon="mdi:target",
    valor=lambda r: (r.calibracao or {}).get("temperatura"),
    atributos=lambda r: dict(r.calibracao or {}),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordenador = hass.data[DOMAIN][entry.entry_id]
    descricoes = [*SENSORES, *DIAGNOSTICOS]
    # A temperatura calibrada só EXISTE quando o dono liga a calibração. Criar
    # uma entidade que nunca terá valor é fabricar presença de dado (regra 120).
    fonte = {**entry.data, **entry.options}
    if (fonte.get(SECAO_CALIBRACAO) or {}).get(CONF_CALIBRAR):
        descricoes.append(CALIBRADA)
    async_add_entities(SensorClima(coordenador, d) for d in descricoes)


class SensorClima(EntidadeClima, SensorEntity):
    entity_description: DescricaoClima

    def __init__(self, coordenador, descricao: DescricaoClima) -> None:
        super().__init__(coordenador)
        self.entity_description = descricao
        self._attr_unique_id = f"{coordenador.entry.entry_id}_{descricao.key}"

    @property
    def native_value(self):
        if not self.retrato:
            return None
        return self.entity_description.valor(self.retrato)

    @property
    def extra_state_attributes(self) -> dict | None:
        if not self.retrato or not self.entity_description.atributos:
            return None
        return {
            chave: valor
            for chave, valor in self.entity_description.atributos(self.retrato).items()
            if valor is not None
        }
