"""Constantes do MW Letícia Weather."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "mw_leticia_weather"
NOME: Final = "MW Letícia Weather"
FABRICANTE: Final = "Visão de Empresa"

PLATAFORMAS: Final = ["weather", "sensor", "binary_sensor"]

# ── config entry ─────────────────────────────────────────────────────────────
# `section()` do config flow devolve DICIONÁRIO ANINHADO. Guardar plano faz a
# tela de opções reabrir vazia — armadilha registrada em
# IA/knowledge/ha-integracao-propria-config-flow.md.
SECAO_LOCAL: Final = "local"
SECAO_FUSAO: Final = "fusao"
SECAO_ALERTAS: Final = "alertas"
SECAO_CALIBRACAO: Final = "calibracao"

CONF_NOME: Final = "nome"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_ALTITUDE: Final = "altitude"
CONF_MODELOS: Final = "modelos"
CONF_INTERVALO: Final = "intervalo_min"
CONF_APRENDER_PESOS: Final = "aprender_pesos"
CONF_ALERTAS_OFICIAIS: Final = "oficiais"
CONF_ALERTAS_DERIVADOS: Final = "derivados"
CONF_CALIBRAR: Final = "calibrar"
CONF_SENSOR_LOCAL: Final = "sensor_local"

# ── padrões ──────────────────────────────────────────────────────────────────
# 15 min: o passo horário dos modelos é de 1 h e a Open-Meteo republica a cada
# ~15 min. Ir mais rápido gasta rede sem trazer número novo.
INTERVALO_PADRAO: Final = 15
INTERVALO_MIN: Final = 5

# Os cinco modelos que a Open-Meteo entrega numa única chamada (verificado em
# 2026-09-09). `metno_seamless` é o MESMO modelo da integração met.no nativa do
# HA — de propósito: a fusão precisa conter a fonte que a casa já usava, senão
# a comparação com o passado não fecha.
MODELOS_PADRAO: Final = [
    "ecmwf_ifs025",
    "gfs_seamless",
    "icon_seamless",
    "metno_seamless",
]
MODELOS_DISPONIVEIS: Final = [
    *MODELOS_PADRAO,
    "jma_seamless",
    "gem_seamless",
    "meteofrance_seamless",
    "ukmo_seamless",
]
MODELOS_ROTULO: Final = {
    "ecmwf_ifs025": "ECMWF (Europa)",
    "gfs_seamless": "GFS (EUA)",
    "icon_seamless": "ICON (Alemanha)",
    "metno_seamless": "MET Norway",
    "jma_seamless": "JMA (Japão)",
    "gem_seamless": "GEM (Canadá)",
    "meteofrance_seamless": "Météo-France",
    "ukmo_seamless": "UK Met Office",
}

# A CALIBRAÇÃO LOCAL NASCE DESLIGADA — decisão do dono em 2026-09-09. Ela é
# poderosa e por isso mesmo perigosa: um sensor de janela com desvio de 2 °C
# arrastaria o número principal sem ninguém perceber. Quando ligada, publica
# uma entidade SEPARADA, nunca sobrescreve a fundida.
CALIBRAR_PADRAO: Final = False

SINAL_DADOS: Final = f"{DOMAIN}_dados"
STORE_VERSAO: Final = 1
STORE_PESOS: Final = f"{DOMAIN}.pesos"
STORE_GEO: Final = f"{DOMAIN}.geocodificacao"

ATRIBUICAO: Final = (
    "Open-Meteo (ECMWF, GFS, ICON, MET Norway) · INMET · NWS · MeteoAlarm"
)
