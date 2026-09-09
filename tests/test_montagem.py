"""Do JSON cru ao retrato publicado, com a resposta REAL de 2026-09-09."""

from datetime import date, datetime, timedelta, timezone

from mww import montagem
from mww.fontes import open_meteo as om

FUSO = timezone(timedelta(hours=-3))


def _retrato(previsao, modelos, ar=None, avisos=None):
    return montagem.montar(
        lugar="Águas Claras",
        latitude=-15.83,
        longitude=-48.03,
        previsao=previsao,
        modelos=modelos,
        agora=datetime(2026, 9, 9, 1, 30, tzinfo=FUSO),
        ar_bruto=ar,
        avisos_oficiais=avisos or [],
    )


def test_o_agora_vem_das_series_horarias(previsao_bruta, modelos):
    """`current` da Open-Meteo COLAPSA com multi-modelo (verificado em
    2026-09-09): o agora do conjunto só existe interpolado do horário."""
    r = _retrato(previsao_bruta, modelos)
    assert r.agora.temperatura is not None
    assert len(r.agora.por_modelo) == 4
    assert r.agora.spread is not None


def test_pressao_publicada_e_a_do_nivel_do_mar(previsao_bruta, modelos):
    """A casa está a 1200 m. A de estação fica por perto de 887 hPa e a de
    nível do mar por perto de 1019 — que é o que o barômetro do dono marcava."""
    r = _retrato(previsao_bruta, modelos)
    assert 990 < r.agora.pressao_msl < 1045
    assert 850 < r.agora.pressao_estacao < 920
    assert r.agora.pressao_msl - r.agora.pressao_estacao > 100


def test_o_diario_tambem_vem_sufixado_por_modelo(previsao_bruta, modelos):
    """Quem tratar `daily` como coluna única publica uma semana em branco sem
    erro nenhum. Este teste é o guarda dessa armadilha."""
    dias = om.diario_por_modelo(previsao_bruta, modelos)
    assert dias
    assert set(om.amostras_diarias(dias[1], "temperature_2m_max")) == set(modelos)


def test_a_janela_horaria_respeita_forecast_days(previsao_bruta):
    """`past_hours` faz a Open-Meteo IGNORAR `forecast_days` e devolver 16 dias.
    A fixture foi gravada já com `past_days=1`."""
    horas = len(om.eixo_tempo(previsao_bruta))
    assert horas <= 24 * 17
    assert horas % 24 == 0


def test_um_modelo_so_cai_na_coluna_sem_sufixo(previsao_bruta):
    """Quando se pede UM modelo, a Open-Meteo devolve a coluna sem sufixo. Se
    o código não tratar, a integração fica vazia no dia em que o dono desmarcar
    três modelos na tela de opções."""
    so_um = {
        "hourly": {"time": [0, 3600], "temperature_2m": [18.0, 19.0]},
        "utc_offset_seconds": -10800,
    }
    assert om.amostras_em(so_um, ["ecmwf_ifs025"], "temperature_2m", 0) == {
        "ecmwf_ifs025": 18.0
    }


def test_previsao_nao_olha_para_tras(previsao_bruta, modelos):
    r = _retrato(previsao_bruta, modelos)
    # `past_days=1` traz ontem no bloco diário — é de propósito, para o
    # barômetro. Mas quem consome como previsão tem de filtrar.
    futuros = [d for d in r.dias if d.data >= date(2026, 9, 9)]
    assert len(futuros) >= 7


def test_pressao_de_tres_horas_atras_existe(previsao_bruta, modelos):
    """É o ponteiro de memória do barômetro e a entrada da tendência."""
    r = _retrato(previsao_bruta, modelos)
    assert r.pressao_3h_atras is not None
    assert abs(r.agora.pressao_msl - r.pressao_3h_atras) < 15


def test_ar_entra_quando_ha_dado(previsao_bruta, modelos, ar_bruto):
    r = _retrato(previsao_bruta, modelos, ar=ar_bruto)
    assert r.ar.get("pm2_5") is not None
    assert r.ar.get("pm2_5_faixa") in ("bom", "atenção", "ruim")


def test_falas_saem_prontas_e_sem_interrogacao(previsao_bruta, modelos):
    """Regra de voz da casa: resposta de tarefa termina em ponto — o `?` final
    é o que reabre o microfone do Voice PE."""
    r = _retrato(previsao_bruta, modelos)
    for chave in ("fala_agora", "fala_hoje", "fala_amanha", "fala_fim_de_semana"):
        texto = r.falas[chave]
        assert texto and not texto.rstrip().endswith("?")
        assert "%" not in texto and "*" not in texto and "#" not in texto


def test_alerta_oficial_desbanca_o_derivado(previsao_bruta, modelos):
    oficial = {
        "tipo": "clima_seco",
        "severidade": "potencial",
        "titulo": "Baixa Umidade",
        "descricao": "aviso do órgão",
        "fonte": "INMET",
        "oficial": True,
        "inicio": None,
        "fim": None,
        "instrucoes": None,
        "id": 123,  # campo extra da fonte: tem de ser descartado sem quebrar
    }
    r = _retrato(previsao_bruta, modelos, avisos=[oficial])
    secos = [a for a in r.alertas if a.tipo == "clima_seco"]
    assert len(secos) == 1
    assert secos[0].oficial is True


def test_condicao_e_do_vocabulario_do_ha(previsao_bruta, modelos):
    validos = {
        "clear-night",
        "cloudy",
        "exceptional",
        "fog",
        "hail",
        "lightning",
        "lightning-rainy",
        "partlycloudy",
        "pouring",
        "rainy",
        "snowy",
        "snowy-rainy",
        "sunny",
        "windy",
        "windy-variant",
    }
    r = _retrato(previsao_bruta, modelos)
    assert r.agora.condicao in validos
    for h in r.horas:
        assert h.condicao in validos
