"""A entidade `weather.` — e por que ela é a peça mais importante da integração.

Não é só mais uma entidade: é o que faz **o intent nativo do Assist**
(`HassGetWeather`), o card `weather-forecast` do próprio HA e qualquer card de
terceiro funcionarem de graça, sem nenhuma linha a mais. Publicar a fusão aqui
é o que impede a integração de virar uma ilha.

`async_forecast_daily/hourly/twice_daily` é o contrato moderno (o antigo
`forecast` como atributo foi removido); e as unidades são declaradas como
NATIVAS — o HA converte para a preferência do usuário sozinho, e converter na
mão é o caminho mais curto para um card mostrar 66 °C.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entidade import EntidadeClima


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([TempoMW(hass.data[DOMAIN][entry.entry_id])])


class TempoMW(EntidadeClima, WeatherEntity):
    _attr_name = None  # o nome é o do dispositivo
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY
        | WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    def __init__(self, coordenador) -> None:
        super().__init__(coordenador)
        self._attr_unique_id = f"{coordenador.entry.entry_id}_weather"

    # ── agora ────────────────────────────────────────────────────────────────
    @property
    def condition(self) -> str | None:
        return self.retrato.agora.condicao if self.retrato else None

    @property
    def native_temperature(self) -> float | None:
        return self.retrato.agora.temperatura if self.retrato else None

    @property
    def native_apparent_temperature(self) -> float | None:
        return self.retrato.agora.sensacao if self.retrato else None

    @property
    def humidity(self) -> float | None:
        return self.retrato.agora.umidade if self.retrato else None

    @property
    def native_pressure(self) -> float | None:
        # AO NÍVEL DO MAR, sempre (regra global 190). A casa está a 1200 m: a
        # pressão de estação daqui é ~887 hPa, e publicar isso aqui faria todo
        # card de terceiro desenhar um furacão permanente.
        return self.retrato.agora.pressao_msl if self.retrato else None

    @property
    def native_wind_speed(self) -> float | None:
        return self.retrato.agora.vento if self.retrato else None

    @property
    def native_wind_gust_speed(self) -> float | None:
        return self.retrato.agora.rajada if self.retrato else None

    @property
    def wind_bearing(self) -> float | None:
        return self.retrato.agora.direcao_vento if self.retrato else None

    @property
    def cloud_coverage(self) -> float | None:
        return self.retrato.agora.nuvens if self.retrato else None

    @property
    def uv_index(self) -> float | None:
        return (self.retrato.ar or {}).get("uv_index") if self.retrato else None

    @property
    def extra_state_attributes(self) -> dict:
        """O que nenhuma outra integração de clima publica: a discórdia."""
        if not self.retrato:
            return {}
        agora = self.retrato.agora
        return {
            "confianca_spread": (
                round(agora.spread, 2) if agora.spread is not None else None
            ),
            "temperatura_p10": (
                round(agora.temperatura_p10, 1)
                if agora.temperatura_p10 is not None
                else None
            ),
            "temperatura_p90": (
                round(agora.temperatura_p90, 1)
                if agora.temperatura_p90 is not None
                else None
            ),
            "por_modelo": {m: round(v, 1) for m, v in agora.por_modelo.items()},
            "modelos_descartados": agora.descartados,
            "pesos": {m: round(p, 2) for m, p in self.retrato.pesos.items()},
            "pressao_estacao": (
                round(agora.pressao_estacao, 1)
                if agora.pressao_estacao is not None
                else None
            ),
            "ponto_de_grade": self.retrato.meta,
            "alertas": len(self.retrato.alertas),
            **self.retrato.falas,
        }

    # ── previsão ─────────────────────────────────────────────────────────────
    async def async_forecast_daily(self) -> list[Forecast] | None:
        if not self.retrato:
            return None
        hoje = self.retrato.atualizado_em.date() if self.retrato.atualizado_em else None
        saida: list[Forecast] = []
        for d in self.retrato.dias:
            if hoje and d.data < hoje:
                continue  # `past_days=1` traz ontem; previsão não olha para trás
            saida.append(
                Forecast(
                    datetime=datetime.combine(
                        d.data, datetime.min.time(), tzinfo=self._fuso()
                    ).isoformat(),
                    condition=self._condicao_do_dia(d),
                    native_temperature=d.maxima,
                    native_templow=d.minima,
                    native_apparent_temperature=d.sensacao_max,
                    precipitation_probability=(
                        int(d.chuva_probabilidade)
                        if d.chuva_probabilidade is not None
                        else None
                    ),
                    native_precipitation=d.chuva,
                    native_wind_speed=d.vento_max,
                    wind_bearing=d.direcao_vento,
                    uv_index=d.uv_max,
                    humidity=d.umidade_min,
                )
            )
        return saida

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        if not self.retrato:
            return None
        return [
            Forecast(
                datetime=datetime.fromtimestamp(ts, tz=self._fuso()).isoformat(),
                condition=h.condicao,
                native_temperature=h.temperatura,
                native_apparent_temperature=h.sensacao,
                humidity=h.umidade,
                native_precipitation=h.precipitacao,
                precipitation_probability=(
                    int(h.chuva_probabilidade)
                    if h.chuva_probabilidade is not None
                    else None
                ),
                native_pressure=h.pressao_msl,
                native_wind_speed=h.vento,
                native_wind_gust_speed=h.rajada,
                wind_bearing=h.direcao_vento,
                cloud_coverage=h.nuvens,
            )
            for ts, h in zip(self.retrato.horas_ts, self.retrato.horas, strict=False)
        ]

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Manhã e noite de cada dia — é o formato que o card padrão do HA usa
        no modo compacto, e ele fica vazio se a integração não o implementar."""
        horaria = await self.async_forecast_hourly()
        if not horaria:
            return None
        saida: list[Forecast] = []
        por_periodo: dict[tuple, list[Forecast]] = {}
        for item in horaria:
            quando = datetime.fromisoformat(item["datetime"])
            chave = (quando.date(), quando.hour < 12)
            por_periodo.setdefault(chave, []).append(item)
        for (_dia, e_dia), itens in sorted(
            por_periodo.items(), key=lambda kv: (kv[0][0], not kv[0][1])
        ):
            temperaturas = [
                i["native_temperature"]
                for i in itens
                if i.get("native_temperature") is not None
            ]
            if not temperaturas:
                continue
            meio = itens[len(itens) // 2]
            saida.append(
                Forecast(
                    datetime=meio["datetime"],
                    is_daytime=e_dia,
                    condition=meio.get("condition"),
                    native_temperature=max(temperaturas),
                    native_templow=min(temperaturas),
                    precipitation_probability=max(
                        (i.get("precipitation_probability") or 0) for i in itens
                    ),
                )
            )
        return saida

    def _fuso(self):
        segundos = int((self.retrato.meta or {}).get("utc_offset_seconds") or 0)
        from datetime import timezone

        return timezone(timedelta(seconds=segundos))

    def _condicao_do_dia(self, d) -> str | None:
        from . import codigos

        return codigos.condicao(d.codigo, dia=True) if d.codigo is not None else None
