# Clima MW — o que foi entregue em 09/09/2026

## O problema, medido

Cinco fontes olhando o **mesmo ponto** (Águas Claras, Brasília, −15,83985 /
−48,03618, **1200 m**) divergiram em **4 °C** no mesmo minuto:

| Fonte | Temperatura | Pressão |
|---|---|---|
| iOS Tempo | 20 °C | — |
| Android | 22 °C | 1.023 mb |
| weather.com | 19 °C | — |
| met.no no HA (o card que existia) | 19 °C | 1019,5 hPa |
| App de barômetro do iPhone (01:09) | **21 °C** · 73 % | **1019,90 hPa** |
| Sensor da janela | 23 °C (desvio conhecido) | — |
| Open-Meteo | 18,7 °C | **887,2 hPa** (`surface_pressure`) |

Nenhuma está com defeito. São **modelos diferentes, em pontos de grade
diferentes**: o ponto que a Open-Meteo realmente entrega para esse endereço é
−15,75 / −48,0, a 2 km de distância, a 1200 m. E os 887 hPa não são erro: é a
pressão **da estação**, não a reduzida ao nível do mar.

## O que foi construído

| Repositório (público) | O que é | Release |
|---|---|---|
| [`mw-ha-leticia-weather`](https://github.com/visaodeempresa/mw-ha-leticia-weather) | integração: funde ECMWF + GFS + ICON + MET Norway numa chamada e publica a discórdia | v0.1.2 |
| [`mw-ha-leticia-weather-card`](https://github.com/visaodeempresa/mw-ha-leticia-weather-card) | card de tempo (5 layouts, com a banda de confiança) **+** o céu no cabeçalho e no menu | v0.1.0 |
| [`mw-ha-barometer-card`](https://github.com/visaodeempresa/mw-ha-barometer-card) | barômetro aneroide, dois ponteiros, previsão Zambretti | v0.1.0 |

Todos instalados **pelo HACS** no HA da casa e conferidos no destino.

## A ideia central: publicar a dúvida

O número principal é a **mediana ponderada** de quatro modelos, e ao lado dele
sai o **spread p10–p90** como entidade de primeira classe. Um número sozinho
mente por omissão; com a largura da discórdia, não.

- O peso de cada modelo é aprendido pelo acerto recente, **com piso** — nunca
  degenera num provedor só.
- A rejeição de discrepante exige **quórum de 5 modelos**. Com os quatro do dia
  (18,3 · 18,6 · 19,5 · 21,7) o critério estatístico expulsava o GFS — e o GFS
  era justamente o que batia com o seu barômetro, que marcava 21 °C.
- A **calibração pelo seu sensor** existe, é opcional e **nasce desligada**,
  como você decidiu. Quando ligada, publica entidade separada: o número fundido
  nunca é sobrescrito em silêncio.

## O que está no ar agora

| Camada | Estado |
|---|---|
| `weather.tempo_aguas_claras` | ✅ com previsão diária, horária e duas vezes ao dia |
| 13 sensores + 7 binários de alerta | ✅ inclusive **confiança** e a **previsão falada** |
| 4 sensores de diagnóstico (desvio por modelo) | ✅ desligados por padrão, é a prova da fusão |
| 3 serviços com resposta | ✅ `previsao`, `alertas`, `comparar_fontes` |
| Alertas INMET por código IBGE + derivados mundiais | ✅ (hoje não há aviso ativo para o DF — isso é resultado, não falha) |
| Voz da Letícia, 10 frases locais | ✅ **token zero** (não passam pelo LLM) |
| Voz para qualquer cidade do mundo | ✅ testado com Lisboa |
| Dashboard `/clima-3-0`, 4 abas | ✅ Agora · Semana · **Confiança** · Alertas |
| Céu no cabeçalho e no menu | ✅ ligado só na `/clima-3-0`, por card de altura zero |

## Verificação (regra 30 — no destino)

```
weather.tempo_aguas_claras          → cloudy
  temperatura fundida                 18,6 °C   (spread 0,65)
  por modelo   ECMWF 18,3 · GFS 19,1 · ICON 18,8 · MET Norway 18,5
  pressão MSL                         1020,1 hPa   (estação: 888,1)
  3 h atrás                           1018,2 hPa → +1,9 hPa (o barômetro sobe)
  ponto de grade                      −15,75 / −48,0 · 1200 m
```

Frases testadas por `POST /api/conversation/process`, todas certas:
«qual a temperatura», «como está o tempo», «vai chover amanhã», «qual a previsão
para hoje», «como fica o tempo no fim de semana», «tem alerta de tempestade»,
«o ar está seco», «que horas o sol se põe», «os modelos concordam», «vai chover
essa semana». E pelo cérebro conversacional: «como está o tempo em Lisboa
agora» → 23 graus, céu limpo.

### O que NÃO foi verificado, e está dito

- **Não consegui abrir a tela real do HA no navegador desta sessão** (a rede
  local não é alcançável daqui). Os cards foram medidos na bancada, e a
  `/clima-3-0` foi conferida por releitura da configuração no servidor — mas o
  **render final da tela só você vê**.
- **Nenhum aviso do INMET estava ativo para o DF** no momento do teste, então o
  caminho do alerta oficial foi exercitado com Uberlândia (2 avisos de
  tempestade, com riscos e instruções), não com a sua cidade.

## Duas coisas que aconteceram e você precisa saber

1. **Reiniciei o core do HA quatro vezes** — instalar integração custom exige.
   Cada parada durou cerca de um minuto.
2. **Rodei `leticia-ops/scripts/apply.py` sem querer** (chamei com `--help`, que
   não é uma flag reconhecida, e ele executou). Ele aplicou **duas** mudanças:
   o bloco novo do prompt (que era a intenção) **e** a wake word da sala, que
   estava em «Okay Nabu» e voltou para «Letícia». A segunda **não era minha
   intenção**, embora seja o estado declarado no `bindings.yaml` e a deriva
   conhecida das instalações de firmware. Se você preferia a sala em «Okay
   Nabu», é só trocar de volta — e me diga, para o `bindings.yaml` refletir isso.

## Trabalho pendente que eu deixaria para depois

- Ligar o céu no HA inteiro (Ajustes, Histórico) exige `configuration.yaml` +
  restart do core. Está documentado e pronto; a decisão é sua.
- O `deploy-ha.yml` dos repos aponta para o `HA_URL` **local**, que o runner da
  GitHub não alcança. Para a esteira publicar sozinha, o segredo precisa ser a
  URL da Nabu Casa.
