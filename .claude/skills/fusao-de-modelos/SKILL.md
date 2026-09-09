---
name: fusao-de-modelos
description: Mexer na integração MW Letícia Weather — a fusão de modelos, as fontes (Open-Meteo, INMET, NWS, MeteoAlarm), os alertas e os serviços de voz. Use quando o Maycon disser "a temperatura está errada", "por que os aplicativos discordam", "o spread está alto", "descartou o modelo errado", "a integração não atualiza", "o alerta do INMET não aparece", "a previsão de outra cidade", ou quando aparecerem ensemble, MAD, quórum, `pressure_msl`, `forecast_days` ou `apiprevmet3` no assunto. A visão de conjunto (integração + os dois cards) está na skill `mw-clima`, publicada em ~/.claude/skills.
---

# Fusão de modelos — a integração

O que é: uma integração que **funde vários modelos e publica a discórdia**. O
que NÃO é: mais um cliente de provedor de tempo.

## Pré-condições

| Preciso de | Como obter | Se faltar |
|---|---|---|
| pytest e ruff | `../mw-ha-leticia-health/.venv/bin/python` | o CI reprova depois |
| `websockets` | `python3` do Homebrew | não instala nem confere no HA |
| Token do HA | `../ha-dashboards/.env` | nada fala com o HA |
| SSH | `ssh -F ../new_wakeword/ssh/ssh_config ha-leticia` (o `-F` **literal** na linha) | não dá para instalar frases |

## Onde a lógica mora

| Camada | Arquivo | Importa `homeassistant`? |
|---|---|---|
| Fontes (URL + parse) | `fontes/*.py` | **não** |
| Fusão | `fusao.py` | **não** |
| Alertas | `alertas.py` | **não** |
| Fala pt-BR | `fala.py` | **não** |
| Montagem do retrato | `montagem.py` | **não** |
| Rede e ciclo | `coordinator.py` | sim |
| Entidades e serviços | `weather.py`, `sensor.py`, `binary_sensor.py`, `servicos.py` | sim |

A pureza das cinco primeiras é **portão de CI**: é o que faz os testes rodarem
sem HA instalado e o que impede uma segunda verdade entre a integração e os
`tools/`.

## Armadilhas (com sintoma)

| Sintoma | Causa | Correção |
|---|---|---|
| O modelo que estava certo foi descartado | MAD sem quórum | `QUORUM_PARA_DESCARTE = 5` — não baixar |
| Semana em branco, sem erro | o bloco `daily` **também** vem sufixado por modelo | `diario_por_modelo` |
| 390 horas em vez de 96 | `past_hours` faz a API ignorar `forecast_days` | `past_days` |
| «Agora» igual em todos os modelos | `current` com `models=` **colapsa** | interpolar da série horária |
| Integração vazia ao desmarcar modelos | com UM modelo a coluna vem sem sufixo | `_coluna()` já cai para ela — não remover |
| Vento médio apontando para o lado oposto | mediana de ângulo | `fundir_angulo` |
| «Entity  is neither a valid entity ID…» ao instalar | `EntitySelector` opcional na tela de instalação | campo de entidade **só nas opções** |
| `The version 0.1.0 ... can not be used with HACS` | integração exige a versão **com `v`** | `version="v0.1.0"` |
| Frase casa e responde `Unknown intent` | restart do core não registra `intent_script` novo | `homeassistant.reload_all` |

## Verificação

```bash
../mw-ha-leticia-health/.venv/bin/ruff check custom_components tests tools
../mw-ha-leticia-health/.venv/bin/python -m pytest -q
../mw-ha-leticia-health/.venv/bin/python tools/sondar_fontes.py --lat -15.84 --lon -48.04 --ibge 5300108
```

Esperado: `All checks passed!`, 38 testes verdes e `tudo no ar` na sonda. Os
testes usam resposta REAL gravada em `tests/fixtures/` — nenhum depende de rede.

**No destino** (regra 30): `GET /api/states/weather.tempo_aguas_claras` tem de
trazer `confianca_spread` e `por_modelo` preenchidos.

**O que esta skill não verifica:** desenho na tela. Isso é dos cards.
