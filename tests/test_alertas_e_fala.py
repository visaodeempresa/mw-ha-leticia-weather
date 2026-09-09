"""Alertas derivados, avisos do INMET e as frases que a Letícia fala."""

import json
from datetime import date, timedelta
from pathlib import Path

from mww import alertas, codigos, fala
from mww.fontes import avisos_inmet

HOJE = date(2026, 9, 9)


def test_limiares_de_umidade_sao_os_do_inmet():
    assert alertas.LIMIARES["clima_seco"] == {
        "potencial": 30.0,
        "perigo": 20.0,
        "grande_perigo": 12.0,
    }


def test_umidade_menor_e_pior():
    def sev(v):
        return alertas.derivar({"umidade_min": v})[0].severidade

    assert sev(28) == "potencial"
    assert sev(18) == "perigo"
    assert sev(10) == "grande_perigo"
    assert alertas.derivar({"umidade_min": 45}) == []


def test_variavel_ausente_nao_vira_alerta_de_zero():
    """Regra 120: variável sem dado não vira nada."""
    assert alertas.derivar({}) == []
    assert alertas.derivar({"umidade_min": None, "rajada_max": ""}) == []


def test_ordem_e_do_mais_grave_para_o_mais_brando():
    lista = alertas.derivar({"umidade_min": 10, "sensacao_max": 33, "rajada_max": 45})
    assert lista[0].severidade == "grande_perigo"
    assert lista[-1].severidade == "potencial"


def test_ponto_no_poligono_com_o_desenho_do_inmet():
    quadrado = [[-50.0, -20.0], [-46.0, -20.0], [-46.0, -14.0], [-50.0, -14.0]]
    assert avisos_inmet.ponto_no_poligono(-16.0, -48.0, quadrado) is True
    assert avisos_inmet.ponto_no_poligono(-16.0, -40.0, quadrado) is False


def test_poligono_chega_como_string_json():
    """O INMET manda o GeoJSON como TEXTO dentro do JSON."""
    bruto = json.dumps(
        {
            "type": "Polygon",
            "coordinates": [[[-50, -20], [-46, -20], [-46, -14], [-50, -14]]],
        }
    )
    aneis = avisos_inmet._aneis(bruto)
    assert len(aneis) == 1 and len(aneis[0]) == 4


def test_riscos_e_instrucoes_podem_vir_como_lista():
    """Medido em 2026-09-09: o mesmo endpoint devolve ora string, ora lista."""
    assert avisos_inmet._texto(["a", "b"]) == "a b"
    assert avisos_inmet._texto("a") == "a"
    assert avisos_inmet._texto(None) == ""


def test_hora_do_inmet_e_local_apesar_do_z():
    quando = avisos_inmet._quando("2026-09-09T00:00:00.000Z", "23:59")
    assert quando.tzinfo is None  # ingênuo: quem localiza é o HA
    assert (quando.hour, quando.minute) == (23, 59)


def test_fala_sem_dado_diz_que_nao_sabe():
    assert "Não estou" in fala.agora(lugar="X", temperatura=None)
    assert "Não tenho" in fala.dia(quando=HOJE, hoje=HOJE, minima=None, maxima=None)


def test_fala_avisa_quando_os_modelos_discordam():
    with_spread = fala.agora(lugar="X", temperatura=19.0, spread=3.4)
    sem = fala.agora(lugar="X", temperatura=19.0, spread=0.4)
    assert "discordam" in with_spread
    assert "discordam" not in sem


def test_fim_de_semana_no_domingo_aponta_para_o_proximo():
    domingo = date(2026, 9, 13)
    dias = [
        {"data": domingo + timedelta(days=i), "minima": 18, "maxima": 28, "codigo": 0}
        for i in range(15)
    ]
    frase = fala.fim_de_semana(dias, domingo)
    assert "Sábado" in frase and "Domingo" in frase


def test_alerta_derivado_se_anuncia_como_derivado():
    lista = [a.como_dicionario() for a in alertas.derivar({"umidade_min": 18})]
    frase = fala.alertas(lista, "Águas Claras")
    assert "cálculo meu" in frase


def test_sol_nao_vira_lua_de_dia_nem_sol_de_noite():
    assert codigos.condicao(0, dia=True) == "sunny"
    assert codigos.condicao(0, dia=False) == "clear-night"
    assert codigos.condicao(3, dia=False) == "cloudy"


def test_codigo_desconhecido_nao_quebra():
    assert codigos.condicao(999) == "exceptional"
    assert codigos.texto(None) == "condição não catalogada"


def test_fixtures_existem():
    raiz = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    assert (raiz / "open_meteo_aguas_claras.json").exists()
