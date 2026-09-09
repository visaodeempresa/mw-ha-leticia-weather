"""Config flow e tela de opções.

ARMADILHA REGISTRADA NO HARNESS (e obedecida aqui): `section()` grava
DICIONÁRIO ANINHADO. Guardar plano — ou ler plano — faz a tela de opções
reabrir **vazia**, sem erro nenhum. Por isso tudo aqui entra e sai por seção.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CALIBRAR_PADRAO,
    CONF_ALERTAS_DERIVADOS,
    CONF_ALERTAS_OFICIAIS,
    CONF_APRENDER_PESOS,
    CONF_CALIBRAR,
    CONF_INTERVALO,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODELOS,
    CONF_NOME,
    CONF_SENSOR_LOCAL,
    DOMAIN,
    INTERVALO_MIN,
    INTERVALO_PADRAO,
    MODELOS_DISPONIVEIS,
    MODELOS_PADRAO,
    MODELOS_ROTULO,
    SECAO_ALERTAS,
    SECAO_CALIBRACAO,
    SECAO_FUSAO,
    SECAO_LOCAL,
)


def _esquema(
    hass, dados: dict[str, Any] | None = None, *, opcoes: bool = False
) -> vol.Schema:
    dados = dados or {}
    local = dados.get(SECAO_LOCAL, {})
    fusao = dados.get(SECAO_FUSAO, {})
    alertas = dados.get(SECAO_ALERTAS, {})
    calibracao = dados.get(SECAO_CALIBRACAO, {})
    base = vol.Schema(
        {
            vol.Required(SECAO_LOCAL): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_NOME,
                            default=local.get(CONF_NOME, hass.config.location_name),
                        ): TextSelector(),
                        vol.Required(
                            "coordenada",
                            default=local.get(
                                "coordenada",
                                {
                                    "latitude": hass.config.latitude,
                                    "longitude": hass.config.longitude,
                                },
                            ),
                        ): LocationSelector(),
                    }
                ),
                {"collapsed": False},
            ),
            vol.Required(SECAO_FUSAO): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_MODELOS,
                            default=fusao.get(CONF_MODELOS, MODELOS_PADRAO),
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    {"value": m, "label": MODELOS_ROTULO.get(m, m)}
                                    for m in MODELOS_DISPONIVEIS
                                ],
                                multiple=True,
                                mode=SelectSelectorMode.LIST,
                            )
                        ),
                        vol.Required(
                            CONF_INTERVALO,
                            default=fusao.get(CONF_INTERVALO, INTERVALO_PADRAO),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=INTERVALO_MIN,
                                max=180,
                                step=5,
                                mode=NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Required(
                            CONF_APRENDER_PESOS,
                            default=fusao.get(CONF_APRENDER_PESOS, True),
                        ): BooleanSelector(),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required(SECAO_ALERTAS): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_ALERTAS_OFICIAIS,
                            default=alertas.get(CONF_ALERTAS_OFICIAIS, True),
                        ): BooleanSelector(),
                        vol.Required(
                            CONF_ALERTAS_DERIVADOS,
                            default=alertas.get(CONF_ALERTAS_DERIVADOS, True),
                        ): BooleanSelector(),
                        vol.Optional(
                            "ibge", default=alertas.get("ibge", "")
                        ): TextSelector(),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )
    if not opcoes:
        # A CALIBRAÇÃO SÓ APARECE NAS OPÇÕES, e por dois motivos.
        # 1. Ela nasce DESLIGADA (decisão do dono em 2026-09-09): é poderosa e
        #    por isso perigosa — um sensor de janela com desvio arrastaria o
        #    número principal sem ninguém perceber.
        # 2. Ninguém escolhe o sensor externo antes de a integração existir. E
        #    um `EntitySelector` opcional na tela de instalação é armadilha:
        #    submetido vazio, o flow recusa com «Entity  is neither a valid
        #    entity ID nor a valid UUID» — sem dizer que o culpado é o campo
        #    vazio. Medido no HA 2026.9.1.
        return base
    return base.extend(
        {
            vol.Required(SECAO_CALIBRACAO): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_CALIBRAR,
                            default=calibracao.get(CONF_CALIBRAR, CALIBRAR_PADRAO),
                        ): BooleanSelector(),
                        vol.Optional(
                            CONF_SENSOR_LOCAL,
                            # SEM `default=""`: o EntitySelector valida o
                            # default ao ENVIAR o formulário, e string vazia
                            # não é entity_id nem UUID — o flow recusa com
                            # «Entity  is neither a valid entity ID nor a
                            # valid UUID» sem dizer que o culpado é o próprio
                            # default. Valor já escolhido volta por
                            # `suggested_value`.
                            description={
                                "suggested_value": calibracao.get(CONF_SENSOR_LOCAL)
                            },
                        ): EntitySelector(
                            EntitySelectorConfig(
                                domain="sensor", device_class="temperature"
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def _normalizar(entrada: dict[str, Any]) -> dict[str, Any]:
    """Achata a coordenada do `LocationSelector` para os campos que o
    coordinator lê — mantendo a estrutura aninhada das seções."""
    dados = {chave: dict(valor) for chave, valor in entrada.items()}
    local = dados.get(SECAO_LOCAL, {})
    coordenada = local.pop("coordenada", None) or {}
    local[CONF_LATITUDE] = coordenada.get("latitude")
    local[CONF_LONGITUDE] = coordenada.get("longitude")
    dados[SECAO_LOCAL] = local
    fusao = dados.get(SECAO_FUSAO, {})
    if not fusao.get(CONF_MODELOS):
        fusao[CONF_MODELOS] = list(MODELOS_PADRAO)
    fusao[CONF_INTERVALO] = int(fusao.get(CONF_INTERVALO, INTERVALO_PADRAO))
    dados[SECAO_FUSAO] = fusao
    return dados


class FluxoClima(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        erros: dict[str, str] = {}
        if user_input is not None:
            dados = _normalizar(user_input)
            local = dados[SECAO_LOCAL]
            if local.get(CONF_LATITUDE) is None:
                erros["base"] = "sem_coordenada"
            else:
                # Uma entrada por COORDENADA (arredondada a ~1 km): dois locais
                # no mesmo ponto de grade seriam a mesma previsão publicada duas
                # vezes, com duas contagens de requisição.
                await self.async_set_unique_id(
                    f"{local[CONF_LATITUDE]:.2f},{local[CONF_LONGITUDE]:.2f}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=local[CONF_NOME], data=dados)
        return self.async_show_form(
            step_id="user", data_schema=_esquema(self.hass, user_input), errors=erros
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return OpcoesClima()


class OpcoesClima(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_normalizar(user_input))
        atual = {**self.config_entry.data, **self.config_entry.options}
        # Devolver a coordenada para o formato do LocationSelector: sem isto o
        # mapa da tela de opções abre no meio do oceano.
        local = dict(atual.get(SECAO_LOCAL, {}))
        if CONF_LATITUDE in local:
            local["coordenada"] = {
                "latitude": local.get(CONF_LATITUDE),
                "longitude": local.get(CONF_LONGITUDE),
            }
        atual = {**atual, SECAO_LOCAL: local}
        return self.async_show_form(
            step_id="init", data_schema=_esquema(self.hass, atual)
        )
