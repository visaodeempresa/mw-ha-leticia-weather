# Inspeção de IA — entrega de 2026-09-09 (clima MW)

**Escopo:** `mw-ha-leticia-weather`, `mw-ha-leticia-weather-card`,
`mw-ha-barometer-card` e o que voltou para `IA/`.
**Método:** leitura e medição. Nada foi alterado, nada da Letícia foi tocado, o
HA não foi reiniciado.
**Portão:** `cd IA && make check` → **exit 0** (29 blocos embutidos ✓, 8 testes
de mesa de lib ✓, links relativos ✓, frontmatter de skill ✓).

## Calibração na régua (regra 140)

Rodado antes de julgar, em `mw-ha-scene-button-card` (aceito pelo dono):

| limite candidato | o que a régua mostra | veredito do limite |
|---|---|---|
| todo commit assinado | `b9c0207 N` — bump `chore: 🔖 v0.4.0` sem assinatura | **descartado**: o bump do `auto-release` nunca assina. O `N` em `b25b555` do clima **não** é achado |
| todo repo tem `CHANGELOG.md` | ausente na régua | **descartado** |
| todo repo tem `.claude/skills/` local | ausente na régua (skill só canônica) | **descartado** |
| README ≤ ~6,5 KB | 6.364 B | **mantido** — os três novos: 4.866 / 4.603 / 5.202 B |
| tarefa típica ≤ 40 KB | 32,4 KB (18.586 obrigatório + 7.462 skill + 6.364 README) | **mantido** |
| `.claude/` fora do git | a régua versiona **0** arquivo em `.claude/` | **mantido** |
| embed registrado no `check-embeds.sh` | 4 blocos, todos ✓ | **mantido** |

## Achados

### BLOQUEIA — a tira de pressão do card de tempo ignora a escala canônica, e a lib declara um consumidor que não consome

- **onde:** `PROJECTS/mw-ha-leticia-weather-card/dist/mw-leticia-weather-card.js:395`
  (`pressao: num(a.pressure)`) e `:639` (badge `mdi:gauge` + `${fmt(d.pressao,1)} hPa`)
  · `IA/lib/mw-pressure-scale/README.md` (seção «Por que ela nasceu»)
- **medida:** 0 marcadores `>>> mw-pressure-scale` no `dist` do card de tempo —
  o único bloco embutido lá é `mw-climate-scale v1`. Consumidores reais da lib:
  **1** (só o barômetro), contra os **2** que o README afirma. A regra 190 lista
  «mostrador, gauge, **badge**, **tira**» e impõe a obrigação 2 («quem não
  converter, declara»): o card imprime o `pressure` cru da entidade, sem cor,
  sem `mwPressureToMsl` e sem `mwPressureParecePressaoDeEstacao`. Numa entidade
  `weather.*` de terceiro que publique pressão de estação, a tira mostra 887 hPa
  em silêncio — exatamente o defeito que a regra nasceu para proibir.
- **conserto:** embutir o bloco em `dist/mw-leticia-weather-card.js` e acrescentar
  o consumidor na linha 28 de `IA/tools/check-embeds.sh`:
  `"mw-pressure-scale v1:$IA_ROOT/lib/mw-pressure-scale/mw-pressure-scale.js:$PROJECTS/mw-ha-barometer-card/dist/mw-barometer-card.js:$PROJECTS/mw-ha-leticia-weather-card/dist/mw-leticia-weather-card.js"`
  — depois `IA/tools/check-embeds.sh`.
  Se a decisão for **não** pintar a tira, então corrigir
  `IA/lib/mw-pressure-scale/README.md` para dizer 1 consumidor e registrar em
  ADR por que a tira fica fora da regra 190.

### IMPORTANTE — 6 symlinks absolutos do SSD do dono commitados em 3 repositórios públicos

- **onde:** `.claude/skills/mw-clima/SKILL.md` nos três repos ·
  `.claude/agents/inspetor-de-{design,ia,integracao}.md` em `mw-ha-leticia-weather`
- **medida:** `git ls-files -s .claude` devolve mode **120000** em 6 entradas,
  todas apontando para `/Volumes/SSD-T1-01/CLAUDE-SSD/IA/…`. Os três repos são
  **PUBLIC** (`gh repo view`). A régua versiona 0 arquivo em `.claude/`, e o
  mecanismo oficial (`IA/tools/sync-skills.sh`, regra 10) publica **fora** do
  repo, em `~/.claude/skills`. Quem clonar recebe 6 links quebrados e o mapa do
  harness privado.
- **conserto:** nos três repos —
  `git rm --cached -r .claude && printf '.claude/\n' >> .gitignore`
  (o symlink continua no disco e continua funcionando para o agente).

