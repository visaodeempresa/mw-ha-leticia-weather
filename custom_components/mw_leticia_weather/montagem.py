"""Monta o retrato do tempo a partir das respostas cruas. Módulo PURO.

Fica separado do coordinator de propósito: aqui não há rede, não há HA e não há
relógio implícito — tudo entra por parâmetro. É o que permite provar a fusão
com JSON gravado, em `pytest`, sem instalar Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from . import alertas as mod_alertas
from . import codigos, fala, fusao
from .fontes import ar as fonte_ar
from .fontes import open_meteo as om

# Variáveis horárias que valem fusão de verdade (as demais viriam do modelo
# padrão e não mudariam decisão nenhuma).
_CONTINUAS = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "precipitation_probability",
    "cloud_cover",
    "pressure_msl",
    "surface_pressure",
    "wind_speed_10m",
    "wind_gusts_10m",
    "cape",
)


@dataclass
class Momento:
    """Um instante, com o número e a discórdia que o produziu."""

    temperatura: float | None = None
    temperatura_p10: float | None = None
    temperatura_p90: float | None = None
    spread: float | None = None
    sensacao: float | None = None
    umidade: float | None = None
    precipitacao: float | None = None
    chuva_probabilidade: float | None = None
    nuvens: float | None = None
    pressao_msl: float | None = None
    pressao_estacao: float | None = None
    vento: float | None = None
    rajada: float | None = None
    direcao_vento: float | None = None
    cape: float | None = None
    codigo: int | None = None
    dia_claro: bool = True
    por_modelo: dict[str, float] = field(default_factory=dict)
    descartados: dict[str, float] = field(default_factory=dict)

    @property
    def condicao(self) -> str:
        return codigos.condicao(self.codigo, dia=self.dia_claro)


@dataclass
class DiaPrevisto:
    data: date
    minima: float | None = None
    maxima: float | None = None
    sensacao_max: float | None = None
    sensacao_min: float | None = None
    codigo: int | None = None
    chuva: float | None = None
    chuva_probabilidade: float | None = None
    vento_max: float | None = None
    rajada_max: float | None = None
    direcao_vento: float | None = None
    uv_max: float | None = None
    umidade_min: float | None = None
    nascer: datetime | None = None
    por: datetime | None = None
    spread_maxima: float | None = None


@dataclass
class Retrato:
    """Tudo que a integração publica num ciclo."""

    lugar: str
    latitude: float
    longitude: float
    agora: Momento
    horas: list[Momento] = field(default_factory=list)
    horas_ts: list[float] = field(default_factory=list)
    dias: list[DiaPrevisto] = field(default_factory=list)
    ar: dict = field(default_factory=dict)
    alertas: list[mod_alertas.Alerta] = field(default_factory=list)
    falas: dict[str, str] = field(default_factory=dict)
    pesos: dict[str, float] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    pressao_3h_atras: float | None = None
    atualizado_em: datetime | None = None


def _momento(
    dados: dict, modelos: list[str], indice: int, pesos: dict[str, float]
) -> Momento:
    m = Momento()
    fundidos: dict[str, fusao.Fusao] = {}
    for variavel in _CONTINUAS:
        fundidos[variavel] = fusao.fundir(
            om.amostras_em(dados, modelos, variavel, indice), pesos
        )
    temperatura = fundidos["temperature_2m"]
    m.temperatura = temperatura.valor
    m.temperatura_p10 = temperatura.p10
    m.temperatura_p90 = temperatura.p90
    m.spread = temperatura.spread
    m.por_modelo = dict(temperatura.usados)
    m.descartados = dict(temperatura.descartados)
    m.sensacao = fundidos["apparent_temperature"].valor
    m.umidade = fundidos["relative_humidity_2m"].valor
    m.precipitacao = fundidos["precipitation"].valor
    m.chuva_probabilidade = fundidos["precipitation_probability"].valor
    m.nuvens = fundidos["cloud_cover"].valor
    m.pressao_msl = fundidos["pressure_msl"].valor
    m.pressao_estacao = fundidos["surface_pressure"].valor
    m.vento = fundidos["wind_speed_10m"].valor
    m.rajada = fundidos["wind_gusts_10m"].valor
    m.cape = fundidos["cape"].valor
    m.direcao_vento = fusao.fundir_angulo(
        om.amostras_em(dados, modelos, "wind_direction_10m", indice), pesos
    ).valor
    codigo = fusao.fundir_categoria(
        om.amostras_em(dados, modelos, "weather_code", indice), pesos
    ).valor
    m.codigo = int(codigo) if codigo is not None else None
    claro = fusao.fundir_categoria(
        om.amostras_em(dados, modelos, "is_day", indice), pesos
    ).valor
    m.dia_claro = bool(claro) if claro is not None else True
    return m


def _dia(bruto: dict, fuso_offset: int) -> DiaPrevisto:
    def f(variavel: str) -> float | None:
        return fusao.fundir(om.amostras_diarias(bruto, variavel)).valor

    def quando(variavel: str) -> datetime | None:
        v = fusao.fundir(om.amostras_diarias(bruto, variavel)).valor
        if v is None:
            return None
        return datetime.fromtimestamp(v, tz=timezone(timedelta(seconds=fuso_offset)))

    maxima = fusao.fundir(om.amostras_diarias(bruto, "temperature_2m_max"))
    codigo = fusao.fundir_categoria(om.amostras_diarias(bruto, "weather_code")).valor
    return DiaPrevisto(
        data=datetime.fromtimestamp(
            bruto["time"], tz=timezone(timedelta(seconds=fuso_offset))
        ).date(),
        minima=f("temperature_2m_min"),
        maxima=maxima.valor,
        spread_maxima=maxima.spread,
        sensacao_max=f("apparent_temperature_max"),
        sensacao_min=f("apparent_temperature_min"),
        codigo=int(codigo) if codigo is not None else None,
        chuva=f("precipitation_sum"),
        chuva_probabilidade=f("precipitation_probability_max"),
        vento_max=f("wind_speed_10m_max"),
        rajada_max=f("wind_gusts_10m_max"),
        direcao_vento=fusao.fundir_angulo(
            om.amostras_diarias(bruto, "wind_direction_10m_dominant")
        ).valor,
        uv_max=f("uv_index_max"),
        umidade_min=f("relative_humidity_2m_min"),
        nascer=quando("sunrise"),
        por=quando("sunset"),
    )


def montar(
    *,
    lugar: str,
    latitude: float,
    longitude: float,
    previsao: dict,
    modelos: list[str],
    agora: datetime,
    pesos: dict[str, float] | None = None,
    ar_bruto: dict | None = None,
    avisos_oficiais: list[dict] | None = None,
    derivar_alertas: bool = True,
    horas_a_publicar: int = 48,
) -> Retrato:
    pesos = pesos or {}
    tempos = om.eixo_tempo(previsao)
    meta = om.metadados(previsao)
    offset = int(meta.get("utc_offset_seconds") or 0)
    presentes = list(om.series_por_modelo(previsao, modelos).keys())

    i_agora = om.indice_de(tempos, agora)
    momento = _momento(previsao, presentes, i_agora, pesos)

    horas: list[Momento] = []
    horas_ts: list[float] = []
    for i in range(i_agora, min(i_agora + horas_a_publicar, len(tempos))):
        horas.append(_momento(previsao, presentes, i, pesos))
        horas_ts.append(tempos[i])

    dias = [_dia(d, offset) for d in om.diario_por_modelo(previsao, presentes)]

    # Pressão de 3 h atrás: é o ponteiro de memória do barômetro e a entrada da
    # tendência do Zambretti. Vem do passado da própria série (por isso
    # `past_days=1` na URL) — não de histórico do recorder, que pode não
    # existir no dia da instalação.
    i_3h = om.indice_de(tempos, agora - timedelta(hours=3))
    pressao_antes = fusao.fundir(
        om.amostras_em(previsao, presentes, "pressure_msl", i_3h), pesos
    ).valor

    ar_dados: dict = {}
    if ar_bruto:
        tempos_ar = fonte_ar.eixo_tempo(ar_bruto)
        i_ar = om.indice_de(tempos_ar, agora)
        ar_dados = fonte_ar.interpretar(ar_bruto, i_ar)

    lista_alertas = [
        mod_alertas.Alerta(**{**a, "valores": a.get("valores", {})})
        for a in _sem_extras(avisos_oficiais or [])
    ]
    if derivar_alertas and dias:
        hoje = dias[0] if dias[0].data == agora.date() else dias[min(1, len(dias) - 1)]
        lista_alertas += mod_alertas.derivar(
            {
                "umidade_min": hoje.umidade_min,
                "sensacao_max": hoje.sensacao_max,
                "temperatura_min": hoje.minima,
                "chuva_max_h": max(
                    (h.precipitacao for h in horas[:24] if h.precipitacao is not None),
                    default=None,
                ),
                "rajada_max": hoje.rajada_max,
                "cape_max": max(
                    (h.cape for h in horas[:24] if h.cape is not None), default=None
                ),
                "uv_max": hoje.uv_max,
            },
            inicio=hoje.nascer,
            fim=hoje.por,
        )
    lista_alertas = mod_alertas.deduplicar(lista_alertas)

    retrato = Retrato(
        lugar=lugar,
        latitude=latitude,
        longitude=longitude,
        agora=momento,
        horas=horas,
        horas_ts=horas_ts,
        dias=dias,
        ar=ar_dados,
        alertas=lista_alertas,
        pesos=dict(pesos),
        meta=meta,
        pressao_3h_atras=pressao_antes,
        atualizado_em=agora,
    )
    retrato.falas = compor_falas(retrato)
    return retrato


def _sem_extras(avisos: list[dict]) -> list[dict]:
    """`Alerta` é um dataclass fechado; campo extra vindo da fonte (como `id`)
    quebraria a construção. Some aqui em vez de espalhar `pop` por três fontes."""
    campos = {
        "tipo",
        "severidade",
        "titulo",
        "descricao",
        "fonte",
        "oficial",
        "inicio",
        "fim",
        "instrucoes",
        "valores",
    }
    return [{k: v for k, v in a.items() if k in campos} for a in avisos]


def compor_falas(r: Retrato) -> dict[str, str]:
    """As frases prontas que viram ATRIBUTO do sensor — é o que faz o
    `intent_script` responder sem passar pelo LLM."""
    hoje = r.atualizado_em.date() if r.atualizado_em else date.today()
    dias = [
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
    do_dia = next((d for d in r.dias if d.data == hoje), r.dias[0] if r.dias else None)
    amanha = next((d for d in r.dias if d.data == hoje + timedelta(days=1)), None)
    falas = {
        "fala_agora": fala.agora(
            lugar=r.lugar,
            temperatura=r.agora.temperatura,
            codigo=r.agora.codigo,
            umidade=r.agora.umidade,
            sensacao=r.agora.sensacao,
            spread=r.agora.spread,
        ),
        "fala_hoje": fala.dia(
            quando=do_dia.data,
            hoje=hoje,
            minima=do_dia.minima,
            maxima=do_dia.maxima,
            codigo=do_dia.codigo,
            chuva_probabilidade=do_dia.chuva_probabilidade,
            umidade_min=do_dia.umidade_min,
        )
        if do_dia
        else "Não tenho a previsão de hoje.",
        "fala_amanha": fala.dia(
            quando=amanha.data,
            hoje=hoje,
            minima=amanha.minima,
            maxima=amanha.maxima,
            codigo=amanha.codigo,
            chuva_probabilidade=amanha.chuva_probabilidade,
            umidade_min=amanha.umidade_min,
        )
        if amanha
        else "Ainda não tenho a previsão de amanhã.",
        "fala_proximos": fala.proximos(dias, hoje, 3),
        "fala_fim_de_semana": fala.fim_de_semana(dias, hoje),
        "fala_alertas": fala.alertas([a.como_dicionario() for a in r.alertas], r.lugar),
    }
    if do_dia and (do_dia.nascer or do_dia.por):
        falas["fala_sol"] = fala.sol(do_dia.nascer, do_dia.por)
    return falas
