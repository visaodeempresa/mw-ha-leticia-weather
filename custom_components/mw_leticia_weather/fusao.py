"""Fusão de modelos: como cinco previsões viram um número defensável.

Módulo puro — NÃO importa `homeassistant`. É aqui que mora a única promessa
difícil desta integração ("temperatura confiável"), então é aqui que os testes
apertam.

O PROBLEMA, MEDIDO
──────────────────
Em 2026-09-09, 00:45, no mesmo ponto (Águas Claras, 1200 m): iPhone 20 °C,
Android 22 °C, weather.com 19 °C, met.no 19 °C, Open-Meteo 18,7 °C. Quatro
graus de diferença. Nenhum app está com defeito: são modelos diferentes,
resolvidos em pontos de grade diferentes, com altitudes de modelo diferentes.

A SAÍDA
───────
1. Mediana PONDERADA em vez de média: um modelo que errou feio não arrasta o
   conjunto (a média arrasta; a mediana não).
2. Rejeição de discrepante por MAD (desvio absoluto mediano) — robusto de
   verdade, ao contrário do desvio padrão, que é contaminado pelo próprio
   discrepante que deveria detectar.
3. O DESACORDO É PUBLICADO. p10–p90 do conjunto vira `confiança`. Um número
   sozinho mente por omissão; um número com a largura da discórdia, não.
4. Peso por desempenho recente (skill score), com meia-vida — o modelo que
   vem acertando nesta casa pesa mais. Começa uniforme: sem histórico, nenhum
   modelo tem direito a mais voto que outro.

O QUE **NÃO** SE FUNDE COMO NÚMERO
──────────────────────────────────
Direção do vento é ângulo: a mediana entre 350° e 10° dá 180°, ou seja, vento
do sul quando na verdade é do norte. Vai por média vetorial (`fundir_angulo`).
Código de tempo é rótulo: mediana entre "sol" e "tempestade" não existe. Vai
por voto ponderado (`fundir_categoria`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import pairwise

EPS = 1e-9


@dataclass(frozen=True)
class Fusao:
    """O número, e tudo que foi preciso para ter direito a publicá-lo."""

    valor: float | None
    p10: float | None = None
    p90: float | None = None
    spread: float | None = None
    usados: dict[str, float] = field(default_factory=dict)
    descartados: dict[str, float] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.usados)

    @property
    def unanime(self) -> bool:
        return bool(self.usados) and not self.descartados


def _limpos(amostras: dict[str, float | None]) -> dict[str, float]:
    """Vazio/nulo não é zero. `float("")` explode e `float(None)` também, mas
    um `0` que chega como string vazia em outra camada pintaria 0 °C — a
    guarda mora aqui para nenhum chamador precisar lembrar."""
    saida: dict[str, float] = {}
    for modelo, valor in amostras.items():
        if valor is None or valor == "":
            continue
        try:
            v = float(valor)
        except (TypeError, ValueError):
            continue
        if math.isfinite(v):
            saida[modelo] = v
    return saida


def mediana(valores: list[float]) -> float:
    ordenados = sorted(valores)
    meio = len(ordenados) // 2
    if len(ordenados) % 2:
        return ordenados[meio]
    return (ordenados[meio - 1] + ordenados[meio]) / 2


def mediana_ponderada(pares: list[tuple[float, float]]) -> float:
    """`pares` é [(valor, peso)]. A mediana ponderada é o valor em que o peso
    acumulado cruza a metade — com interpolação quando cai exatamente em cima
    da fronteira, para dois modelos não produzirem degrau."""
    ordenados = sorted(pares, key=lambda p: p[0])
    total = sum(peso for _, peso in ordenados)
    if total <= EPS:
        return mediana([v for v, _ in ordenados])
    alvo = total / 2
    acumulado = 0.0
    for i, (valor, peso) in enumerate(ordenados):
        acumulado += peso
        if acumulado > alvo + EPS:
            return valor
        if abs(acumulado - alvo) <= EPS and i + 1 < len(ordenados):
            return (valor + ordenados[i + 1][0]) / 2
    return ordenados[-1][0]


def percentil(valores: list[float], p: float) -> float:
    """Percentil por interpolação linear. Com 4 modelos, p10 e p90 são quase
    o mínimo e o máximo — e é isso mesmo que se quer: a largura da discórdia."""
    if not valores:
        raise ValueError("sem valores")
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return ordenados[0]
    pos = (len(ordenados) - 1) * p
    baixo = math.floor(pos)
    alto = math.ceil(pos)
    if baixo == alto:
        return ordenados[int(pos)]
    return ordenados[baixo] + (ordenados[alto] - ordenados[baixo]) * (pos - baixo)


# Rejeitar discrepante exige quórum. Com 4 modelos, três valores próximos e um
# afastado, o MAD fica minúsculo e o quarto é expulso — foi exatamente o que
# aconteceu em 2026-09-09: {18,3 · 18,6 · 19,5 · 21,7} descartou o GFS, e o
# GFS era o único que batia com o instrumento do dono (21 °C no barômetro do
# iPhone). Com poucos modelos, "discordante" e "único certo" são
# indistinguíveis, e a mediana ponderada já é robusta sozinha.
QUORUM_PARA_DESCARTE = 5


def fundir(
    amostras: dict[str, float | None],
    pesos: dict[str, float] | None = None,
    *,
    tolerancia_mad: float = 3.0,
) -> Fusao:
    """Funde uma grandeza contínua (temperatura, umidade, pressão, vento…)."""
    limpos = _limpos(amostras)
    if not limpos:
        return Fusao(valor=None)
    if len(limpos) == 1:
        ((modelo, valor),) = limpos.items()
        # Um modelo só: o número sai, mas SEM spread. Publicar spread zero
        # aqui seria anunciar consenso onde não houve consulta.
        return Fusao(valor=valor, usados={modelo: valor})

    valores = list(limpos.values())
    med = mediana(valores)
    desvios = [abs(v - med) for v in valores]
    mad = mediana(desvios)

    usados: dict[str, float] = {}
    descartados: dict[str, float] = {}
    if mad <= EPS or len(limpos) < QUORUM_PARA_DESCARTE:
        # Sem dispersão, ou sem quórum: ninguém é expulso. Ver
        # QUORUM_PARA_DESCARTE — é a diferença entre filtrar ruído e silenciar
        # o modelo que estava certo.
        usados = dict(limpos)
    else:
        for modelo, valor in limpos.items():
            if abs(valor - med) / mad > tolerancia_mad:
                descartados[modelo] = valor
            else:
                usados[modelo] = valor
        if len(usados) < 2:
            # Rejeitar até sobrar um é pior que não rejeitar: volta atrás e
            # deixa a mediana ponderada absorver o estrago.
            usados, descartados = dict(limpos), {}

    p = pesos or {}
    pares = [(v, max(float(p.get(m, 1.0)), EPS)) for m, v in usados.items()]
    valor = mediana_ponderada(pares)
    restantes = list(usados.values())
    p10 = percentil(restantes, 0.10)
    p90 = percentil(restantes, 0.90)
    return Fusao(
        valor=valor,
        p10=p10,
        p90=p90,
        spread=p90 - p10,
        usados=usados,
        descartados=descartados,
    )


def fundir_angulo(
    amostras: dict[str, float | None], pesos: dict[str, float] | None = None
) -> Fusao:
    """Direção do vento, em graus. Média vetorial ponderada: a mediana entre
    350° e 10° daria 180° — vento do sul quando é do norte."""
    limpos = _limpos(amostras)
    if not limpos:
        return Fusao(valor=None)
    p = pesos or {}
    sx = sy = 0.0
    for modelo, graus in limpos.items():
        peso = max(float(p.get(modelo, 1.0)), EPS)
        rad = math.radians(graus)
        sx += peso * math.cos(rad)
        sy += peso * math.sin(rad)
    if abs(sx) < EPS and abs(sy) < EPS:
        # Vetores se anulam: não há direção média honesta.
        return Fusao(valor=None, usados=limpos)
    valor = math.degrees(math.atan2(sy, sx)) % 360
    # A "concordância" circular (R) vira spread em graus: R=1 é acordo total.
    total = sum(max(float(p.get(m, 1.0)), EPS) for m in limpos)
    r = math.hypot(sx, sy) / total
    return Fusao(valor=valor, spread=(1 - r) * 180, usados=limpos)


def fundir_categoria(
    amostras: dict[str, float | int | str | None],
    pesos: dict[str, float] | None = None,
) -> Fusao:
    """Código de tempo: voto ponderado. Empate desempata pelo modelo de maior
    peso, e o `valor` sai como float para caber no mesmo dataclass."""
    votos: dict[str, float] = {}
    usados: dict[str, float] = {}
    p = pesos or {}
    melhor_peso: dict[str, float] = {}
    for modelo, codigo in amostras.items():
        if codigo is None or codigo == "":
            continue
        chave = str(int(float(codigo)))
        peso = max(float(p.get(modelo, 1.0)), EPS)
        votos[chave] = votos.get(chave, 0.0) + peso
        melhor_peso[chave] = max(melhor_peso.get(chave, 0.0), peso)
        usados[modelo] = float(chave)
    if not votos:
        return Fusao(valor=None)
    vencedor = max(votos, key=lambda c: (votos[c], melhor_peso[c]))
    concordancia = votos[vencedor] / sum(votos.values())
    return Fusao(valor=float(vencedor), spread=1 - concordancia, usados=usados)


def interpolar(serie: list[tuple[float, float | None]], quando: float) -> float | None:
    """Valor de uma série horária num instante qualquer.

    Existe porque a Open-Meteo **não aceita multi-modelo em `current`** —
    verificado em 2026-09-09: pedir `current=temperature_2m&models=a,b,c`
    devolve UM valor só, sem sufixo de modelo. O "agora" do conjunto tem de
    ser interpolado das séries horárias, que aceitam.

    `serie` é [(timestamp, valor)] ordenada. Fora das pontas, devolve a ponta
    (extrapolar previsão do tempo é inventar).
    """
    pontos = [(t, v) for t, v in serie if v is not None]
    if not pontos:
        return None
    if quando <= pontos[0][0]:
        return float(pontos[0][1])
    if quando >= pontos[-1][0]:
        return float(pontos[-1][1])
    for (t0, v0), (t1, v1) in pairwise(pontos):
        if t0 <= quando <= t1:
            if t1 == t0:
                return float(v0)
            fatia = (quando - t0) / (t1 - t0)
            return float(v0) + (float(v1) - float(v0)) * fatia
    return None


def atualizar_pesos(
    pesos: dict[str, float],
    erros: dict[str, float],
    *,
    meia_vida: float = 7.0,
    piso: float = 0.25,
) -> dict[str, float]:
    """Skill score móvel: quem vem acertando nesta casa pesa mais.

    `erros` é o erro absoluto de cada modelo no ciclo (contra o consenso, ou
    contra o sensor local quando a calibração está ligada). A memória decai por
    meia-vida em dias — `meia_vida=7` significa que o erro de uma semana atrás
    vale metade.

    `piso` impede que um modelo com má fase seja silenciado para sempre: sem
    ele, o conjunto degenera num provedor só, que é exatamente o problema que
    esta integração existe para resolver.
    """
    if not erros:
        return dict(pesos)
    alfa = 1 - 0.5 ** (1.0 / max(meia_vida, EPS))
    historico = {m: 1.0 / max(w, EPS) - 1.0 for m, w in pesos.items()}
    for modelo, erro in erros.items():
        try:
            e = abs(float(erro))
        except (TypeError, ValueError):
            continue
        anterior = historico.get(modelo, e)
        historico[modelo] = anterior + alfa * (e - anterior)
    if not historico:
        return dict(pesos)
    brutos = {m: 1.0 / (1.0 + max(e, 0.0)) for m, e in historico.items()}
    maior = max(brutos.values()) or 1.0
    normalizados = {m: max(v / maior, piso) for m, v in brutos.items()}
    total = sum(normalizados.values()) or 1.0
    n = len(normalizados)
    # Média 1.0 por modelo: peso é relativo, e assim `pesos.get(m, 1.0)` de um
    # modelo novo entra no mesmo patamar dos veteranos.
    return {m: v * n / total for m, v in normalizados.items()}