### IMPORTANTE — o fato do 887 hPa tem 5 donos em `IA/`, um deles verbatim

- **onde:** `IA/rules/global/190-cores-de-pressao.md` e
  `IA/lib/mw-pressure-scale/README.md`
- **medida:** o fato aparece em 5 markdowns de `IA/` + 3 nos repos. Os dois
  citados repetem **a mesma frase palavra por palavra** («a janela de
  plausibilidade sozinha não pega, porque 887 hPa é um valor MSL legítimo (olho
  de tufão)») e a mesma tabela de 4 fontes. Na régua, o fato equivalente
  (`scene.*` nunca vale `on`) tem **2** donos.
- **conserto:** dono único = `IA/knowledge/ha-pressao-msl-vs-estacao.md`. A regra
  190 fica com a tabela de cores e as 3 obrigações e **linka**; o
  `lib/mw-pressure-scale/README.md` troca a seção «A armadilha que justifica
  metade do código» por uma linha + link.

### POLIMENTO — `docs/RESUMO-2026-09-09-clima-mw.md` é órfão e não versionado

- **onde:** `PROJECTS/mw-ha-leticia-weather/docs/RESUMO-2026-09-09-clima-mw.md`
- **medida:** 5.871 B · `git status` = `?? docs/` · 0 link de entrada em `IA/`
  ou no README do repo.
- **conserto:** commitar e citar no `README.md`, ou apagar.

### POLIMENTO — o portão de links não enxerga as skills de repositório

- **onde:** `IA/tools/check-links.sh` (percorre só `$IA_ROOT`)
- **medida:** 2 links relativos (`../mw-clima/SKILL.md`) nas skills de
  `mw-ha-barometer-card` e `mw-ha-leticia-weather-card` hoje só resolvem por
  causa do symlink do achado anterior. Corrigido aquele, quebram e **nenhum**
  comando do `make check` reclama.
- **conserto:** trocar por caminho absoluto/menção textual, ou estender o
  `find` do `check-links.sh` a `<repo>/.claude/skills`.

### POLIMENTO — os dois repos de card estão com o checkout local em `main`

- **medida:** `git branch` = `main` nos dois; a régua fica em `develop`. No
  GitHub está tudo certo: default = `develop` nos três, e
  `origin/main...origin/develop` = `0 0`. Risco só de commit futuro cair direto
  em `main`.
- **conserto:** `git checkout develop` nos dois.

## O que passou, com número

| eixo | evidência |
|---|---|
| Reuso — cliente WS | `tools/criar_clima_3_0.py:17-18` importa `HAClient` de `ha-dashboards/scripts` em vez de escrever o 4º cliente |
| Reuso — fórmula MSL | não há reimplementação em Python: `fontes/open_meteo.py:36` pede `pressure_msl` à fonte |
| Reuso — devops | `publicar-no-ha.py` difere do da régua em **3 linhas** (as constantes) — cópia consciente do template (ADR 0003) |
| Reuso — embeds | `mw-pressure-scale v1` e `mw-zambretti v1` registrados e byte a byte iguais |
| Custo | tarefa típica de clima = 18.586 (obrigatório) + 6.684 (`SKILL.md`) = **25,3 KB**, abaixo dos 32,4 KB da régua. A skill indexa knowledge/ADR em tabela, não manda ler |
| Custo — memória | `MEMORY.md` 12.007 B / 104 linhas = 115 B por linha. As 2 novas são de uma linha cada (**+250 B**) |
| Custo — rota barata | declarada: 10 frases por `custom_sentences` + `intent_script`, fala já pronta como atributo, sem LLM |
| Destilação | 2 ADRs com «Alternativas descartadas» real (16 e 15 linhas) · 5 knowledge datados com versão do HA · regra 190 · 2 libs com README + teste de mesa · skill canônica + 4 casos em `evals/` · 2 skills de repo com os 5 requisitos · CHANGELOG com os números (4 °C, 887,2 × 1019,90 hPa, `QUORUM=5`, 390 × 96 pontos) |
| Autoria | 13 commits, todos `MAYCON WILLIAN OLIVEIRA <visaodeempresa@gmail.com>`, mensagens em inglês, **0** linha de coautoria de IA |

## O que não consegui medir

1. **A tela.** Nada foi conferido renderizado no HA — auditoria é leitura.
2. **Regra 30 no destino.** Não rodei `curl` no `dist` que o servidor entrega,
   então não sei se o arquivo publicado é igual ao da `main`.
3. **A hipótese do achado BLOQUEIA na prática.** Não testei o card de tempo
   apontado para uma entidade `weather.*` de terceiro com pressão de estação —
   o defeito está provado por leitura do código e da regra, não por observação.
