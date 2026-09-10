"""Open-Meteo: o conjunto inteiro de modelos numa única chamada.

VERIFICADO EM 2026-09-09 (não re-testar de cabeça):

  ✔ `hourly=temperature_2m&models=ecmwf_ifs025,gfs_seamless,...` devolve
    `temperature_2m_ecmwf_ifs025`, `temperature_2m_gfs_seamless`, … — uma
    coluna por modelo, sufixada. É isso que torna o conjunto barato: 1 GET.

  ✘ `current=temperature_2m&models=...` **COLAPSA** para um valor só, sem
    sufixo. Não existe "agora" multi-modelo. O agora do conjunto tem de ser
    INTERPOLADO das séries horárias (ver `fusao.interpolar`).

Sem chave de API, sem cadastro. A cortesia é usar o `timezone` certo e não
bater mais que o necessário.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

BASE = "https://api.open-meteo.com/v1/forecast"

# Variáveis horárias pedidas por modelo. Cada nome vira N colunas (uma por
# modelo), então acrescentar variável aqui custa banda — a lista é curta de
# propósito e cada linha se justifica.
HORARIAS = (
    "temperature_2m",  # o número principal
    "relative_humidity_2m",  # clima seco é o alerta que mais importa em Brasília
    # sensação: é o que se responde quando perguntam se está quente
    "apparent_temperature",
    "precipitation",  # mm
    "precipitation_probability",
    "weather_code",  # o desenho do céu
    "cloud_cover",  # quanto de nuvem o fundo do cabeçalho pinta
    "pressure_msl",  # AO NÍVEL DO MAR: a casa está a 1200 m (regra 190)
    "surface_pressure",  # a de estação, para quem quiser ver a diferença
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "cape",  # energia convectiva → alerta derivado de tempestade
    "is_day",  # sol ou lua no desenho
)

# Diárias: a Open-Meteo TAMBÉM as devolve sufixadas por modelo quando se pede
# `models=` — 57 colunas para 4 modelos. É de propósito: mínima e máxima do dia
# são exatamente onde os modelos mais discordam, e é essa discórdia que a tela
# da semana desenha.
DIARIAS = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    "sunrise",
    "sunset",
    "uv_index_max",
    "relative_humidity_2m_min",
)


def url(
    latitude: float,
    longitude: float,
    modelos: list[str],
    *,
    dias: int = 16,
    horas: int = 72,
    fuso: str = "auto",
) -> str:
    parametros = {
        "latitude": f"{latitude:.5f}",
        "longitude": f"{longitude:.5f}",
        "hourly": ",".join(HORARIAS),
        "daily": ",".join(DIARIAS),
        "models": ",".join(modelos),
        "forecast_days": str(max(1, min(int(dias), 16))),
        # A série horária é cara: são N colunas por MODELO. Pedir 16 dias de
        # hora em hora para publicar 48 h é pagar 4x de banda por dado que
        # ninguém lê — 113 KiB contra 30 KiB, medido em 2026-09-09.
        #
        # `forecast_hours` + `past_hours` + `forecast_days` CONVIVEM (72
        # linhas horárias e 16 diárias na mesma resposta). O que não
        # convive é `past_hours` SOZINHO: aí a API ignora `forecast_days`
        # e devolve os 16 dias inteiros na série horária.
        #
        # As 24 h de passado são o ponteiro de memória do barômetro.
        "forecast_hours": str(max(6, min(int(horas), 384))),
        "past_hours": "24",
        "timezone": fuso,
        "timeformat": "unixtime",
        "wind_speed_unit": "kmh",
    }
    return f"{BASE}?{urlencode(parametros)}"


def _coluna(bloco: dict, variavel: str, modelo: str | None) -> list | None:
    """A coluna de um modelo, com a queda para a coluna sem sufixo.

    Quando UM modelo só é pedido, a Open-Meteo devolve a coluna **sem** sufixo.
    Quem não trata isso vê a integração inteira ficar vazia no dia em que o
    dono desmarcar três modelos na tela de opções.
    """
    if modelo:
        chave = f"{variavel}_{modelo}"
        if chave in bloco:
            return bloco[chave]
    return bloco.get(variavel)


def series_por_modelo(dados: dict, modelos: list[str]) -> dict[str, dict[str, list]]:
    """{modelo: {variável: [valores]}}, já alinhado ao eixo `time`."""
    horario = dados.get("hourly") or {}
    saida: dict[str, dict[str, list]] = {}
    for modelo in modelos:
        colunas: dict[str, list] = {}
        for variavel in HORARIAS:
            coluna = _coluna(horario, variavel, modelo)
            if coluna:
                colunas[variavel] = coluna
        # Modelo que não devolveu NADA não entra como dicionário vazio: entrar
        # vazio faria a fusão contar um voto inexistente.
        if colunas:
            saida[modelo] = colunas
    return saida


def eixo_tempo(dados: dict) -> list[float]:
    return [float(t) for t in (dados.get("hourly") or {}).get("time", [])]


def amostras_em(
    dados: dict,
    modelos: list[str],
    variavel: str,
    indice: int,
) -> dict[str, float | None]:
    """O valor de cada modelo numa posição da série — a entrada da fusão."""
    horario = dados.get("hourly") or {}
    saida: dict[str, float | None] = {}
    for modelo in modelos:
        coluna = _coluna(horario, variavel, modelo)
        if not coluna or indice >= len(coluna):
            continue
        saida[modelo] = coluna[indice]
    return saida


def diario_por_modelo(dados: dict, modelos: list[str]) -> list[dict[str, dict]]:
    """A previsão diária, por dia e por modelo — porque ela TAMBÉM vem
    sufixada quando se pede `models=` (verificado em 2026-09-09). Quem tratar
    o bloco `daily` como coluna única encontra as chaves vazias e publica uma
    semana em branco sem erro nenhum.

    Saída: [{modelo: {variável: valor}}], um item por dia.
    """
    bloco = dados.get("daily") or {}
    tempos = bloco.get("time") or []
    saida: list[dict[str, dict]] = []
    for i, t in enumerate(tempos):
        do_dia: dict[str, dict] = {}
        for modelo in modelos:
            colunas: dict = {}
            for variavel in DIARIAS:
                coluna = _coluna(bloco, variavel, modelo)
                if coluna and i < len(coluna):
                    colunas[variavel] = coluna[i]
            if colunas:
                do_dia[modelo] = colunas
        saida.append({"time": float(t), "modelos": do_dia})
    return saida


def amostras_diarias(dia: dict, variavel: str) -> dict[str, float | None]:
    """Os valores de uma variável diária, modelo a modelo — entrada da fusão."""
    return {
        modelo: colunas.get(variavel)
        for modelo, colunas in (dia.get("modelos") or {}).items()
        if colunas.get(variavel) is not None
    }


def indice_de(tempos: list[float], quando: datetime) -> int:
    """Posição da hora que contém `quando`. Serve para 'agora' e para a hora
    de 3 h atrás que o barômetro usa."""
    alvo = quando.timestamp()
    if not tempos:
        return 0
    for i, t in enumerate(tempos):
        if t > alvo:
            return max(i - 1, 0)
    return len(tempos) - 1


def metadados(dados: dict) -> dict:
    """O que a resposta diz sobre o ponto que ela realmente representa.

    Importa mais do que parece: a Open-Meteo devolve o ponto de GRADE, não o
    pedido. Em 2026-09-09 o pedido foi −15,83985/−48,03618 e a resposta veio de
    −15,852372/−48,017, a 1200 m. Metade da divergência entre apps de tempo é
    isto — e por isso vai para os atributos da entidade, não para o log.
    """
    return {
        "latitude_grade": dados.get("latitude"),
        "longitude_grade": dados.get("longitude"),
        "elevacao_modelo": dados.get("elevation"),
        "fuso": dados.get("timezone"),
        "utc_offset_seconds": dados.get("utc_offset_seconds"),
    }
