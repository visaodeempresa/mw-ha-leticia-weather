# CHANGELOG — MW Letícia Weather

## 0.1.0 — 2026-09-09

Primeira versão. Nasceu de cinco aplicativos discordando em 4 °C sobre o mesmo
ponto, no mesmo minuto.

- **Fusão de modelos** (`fusao.py`): mediana ponderada, rejeição de discrepante
  por MAD **com quórum de 5 modelos**, percentis p10/p90 publicados como
  confiança, média vetorial para direção de vento e voto ponderado para código
  de tempo.
- **Quórum importa.** Com os quatro modelos do dia (18,3 · 18,6 · 19,5 · 21,7)
  o MAD expulsava o GFS — que era justamente o que batia com o instrumento do
  dono (21 °C no barômetro do iPhone). Com poucos modelos, «discordante» e
  «único certo» são indistinguíveis.
- **Open-Meteo multi-modelo numa chamada só.** Verificado: `models=` funciona em
  `hourly` **e** em `daily` (colunas sufixadas), mas **colapsa em `current`** —
  o agora do conjunto é interpolado da série horária.
- **`past_days` e não `past_hours`.** Com `past_hours`, a Open-Meteo ignora
  `forecast_days` e devolve 16 dias inteiros na série horária (390 linhas em vez
  de 96).
- **Alertas oficiais do INMET por polígono ou código IBGE.** O GeoJSON vem como
  **string** dentro do JSON; `riscos` e `instrucoes` vêm ora string, ora lista;
  e a hora é **local apesar do sufixo Z**.
- **Alertas derivados** com os limiares do próprio INMET para umidade e chuva,
  cobrindo qualquer ponto do planeta — sempre rotulados como derivados.
- **Frases prontas em pt-BR** nos atributos do `sensor.*_previsao`, para o
  assistente responder sem passar pelo LLM.
- **Pressão publicada em MSL**, com a de estação como atributo (regra global
  190).
- 38 testes, todos sobre resposta real gravada — nenhum depende de internet.
