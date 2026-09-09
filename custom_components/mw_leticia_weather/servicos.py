"""Serviços com RESPOSTA — é por aqui que a Letícia pergunta por uma cidade
qualquer do mundo.

`SupportsResponse.ONLY` + `?return_response` na chamada REST (armadilha
registrada em IA/knowledge/ha-integracao-propria-config-flow.md: sem o
parâmetro, o HA devolve 200 vazio e ninguém entende por quê).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

import aiohttp
import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import fala, montagem
from .const import DOMAIN, MODELOS_PADRAO, MODELOS_ROTULO, STORE_GEO, STORE_VERSAO
from .coordinator import AGENTE, TEMPO_LIMITE
from .fontes import ar as fonte_ar
from .fontes import avisos_inmet, avisos_nws, geocodificacao
from .fontes import open_meteo as om

_LOG = logging.getLogger(__name__)

PERIODOS = ("agora", "hoje", "amanha", "fim_de_semana", "proximos")

ESQUEMA_PREVISAO = vol.Schema(
    {
        vol.Optional("cidade"): cv.string,
        vol.Optional("entry_id"): cv.string,
        vol.Optional("periodo", default="agora"): vol.In(PERIODOS),
        vol.Optional("dias", default=3): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=14)
        ),
    }
)
ESQUEMA_ALERTAS = vol.Schema(
    {vol.Optional("cidade"): cv.string, vol.Optional("entry_id"): cv.string}
)
ESQUEMA_FONTES = vol.Schema({vol.Optional("entry_id"): cv.string})


def _coordenadores(hass: HomeAssistant) -> list:
    return list(hass.data.get(DOMAIN, {}).values())


def _escolher(hass: HomeAssistant, entry_id: str | None):
    dados = hass.data.get(DOMAIN, {})
    if entry_id and entry_id in dados:
        return dados[entry_id]
    return next(iter(dados.values()), None)


async def _retrato_de_cidade(
    hass: HomeAssistant, cidade: str
) -> montagem.Retrato | None:
    """Busca sob demanda, sem criar entidade nenhuma.

    Perguntar por Lisboa não pode encher o registro de entidades de Lisboa —
    a pergunta é episódica e a resposta é uma frase.
    """
    sessao = async_get_clientsession(hass)
    store: Store = Store(hass, STORE_VERSAO, STORE_GEO)

    async def buscar(url: str) -> dict | None:
        try:
            async with sessao.get(
                url, timeout=TEMPO_LIMITE, headers={"User-Agent": AGENTE}
            ) as r:
                return await r.json(content_type=None) if r.status == 200 else None
        except (TimeoutError, aiohttp.ClientError, ValueError):
            return None

    cache = await store.async_load() or {}
    chave = geocodificacao.chave(cidade)
    lugar = cache.get(chave)
    if not lugar:
        bruto = await buscar(geocodificacao.url(cidade))
        lugar = geocodificacao.melhor(geocodificacao.interpretar(bruto or {}))
        if not lugar:
            return None
        cache[chave] = lugar
        await store.async_save(cache)

    lat, lon = float(lugar["latitude"]), float(lugar["longitude"])
    previsao, ar_bruto = await asyncio.gather(
        buscar(om.url(lat, lon, list(MODELOS_PADRAO))),
        buscar(fonte_ar.url(lat, lon)),
    )
    if not previsao:
        return None
    avisos: list[dict] = []
    if -34 <= lat <= 6 and -75 <= lon <= -33:
        dados = await buscar(avisos_inmet.URL)
        if dados:
            avisos = avisos_inmet.interpretar(dados, lat, lon)
    elif 18 <= lat <= 72 and -170 <= lon <= -60:
        dados = await buscar(avisos_nws.url(lat, lon))
        avisos = avisos_nws.interpretar(dados) if dados else []
    return await hass.async_add_executor_job(
        lambda: montagem.montar(
            lugar=geocodificacao.rotulo(lugar),
            latitude=lat,
            longitude=lon,
            previsao=previsao,
            modelos=list(MODELOS_PADRAO),
            agora=dt_util.now(),
            ar_bruto=ar_bruto,
            avisos_oficiais=avisos,
        )
    )


async def _resolver(
    hass: HomeAssistant, chamada: ServiceCall
) -> montagem.Retrato | None:
    cidade = chamada.data.get("cidade")
    if cidade:
        return await _retrato_de_cidade(hass, cidade)
    coordenador = _escolher(hass, chamada.data.get("entry_id"))
    return coordenador.data if coordenador else None


def _dias_como_lista(r: montagem.Retrato) -> list[dict]:
    return [
        {
            "data": d.data,
            "minima": d.minima,
            "maxima": d.maxima,
            "codigo": d.codigo,
            "chuva_probabilidade": d.chuva_probabilidade,
            "umidade_min": d.umidade_min,
        }
        for d in r.dias
    ]


async def registrar(hass: HomeAssistant) -> None:
    async def previsao(chamada: ServiceCall) -> ServiceResponse:
        r = await _resolver(hass, chamada)
        if r is None:
            return {
                "encontrado": False,
                "fala": "Não encontrei essa cidade na minha lista.",
            }
        hoje = (r.atualizado_em or dt_util.now()).date()
        periodo = chamada.data.get("periodo", "agora")
        if periodo == "agora":
            texto = r.falas.get("fala_agora", "")
        elif periodo == "hoje":
            texto = r.falas.get("fala_hoje", "")
        elif periodo == "amanha":
            texto = r.falas.get("fala_amanha", "")
        elif periodo == "fim_de_semana":
            texto = fala.fim_de_semana(_dias_como_lista(r), hoje)
        else:
            texto = fala.proximos(
                _dias_como_lista(r), hoje, int(chamada.data.get("dias", 3))
            )
        return {
            "encontrado": True,
            "lugar": r.lugar,
            "periodo": periodo,
            "fala": texto,
            "agora": {
                "temperatura": r.agora.temperatura,
                "sensacao": r.agora.sensacao,
                "umidade": r.agora.umidade,
                "pressao_msl": r.agora.pressao_msl,
                "condicao": r.agora.condicao,
                "confianca_spread": r.agora.spread,
            },
            "dias": [
                {
                    **{
                        k: (v.isoformat() if isinstance(v, (date, datetime)) else v)
                        for k, v in d.items()
                    }
                }
                for d in _dias_como_lista(r)[:8]
            ],
        }

    async def alertas(chamada: ServiceCall) -> ServiceResponse:
        r = await _resolver(hass, chamada)
        if r is None:
            return {
                "encontrado": False,
                "fala": "Não encontrei essa cidade na minha lista.",
            }
        lista = [a.como_dicionario() for a in r.alertas]
        return {
            "encontrado": True,
            "lugar": r.lugar,
            "quantidade": len(lista),
            "oficiais": sum(1 for a in lista if a["oficial"]),
            "fala": fala.alertas(lista, r.lugar),
            "alertas": lista,
        }

    async def comparar_fontes(chamada: ServiceCall) -> ServiceResponse:
        """A resposta para «por que o iPhone diz 20 e o card diz 19».

        Devolve modelo a modelo, o consenso, a discórdia e o ponto de grade que
        cada resposta realmente representa — que é metade da explicação.
        """
        coordenador = _escolher(hass, chamada.data.get("entry_id"))
        r = coordenador.data if coordenador else None
        if r is None:
            return {"disponivel": False}
        return {
            "disponivel": True,
            "lugar": r.lugar,
            "consenso": r.agora.temperatura,
            "p10": r.agora.temperatura_p10,
            "p90": r.agora.temperatura_p90,
            "spread": r.agora.spread,
            "modelos": [
                {
                    "modelo": m,
                    "rotulo": MODELOS_ROTULO.get(m, m),
                    "temperatura": v,
                    "desvio": round(v - r.agora.temperatura, 2)
                    if r.agora.temperatura is not None
                    else None,
                    "peso": round(r.pesos.get(m, 1.0), 3),
                    "descartado": m in r.agora.descartados,
                }
                for m, v in {**r.agora.por_modelo, **r.agora.descartados}.items()
            ],
            "ponto_de_grade": r.meta,
            "atualizado_em": r.atualizado_em.isoformat() if r.atualizado_em else None,
        }

    for nome, funcao, esquema in (
        ("previsao", previsao, ESQUEMA_PREVISAO),
        ("alertas", alertas, ESQUEMA_ALERTAS),
        ("comparar_fontes", comparar_fontes, ESQUEMA_FONTES),
    ):
        if not hass.services.has_service(DOMAIN, nome):
            hass.services.async_register(
                DOMAIN,
                nome,
                funcao,
                schema=esquema,
                supports_response=SupportsResponse.ONLY,
            )


def remover(hass: HomeAssistant) -> None:
    """Só some com os serviços quando a ÚLTIMA entrada sai — senão remover um
    local de dois derruba a voz da casa inteira."""
    if _coordenadores(hass):
        return
    for nome in ("previsao", "alertas", "comparar_fontes"):
        hass.services.async_remove(DOMAIN, nome)
