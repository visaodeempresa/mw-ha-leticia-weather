"""Alertas: os oficiais, normalizados, e os derivados, calculados aqui.

Módulo puro — NÃO importa `homeassistant`.

POR QUE DOIS TIPOS
──────────────────
Alerta OFICIAL tem autoridade, texto e instrução de órgão público — mas só
existe onde o órgão existe. O INMET cobre o Brasil, o NWS os EUA, o MeteoAlarm
a Europa. Perguntar "tem alerta em Kigali?" para qualquer um deles devolve
silêncio, e silêncio não é "não tem".

Alerta DERIVADO é calculado da própria previsão e funciona em qualquer ponto
do planeta. Não tem autoridade — e por isso é rotulado como derivado na tela e
na fala, sempre. Os limiares NÃO foram inventados: os de umidade e chuva são
os do próprio INMET (é o que o dono vê no celular), e os demais seguem as
faixas usuais de aviso.

SEVERIDADE
──────────
Três degraus, com os nomes que o INMET usa e que já aparecem no celular do
dono: `potencial` (amarelo), `perigo` (laranja), `grande_perigo` (vermelho).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

SEVERIDADES = ("potencial", "perigo", "grande_perigo")
SEVERIDADE_ROTULO = {
    "potencial": "Perigo potencial",
    "perigo": "Perigo",
    "grande_perigo": "Grande perigo",
}
SEVERIDADE_COR = {
    "potencial": "#ffa600",
    "perigo": "#f57c00",
    "grande_perigo": "#db4437",
}
# Mapa para o vocabulário CAP, que é o que NWS e MeteoAlarm falam.
CAP_PARA_SEVERIDADE = {
    "minor": "potencial",
    "moderate": "perigo",
    "severe": "grande_perigo",
    "extreme": "grande_perigo",
}


@dataclass(frozen=True)
class Alerta:
    tipo: str
    severidade: str
    titulo: str
    descricao: str
    fonte: str
    oficial: bool
    inicio: datetime | None = None
    fim: datetime | None = None
    instrucoes: str | None = None
    valores: dict[str, float] = field(default_factory=dict)

    @property
    def rotulo_severidade(self) -> str:
        return SEVERIDADE_ROTULO.get(self.severidade, self.severidade)

    @property
    def cor(self) -> str:
        return SEVERIDADE_COR.get(self.severidade, "#ffa600")

    def como_dicionario(self) -> dict:
        return {
            "tipo": self.tipo,
            "severidade": self.severidade,
            "severidade_rotulo": self.rotulo_severidade,
            "cor": self.cor,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "fonte": self.fonte,
            "oficial": self.oficial,
            "inicio": self.inicio.isoformat() if self.inicio else None,
            "fim": self.fim.isoformat() if self.fim else None,
            "instrucoes": self.instrucoes,
            "valores": dict(self.valores),
        }


# ── limiares dos alertas derivados ───────────────────────────────────────────
# Umidade e chuva: os do INMET (portal de avisos). Os demais: faixas usuais.
LIMIARES = {
    # umidade relativa MÍNIMA do dia, em %: quanto MENOR, pior
    "clima_seco": {"potencial": 30.0, "perigo": 20.0, "grande_perigo": 12.0},
    # sensação térmica máxima, em °C
    "calor": {"potencial": 32.0, "perigo": 38.0, "grande_perigo": 41.0},
    # temperatura mínima, em °C: quanto MENOR, pior
    "frio": {"potencial": 10.0, "perigo": 5.0, "grande_perigo": 0.0},
    # chuva em mm/h
    "chuva_forte": {"potencial": 20.0, "perigo": 30.0, "grande_perigo": 60.0},
    # rajada em km/h
    "vento_forte": {"potencial": 40.0, "perigo": 60.0, "grande_perigo": 100.0},
    # CAPE em J/kg (energia disponível para convecção)
    "tempestade": {"potencial": 1000.0, "perigo": 2500.0, "grande_perigo": 4000.0},
    # índice UV
    "uv": {"potencial": 8.0, "perigo": 11.0, "grande_perigo": 13.0},
}

_INVERTIDOS = {"clima_seco", "frio"}  # aqui, MENOR é pior

TEXTOS = {
    "clima_seco": (
        "Umidade do ar baixa",
        "Umidade relativa mínima de {valor:.0f} por cento.",
        "Beba água, evite exercício ao ar livre nas horas mais secas e "
        "umidifique o ambiente.",
    ),
    "calor": (
        "Calor",
        "Sensação térmica chegando a {valor:.0f} °C.",
        "Hidrate-se, evite sol entre 10h e 16h e cuide de crianças e idosos.",
    ),
    "frio": (
        "Frio",
        "Temperatura mínima de {valor:.0f} °C.",
        "Agasalhe-se, cuidado com plantas sensíveis e com quem dorme na rua.",
    ),
    "chuva_forte": (
        "Chuva forte",
        "Até {valor:.0f} milímetros em uma hora.",
        "Evite áreas de alagamento e não atravesse ruas com água corrente.",
    ),
    "vento_forte": (
        "Vento forte",
        "Rajadas de até {valor:.0f} quilômetros por hora.",
        "Recolha objetos soltos, evite áreas arborizadas e desligue "
        "equipamentos sensíveis.",
    ),
    "tempestade": (
        "Risco de tempestade",
        "Atmosfera carregada, com energia convectiva de {valor:.0f} joules por quilo.",
        "Fique em local abrigado, evite áreas abertas e desligue aparelhos da tomada.",
    ),
    "uv": (
        "Radiação ultravioleta alta",
        "Índice UV chegando a {valor:.0f}.",
        "Use protetor solar, chapéu e óculos; procure sombra no meio do dia.",
    ),
}


def _severidade(tipo: str, valor: float) -> str | None:
    limiares = LIMIARES.get(tipo)
    if limiares is None or valor is None:
        return None
    invertido = tipo in _INVERTIDOS
    escolhida = None
    for nivel in SEVERIDADES:  # do mais brando ao mais grave
        limite = limiares[nivel]
        if (valor <= limite) if invertido else (valor >= limite):
            escolhida = nivel
    return escolhida


def derivar(
    medidas: dict[str, float | None],
    *,
    inicio: datetime | None = None,
    fim: datetime | None = None,
) -> list[Alerta]:
    """Calcula os alertas derivados a partir das medidas do dia.

    `medidas` aceita as chaves: umidade_min, sensacao_max, temperatura_min,
    chuva_max_h, rajada_max, cape_max, uv_max. Chave ausente simplesmente não
    gera alerta — nunca gera alerta de valor zero (regra 120: variável sem
    dado não vira nada).
    """
    de_para = {
        "clima_seco": "umidade_min",
        "calor": "sensacao_max",
        "frio": "temperatura_min",
        "chuva_forte": "chuva_max_h",
        "vento_forte": "rajada_max",
        "tempestade": "cape_max",
        "uv": "uv_max",
    }
    saida: list[Alerta] = []
    for tipo, chave in de_para.items():
        bruto = medidas.get(chave)
        if bruto is None or bruto == "":
            continue
        try:
            valor = float(bruto)
        except (TypeError, ValueError):
            continue
        nivel = _severidade(tipo, valor)
        if nivel is None:
            continue
        titulo, descricao, instrucoes = TEXTOS[tipo]
        saida.append(
            Alerta(
                tipo=tipo,
                severidade=nivel,
                titulo=titulo,
                descricao=descricao.format(valor=valor),
                fonte="MW Letícia Weather (derivado da previsão)",
                oficial=False,
                inicio=inicio,
                fim=fim,
                instrucoes=instrucoes,
                valores={chave: valor},
            )
        )
    return ordenar(saida)


_ORDEM = {nivel: i for i, nivel in enumerate(reversed(SEVERIDADES))}


def ordenar(alertas: list[Alerta]) -> list[Alerta]:
    """Mais grave primeiro; empate, oficial antes de derivado. É a ordem em que
    a tela desenha e a Letícia fala."""
    return sorted(
        alertas,
        key=lambda a: (_ORDEM.get(a.severidade, 99), 0 if a.oficial else 1, a.titulo),
    )


def deduplicar(alertas: list[Alerta]) -> list[Alerta]:
    """Quando o órgão oficial já avisou de chuva forte, o alerta derivado de
    chuva forte vira ruído: some. O oficial vence sempre, mesmo se for menos
    grave — quem manda na região é ele."""
    oficiais = {a.tipo for a in alertas if a.oficial}
    return ordenar([a for a in alertas if a.oficial or a.tipo not in oficiais])
