"""A fusão é a única promessa difícil desta integração. Aqui ela é apertada."""

from mww import fusao


def test_mediana_ponderada_com_peso_igual_e_a_mediana():
    pares = [(18.3, 1.0), (18.6, 1.0), (19.5, 1.0), (21.7, 1.0)]
    assert fusao.mediana_ponderada(pares) == 19.05


def test_peso_maior_puxa_a_mediana_para_o_modelo_que_acerta_mais():
    # O mesmo conjunto, mas com o GFS pesando o dobro: o número anda para cima.
    leve = fusao.mediana_ponderada([(18.3, 1), (18.6, 1), (19.5, 1), (21.7, 1)])
    pesado = fusao.mediana_ponderada([(18.3, 1), (18.6, 1), (19.5, 1), (21.7, 4)])
    assert pesado > leve


def test_o_caso_real_de_2026_09_09():
    """Os quatro modelos do dia em que o dono pediu esta integração."""
    r = fusao.fundir(
        {
            "ecmwf_ifs025": 18.3,
            "gfs_seamless": 21.7,
            "icon_seamless": 19.5,
            "metno_seamless": 18.6,
        }
    )
    assert r.valor == 19.05
    assert r.n == 4
    # NENHUM descartado: com quatro modelos não há quórum para expulsar, e o
    # GFS (o mais afastado) era justamente o que batia com o instrumento do
    # dono, que marcava 21 °C.
    assert r.descartados == {}
    assert round(r.spread, 1) == 2.6


def test_discrepante_so_cai_com_quorum():
    poucos = fusao.fundir({"a": 19.0, "b": 19.2, "c": 18.9, "d": 45.0})
    assert poucos.descartados == {}
    muitos = fusao.fundir(
        {"a": 19.0, "b": 19.2, "c": 18.9, "d": 19.1, "e": 19.3, "f": 45.0}
    )
    assert muitos.descartados == {"f": 45.0}
    assert 18.9 <= muitos.valor <= 19.3


def test_rejeicao_nunca_deixa_menos_de_dois():
    r = fusao.fundir({"a": 1.0, "b": 50.0, "c": 100.0, "d": 150.0, "e": 200.0})
    assert r.n >= 2


def test_um_modelo_so_nao_publica_spread():
    """Spread zero anunciaria consenso onde não houve consulta."""
    r = fusao.fundir({"unico": 20.0})
    assert r.valor == 20.0
    assert r.spread is None


def test_vazio_nao_e_zero():
    r = fusao.fundir({"a": None, "b": "", "c": "não é número"})
    assert r.valor is None
    assert fusao.fundir({"a": 20.0, "b": None}).valor == 20.0


def test_angulo_nao_se_funde_como_numero():
    """Mediana entre 350° e 10° daria 180°: vento do sul quando é do norte."""
    r = fusao.fundir_angulo({"a": 350.0, "b": 10.0})
    assert r.valor is not None
    assert min(r.valor, 360 - r.valor) < 1.0


def test_angulo_oposto_nao_inventa_direcao():
    r = fusao.fundir_angulo({"a": 0.0, "b": 180.0})
    assert r.valor is None


def test_categoria_e_voto_ponderado():
    r = fusao.fundir_categoria({"a": 0, "b": 3, "c": 3})
    assert r.valor == 3.0
    empate = fusao.fundir_categoria({"a": 0, "b": 3}, {"a": 5.0, "b": 1.0})
    assert empate.valor == 0.0


def test_interpolar_e_o_agora_do_conjunto():
    serie = [(0.0, 18.0), (3600.0, 20.0)]
    assert fusao.interpolar(serie, 1800.0) == 19.0
    # Fora das pontas devolve a ponta: extrapolar previsão é inventar.
    assert fusao.interpolar(serie, -100.0) == 18.0
    assert fusao.interpolar(serie, 99999.0) == 20.0
    assert fusao.interpolar([], 10.0) is None


def test_pesos_aprendem_mas_ninguem_e_silenciado():
    pesos = {}
    for _ in range(60):
        pesos = fusao.atualizar_pesos(pesos, {"bom": 0.1, "ruim": 5.0})
    assert pesos["bom"] > pesos["ruim"]
    assert pesos["ruim"] >= 0.24  # o piso impede degenerar num provedor só
    assert abs(sum(pesos.values()) / len(pesos) - 1.0) < 0.01


# ── o recuo, que já esteve invertido ─────────────────────────────────────────
from mww import recuo  # noqa: E402


def test_o_recuo_nunca_acelera():
    """A primeira versão dava 120 s onde o normal eram 900 — um acelerador
    disfarçado de backoff. Este teste existe para isso não voltar."""
    base = 900.0
    assert recuo.atraso(base, 1) >= base
    for n in range(1, 12):
        assert recuo.atraso(base, n) >= base


def test_o_recuo_dobra_e_para_no_teto():
    base = 900.0
    assert recuo.atraso(base, 1) == 900.0
    assert recuo.atraso(base, 2) == 1800.0
    assert recuo.atraso(base, 3) == 3600.0
    assert recuo.atraso(base, 9) == recuo.atraso(base, 30) == 7200.0


def test_o_recuo_aguenta_entrada_estranha():
    assert recuo.atraso(0, 0) >= 1.0
    assert recuo.atraso(900, -5) == 900.0
