"""Coordinator: o único lugar desta integração que toca a rede.

Orçamento declarado, porque o inspetor de integração mede: **3 requisições por
ciclo por local** (previsão, ar, avisos oficiais), a cada 15 minutos. Nada de
sessão própria — a do HA, compartilhada. Nada de I/O bloqueante no event loop.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import montagem, recuo
from .const import (
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
    MODELOS_PADRAO,
    SECAO_ALERTAS,
    SECAO_CALIBRACAO,
    SECAO_FUSAO,
    SECAO_LOCAL,
    STORE_PESOS,
    STORE_VERSAO,
)
from .fontes import ar as fonte_ar
from .fontes import avisos_inmet, avisos_nws
from .fontes import open_meteo as om
from .fusao import atualizar_pesos

_LOG = logging.getLogger(__name__)

# Identificar-se é cortesia com provedor gratuito — e no NWS é obrigatório: ele
# devolve 403 para agente genérico.
AGENTE = (
    "mw-ha-leticia-weather (+https://github.com/visaodeempresa/mw-ha-leticia-weather)"
)
TEMPO_LIMITE = aiohttp.ClientTimeout(total=25)

# Cache dos avisos oficiais, em segundos (ver o comentário no __init__).
TTL_AVISOS = 30 * 60

# Suavização da calibração: ~24 ciclos de meia-vida no intervalo padrão.
ALFA_CALIBRACAO = 0.03


def _secao(entry: ConfigEntry, secao: str) -> dict:
    """`section()` do config flow grava DICIONÁRIO ANINHADO. Ler plano faz a
    tela de opções reabrir vazia — armadilha registrada no harness."""
    fonte = {**entry.data, **entry.options}
    valor = fonte.get(secao)
    return valor if isinstance(valor, dict) else {}


class CoordenadorClima(DataUpdateCoordinator[montagem.Retrato]):
    """Um por local."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        local = _secao(entry, SECAO_LOCAL)
        fusao_cfg = _secao(entry, SECAO_FUSAO)
        minutos = int(fusao_cfg.get(CONF_INTERVALO) or INTERVALO_PADRAO)
        super().__init__(
            hass,
            _LOG,
            name=f"{DOMAIN}:{entry.entry_id[:8]}",
            update_interval=timedelta(minutes=max(minutos, 5)),
            config_entry=entry,
        )
        self.entry = entry
        self.lugar: str = local.get(CONF_NOME) or hass.config.location_name
        self.latitude: float = float(local.get(CONF_LATITUDE, hass.config.latitude))
        self.longitude: float = float(local.get(CONF_LONGITUDE, hass.config.longitude))
        self.modelos: list[str] = list(fusao_cfg.get(CONF_MODELOS) or MODELOS_PADRAO)
        self._sessao = async_get_clientsession(hass)
        self._store: Store = Store(
            hass, STORE_VERSAO, f"{STORE_PESOS}.{entry.entry_id}"
        )
        self.pesos: dict[str, float] = {}
        self._falhas = 0
        # O /avisos/ativos do INMET traz o BRASIL INTEIRO: 621 KiB por chamada,
        # 58 MiB por dia a cada 15 min — para tipicamente meia dúzia de avisos.
        # Aviso meteorológico é emitido em hora cheia, não a cada quarto de
        # hora, então 30 min de cache não perde nada e devolve 3/4 da banda.
        self._cache_avisos: tuple[float, list[dict]] | None = None
        self._offset: float | None = None

    def _intervalo_normal(self) -> timedelta:
        """O intervalo configurado, com o piso. Num lugar só: o recuo precisa
        saber de onde parte, e a volta precisa saber para onde voltar."""
        minutos = int(
            _secao(self.entry, SECAO_FUSAO).get(CONF_INTERVALO) or INTERVALO_PADRAO
        )
        return timedelta(minutes=max(minutos, INTERVALO_MIN))

    async def async_carregar_pesos(self) -> None:
        guardado = await self._store.async_load()
        self.pesos = dict((guardado or {}).get("pesos") or {})

    async def _buscar(self, url: str) -> dict | None:
        """Uma requisição. Erro de rede NÃO derruba o ciclo inteiro: cada fonte
        é opcional menos a previsão, e quem some volta no próximo ciclo."""
        try:
            async with self._sessao.get(
                url, timeout=TEMPO_LIMITE, headers={"User-Agent": AGENTE}
            ) as resposta:
                if resposta.status != 200:
                    _LOG.debug("%s respondeu %s", url.split("?")[0], resposta.status)
                    return None
                return await resposta.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError, ValueError) as erro:
            _LOG.debug("falha em %s: %s", url.split("?")[0], erro)
            return None

    async def _async_update_data(self) -> montagem.Retrato:
        alertas_cfg = _secao(self.entry, SECAO_ALERTAS)
        fusao_cfg = _secao(self.entry, SECAO_FUSAO)
        oficiais = alertas_cfg.get(CONF_ALERTAS_OFICIAIS, True)

        tarefas = [
            self._buscar(om.url(self.latitude, self.longitude, self.modelos)),
            self._buscar(fonte_ar.url(self.latitude, self.longitude)),
        ]
        if oficiais:
            tarefas.append(self._avisos_oficiais())
        else:
            tarefas.append(asyncio.sleep(0, result=[]))

        previsao, ar_bruto, avisos = await asyncio.gather(*tarefas)

        if not previsao or not om.eixo_tempo(previsao):
            self._falhas += 1
            # RECUO DE VERDADE: o intervalo cresce A PARTIR do intervalo
            # normal, nunca abaixo dele.
            #
            # A primeira versão era `min(2**falhas, 8) * 60`, que na primeira
            # falha dava 120 s — oito vezes MAIS rápido que os 900 s normais.
            # Um "backoff" que acelera é um acelerador: o provedor tremendo
            # passaria a receber 87 requisições por hora em vez de 12, e a
            # instabilidade viraria justamente o bloqueio que este comentário
            # dizia evitar. Achado pelo inspetor de integração em 2026-09-09.
            espera = recuo.atraso(
                self._intervalo_normal().total_seconds(), self._falhas
            )
            # O sorteio existe para N casas não voltarem no mesmo segundo.
            self.update_interval = timedelta(seconds=espera + random.uniform(0, 30))

            raise UpdateFailed("a previsão não veio; tentando de novo com recuo")

        if self._falhas:
            self._falhas = 0
            self.update_interval = self._intervalo_normal()

        agora = dt_util.now()
        retrato = await self.hass.async_add_executor_job(
            self._montar, previsao, ar_bruto, avisos, agora, alertas_cfg
        )

        self._calibrar(retrato)

        if fusao_cfg.get(CONF_APRENDER_PESOS, True):
            await self._aprender(retrato)
        return retrato

    def _calibrar(self, retrato: montagem.Retrato) -> None:
        """Ancoragem opcional no sensor da casa. NASCE DESLIGADA.

        O que ela faz: acompanha a diferença entre o seu sensor externo e o
        consenso dos modelos, suavizada, e publica uma entidade SEPARADA com o
        valor ancorado. O que ela NÃO faz: mexer no número fundido. Um sensor
        de janela com 2 °C de desvio arrastaria a casa inteira sem ninguém
        perceber — por isso a correção sai ao lado, nomeada, e não por dentro.
        """
        cfg = _secao(self.entry, SECAO_CALIBRACAO)
        if not cfg.get(CONF_CALIBRAR):
            return
        entidade = cfg.get(CONF_SENSOR_LOCAL)
        consenso = retrato.agora.temperatura
        if not entidade or consenso is None:
            return
        estado = self.hass.states.get(entidade)
        if estado is None or estado.state in ("unknown", "unavailable", ""):
            return
        try:
            local = float(estado.state)
        except (TypeError, ValueError):
            return
        diferenca = local - consenso
        # Média móvel exponencial: um dia frio não vira calibração permanente.
        # ALFA_CALIBRACAO ≈ 24 ciclos de meia-vida com o intervalo padrão.
        self._offset = (
            diferenca
            if self._offset is None
            else self._offset + ALFA_CALIBRACAO * (diferenca - self._offset)
        )
        retrato.calibracao = {
            "sensor": entidade,
            "leitura_local": local,
            "consenso": consenso,
            "offset": round(self._offset, 2),
            "temperatura": round(consenso + self._offset, 2),
        }

    def _montar(
        self, previsao, ar_bruto, avisos, agora, alertas_cfg
    ) -> montagem.Retrato:
        """Montagem é CPU pura sobre listas de centenas de pontos: vai para o
        executor para não segurar o event loop."""
        return montagem.montar(
            lugar=self.lugar,
            latitude=self.latitude,
            longitude=self.longitude,
            previsao=previsao,
            modelos=self.modelos,
            agora=agora,
            pesos=self.pesos,
            ar_bruto=ar_bruto,
            avisos_oficiais=avisos or [],
            derivar_alertas=alertas_cfg.get(CONF_ALERTAS_DERIVADOS, True),
        )

    async def _avisos_oficiais(self) -> list[dict]:
        """A fonte oficial depende de ONDE o local está. Fora das três
        coberturas, a lista vem vazia — e o alerta derivado é quem cobre, com o
        rótulo de derivado bem visível."""
        if -34 <= self.latitude <= 6 and -75 <= self.longitude <= -33:
            agora = time.monotonic()
            if self._cache_avisos and agora - self._cache_avisos[0] < TTL_AVISOS:
                return self._cache_avisos[1]
            dados = await self._buscar(avisos_inmet.URL)
            if dados:
                meus = avisos_inmet.interpretar(
                    dados,
                    self.latitude,
                    self.longitude,
                    ibge=_secao(self.entry, SECAO_ALERTAS).get("ibge"),
                )
                self._cache_avisos = (agora, meus)
                return meus
            # Falhou: devolve o cache velho em vez de "não há aviso". Silêncio
            # por erro de rede não pode virar ausência de risco.
            return self._cache_avisos[1] if self._cache_avisos else []
        if 18 <= self.latitude <= 72 and -170 <= self.longitude <= -60:
            dados = await self._buscar(avisos_nws.url(self.latitude, self.longitude))
            return avisos_nws.interpretar(dados) if dados else []
        return []

    async def _aprender(self, retrato: montagem.Retrato) -> None:
        """Skill score: o erro de cada modelo contra o consenso do próprio
        ciclo. Não é validação contra observação — é concordância — e por isso
        o peso tem piso: um modelo teimosamente diferente perde voto, mas nunca
        é silenciado."""
        consenso = retrato.agora.temperatura
        if consenso is None or not retrato.agora.por_modelo:
            return
        erros = {m: abs(v - consenso) for m, v in retrato.agora.por_modelo.items()}
        self.pesos = atualizar_pesos(self.pesos, erros)
        await self._store.async_save({"pesos": self.pesos})
