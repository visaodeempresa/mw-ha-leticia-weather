"""Frases prontas em pt-BR para a Letícia falar.

Módulo puro — NÃO importa `homeassistant`.

POR QUE A FALA É MONTADA AQUI, E NÃO NO PROMPT
──────────────────────────────────────────────
Duas razões, as duas medidas em custo:

1. O pipeline da casa está com `prefer_local_intents: true`. Frase que casa com
   `custom_sentences` **nunca chega ao LLM** — resposta instantânea e token
   zero. Para isso, a resposta precisa existir pronta, e o `intent_script` só
   lê um atributo.

2. Há uma armadilha registrada nos dois repos que já fizeram isso nesta casa:
   **`speech` não enxerga `response_variable` de `action`**. O contorno usual é
   um helper `input_text` de relay. Aqui não precisa: as frases saem prontas
   como ATRIBUTO do sensor, e o `intent_script` faz
   `{{ state_attr('sensor.x','fala_hoje') }}`.

REGRAS DE VOZ (as do prompt da Letícia, obedecidas aqui)
────────────────────────────────────────────────────────
- 1 a 3 frases, texto puro: sem lista, sem markdown, sem emoji.
- Resposta de tarefa TERMINA EM PONTO. Nada de interrogação no fim: o "?" final
  é o que reabre o microfone do Voice PE, e clima é resposta, não convite.
- Nunca inventar: sem dado, a frase diz que não sabe.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from . import codigos

DIAS = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


def _n(valor: float | None, casas: int = 0) -> str | None:
    """Número em pt-BR, com vírgula decimal e sem casa inútil."""
    if valor is None:
        return None
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    if casas == 0:
        return str(round(v))
    return f"{v:.{casas}f}".replace(".", ",")


def _graus(valor: float | None) -> str | None:
    n = _n(valor)
    if n is None:
        return None
    return "um grau" if n == "1" else f"{n} graus"


def _dia_nome(quando: date, hoje: date) -> str:
    delta = (quando - hoje).days
    if delta == 0:
        return "hoje"
    if delta == 1:
        return "amanhã"
    if delta == 2:
        return "depois de amanhã"
    if 3 <= delta <= 6:
        return f"{DIAS[quando.weekday()]}"
    return quando.strftime("%d/%m")


def agora(
    *,
    lugar: str,
    temperatura: float | None,
    codigo: int | None = None,
    umidade: float | None = None,
    sensacao: float | None = None,
    spread: float | None = None,
) -> str:
    """A resposta de «qual a temperatura» / «como está o tempo»."""
    t = _graus(temperatura)
    if t is None:
        return f"Não estou com a temperatura de {lugar} agora."
    frase = f"Agora {t} em {lugar}"
    if codigo is not None:
        frase += f", {codigos.texto(codigo)}"
    frase += "."
    segunda: list[str] = []
    if (
        sensacao is not None
        and temperatura is not None
        and abs(float(sensacao) - float(temperatura)) >= 2
    ):
        segunda.append(f"a sensação é de {_graus(sensacao)}")
    if umidade is not None:
        segunda.append(f"a umidade está em {_n(umidade)} por cento")
    if segunda:
        junta = " e ".join(segunda) if len(segunda) == 2 else segunda[0]
        frase += " " + junta[0].upper() + junta[1:] + "."
    return frase + confianca(spread)


def confianca(spread: float | None, *, limite: float = 2.0) -> str:
    """A frase de honestidade. Quando os modelos discordam muito, dizer isso
    vale mais que fingir uma precisão que não existe."""
    if spread is None:
        return ""
    try:
        s = float(spread)
    except (TypeError, ValueError):
        return ""
    if s < limite:
        return ""
    return (
        f" Os modelos discordam em cerca de {_n(s, 1)} graus hoje,"
        " então leve com folga."
    )


def dia(
    *,
    quando: date,
    hoje: date,
    minima: float | None,
    maxima: float | None,
    codigo: int | None = None,
    chuva_probabilidade: float | None = None,
    umidade_min: float | None = None,
    rotulo: str | None = None,
) -> str:
    """Uma frase sobre um dia. É o tijolo de «amanhã», «fim de semana» e
    «próximos dias».

    `rotulo` força o nome do dia. Existe por causa do domingo: perguntar pelo
    fim de semana num domingo aponta para daqui a 6 e 7 dias, e aí o cálculo
    por diferença cairia em «20/09» em vez de «domingo».
    """
    nome = rotulo or _dia_nome(quando, hoje)
    if maxima is None and minima is None:
        return f"Não tenho a previsão de {nome}."
    faixa = ""
    if maxima is not None and minima is not None:
        faixa = f" entre {_n(minima)} e {_graus(maxima)}"
    elif maxima is not None:
        faixa = f" com máxima de {_graus(maxima)}"
    else:
        faixa = f" com mínima de {_graus(minima)}"
    ceu = f", {codigos.texto(codigo)}" if codigo is not None else ""
    chuva = ""
    if chuva_probabilidade is not None and float(chuva_probabilidade) >= 40:
        chuva = f", {_n(chuva_probabilidade)} por cento de chance de chuva"
    seco = ""
    if umidade_min is not None and float(umidade_min) <= 30:
        seco = f", e o ar bem seco, {_n(umidade_min)} por cento"
    return f"{nome.capitalize()}{faixa}{ceu}{chuva}{seco}."


def proximos(dias: list[dict], hoje: date, quantos: int = 3) -> str:
    """Resumo de N dias em no máximo três frases — o limite de voz da casa."""
    escolhidos = [d for d in dias if d.get("data") and d["data"] >= hoje][
        : max(1, quantos)
    ]
    if not escolhidos:
        return "Não tenho a previsão dos próximos dias agora."
    frases = [
        dia(
            quando=d["data"],
            hoje=hoje,
            minima=d.get("minima"),
            maxima=d.get("maxima"),
            codigo=d.get("codigo"),
            chuva_probabilidade=d.get("chuva_probabilidade"),
        )
        for d in escolhidos[:3]
    ]
    return " ".join(frases)


def fim_de_semana(dias: list[dict], hoje: date) -> str:
    """Sábado e domingo — o próximo par, mesmo que hoje já seja sábado.

    Domingo à noite a pergunta passa a valer para o fim de semana SEGUINTE:
    responder «sábado foi ontem» seria tecnicamente correto e inútil.
    """
    sabado = hoje + timedelta(days=(5 - hoje.weekday()) % 7)
    if hoje.weekday() == 6:  # domingo: o par que interessa é o próximo
        sabado = hoje + timedelta(days=6)
    domingo = sabado + timedelta(days=1)
    por_data = {d["data"]: d for d in dias if d.get("data")}
    partes = []
    for alvo, rotulo in ((sabado, "sábado"), (domingo, "domingo")):
        d = por_data.get(alvo)
        if not d:
            continue
        partes.append(
            dia(
                quando=alvo,
                hoje=hoje,
                minima=d.get("minima"),
                maxima=d.get("maxima"),
                codigo=d.get("codigo"),
                chuva_probabilidade=d.get("chuva_probabilidade"),
                rotulo=rotulo if (alvo - hoje).days > 2 else None,
            )
        )
    if not partes:
        return "Ainda não alcanço o fim de semana na previsão."
    return " ".join(partes)


def alertas(lista: list[dict], lugar: str) -> str:
    """Os avisos, do mais grave para o mais brando, em até três frases.

    Alerta derivado é sempre anunciado como cálculo nosso — nunca como se
    fosse boletim de órgão oficial.
    """
    if not lista:
        return f"Nenhum alerta de tempo para {lugar} agora."
    primeiro = lista[0]
    fonte = primeiro.get("fonte") or "fonte não identificada"
    marca = (
        ""
        if primeiro.get("oficial")
        else " Esse é um cálculo meu a partir da previsão, não um boletim oficial."
    )
    titulo = str(primeiro.get("titulo", "aviso")).lower()
    nivel = str(primeiro.get("severidade_rotulo", "")).lower()
    frase = f"{titulo[0].upper()}{titulo[1:]} em {lugar}"
    if nivel:
        frase += f", nível {nivel}"
    frase += f". {primeiro.get('descricao', '')}".rstrip()
    if len(lista) > 1:
        outros = len(lista) - 1
        frase += f" E há mais {outros} aviso{'s' if outros > 1 else ''} em vigor."
    if primeiro.get("oficial"):
        frase += f" Fonte: {fonte}."
    return frase + marca


def sol(nascer: datetime | None, por: datetime | None) -> str:
    if not nascer and not por:
        return "Não tenho os horários do sol agora."
    partes = []
    if nascer:
        partes.append(f"o sol nasce às {nascer.strftime('%H:%M').replace(':', 'h')}")
    if por:
        partes.append(f"se põe às {por.strftime('%H:%M').replace(':', 'h')}")
    return "Hoje " + " e ".join(partes) + "."
