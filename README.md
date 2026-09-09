<!-- MW-BRAND:BEGIN — gerado por IA/tools/mw-brand.sh · não editar à mão -->
<p align="center">
  <a href="https://github.com/visaodeempresa">
    <img src="https://mayconsoftware.github.io/assets/ve/LOGO_VISAO_DE_EMPRESA_HEIGHT-64px.png" alt="Visão de Empresa — MAYCON WILLIAN OLIVEIRA" height="64">
  </a>
  <br>
  <sub><b>Visão de Empresa</b> · componente de Home Assistant por MAYCON WILLIAN OLIVEIRA</sub>
</p>
<!-- MW-BRAND:END -->

# MW Letícia Weather

**Temperatura e previsão que você pode defender** — porque o número vem da fusão
de vários modelos meteorológicos, e a discórdia entre eles é publicada junto.

## O problema que gerou esta integração

Em 09/09/2026, 00:45, cinco fontes olhando o **mesmo ponto** (Águas Claras,
Brasília, 1200 m de altitude) divergiram em **4 °C** no mesmo minuto:

| Fonte | Temperatura |
|---|---|
| iOS Tempo | 20 °C |
| Android | 22 °C |
| weather.com | 19 °C |
| Met.no (integração nativa do HA) | 19 °C |
| Open-Meteo | 18,7 °C |

Nenhuma está com defeito. São **modelos diferentes, resolvidos em pontos de
grade diferentes, com altitudes de modelo diferentes**. Trocar de provedor não
resolve: escolhe outro número, com a mesma autoridade e a mesma solidão.

O que resolve é **fundir e publicar a incerteza**.

## O que ela faz

- **Mediana ponderada** de até 8 modelos (ECMWF, GFS, ICON, MET Norway, JMA,
  GEM, Météo-France, UKMO) numa **única requisição HTTP**.
- **Peso aprendido**: o modelo que vem concordando com o conjunto nesta casa
  pesa mais — com piso, para nunca degenerar num provedor só.
- **Confiança publicada**: `sensor.<local>_confianca` é a largura p10–p90 do
  conjunto. Um número sozinho mente por omissão.
- **Entidade `weather.` completa** (`FORECAST_DAILY | HOURLY | TWICE_DAILY`) —
  o intent nativo do Assist e qualquer card do HACS funcionam de graça.
- **Alertas oficiais** do INMET (Brasil, por polígono ou código IBGE), NWS
  (EUA) e MeteoAlarm (Europa), **mais alertas derivados** que funcionam em
  qualquer ponto do planeta — sempre rotulados como derivados.
- **Frases prontas em pt-BR** nos atributos, para o assistente de voz responder
  sem gastar token de LLM.
- **Serviços com resposta** para perguntar por **qualquer cidade do mundo**.

## O que ela NÃO faz

- **Não substitui órgão oficial.** Alerta derivado é cálculo desta integração e
  se anuncia como tal, na tela e na fala. Onde o órgão oficial não alcança, o
  silêncio dele não vira «não há risco».
- **Não corrige pelo sensor da casa por padrão.** A calibração local existe, é
  opcional e nasce **desligada**: quando ligada, publica entidade separada e
  nunca sobrescreve o número fundido em silêncio.

## Entidades

| Tipo | O que é |
|---|---|
| `weather.tempo_<local>` | condição, agora e previsão (diária, horária e duas vezes ao dia) |
| `sensor.*` | temperatura, sensação, **confiança**, umidade, pressão (MSL), vento, direção, UV, PM2.5, AQI, chance de chuva, alertas, **previsão falada** |
| `sensor.*` (diagnóstico) | o desvio de **cada modelo** contra o consenso — a prova da fusão |
| `binary_sensor.*` | clima seco, calor, frio, chuva forte, tempestade, vento forte, UV |

## Serviços

| Serviço | Para quê |
|---|---|
| `mw_leticia_weather.previsao` | agora, hoje, amanhã, **fim de semana** ou próximos N dias — de um local configurado ou de **qualquer cidade** |
| `mw_leticia_weather.alertas` | oficiais + derivados, com severidade, validade e instruções |
| `mw_leticia_weather.comparar_fontes` | modelo a modelo, consenso, discórdia e ponto de grade — a resposta para «por que o iPhone diz 20 e o card diz 19» |

Todos usam `SupportsResponse.ONLY`: na REST, **não esqueça `?return_response`**,
senão o HA devolve 200 vazio e ninguém entende por quê.

## Pressão: ao nível do mar, sempre

Esta casa está a **1200 m**. No mesmo minuto, a Open-Meteo devolveu
`surface_pressure` = **887,2 hPa** e todo o resto do mundo dizia **1019 hPa**.
Os dois estão certos: um é a pressão *da estação*, o outro é a *reduzida ao
nível do mar*. A entidade `weather.` e o `sensor.*_pressao` publicam **MSL** —
a de estação vai como atributo. Um mostrador de barômetro alimentado com 887
hPa ficaria eternamente em «tempestade».

## Instalação

HACS → Repositórios personalizados → `visaodeempresa/mw-ha-leticia-weather`,
categoria **Integração**. Depois: Ajustes → Dispositivos e Serviços →
Adicionar integração → **MW Letícia Weather**.

## Verificação

```bash
ruff check custom_components tests
python -m pytest -q
```

Saída esperada: `All checks passed!` e todos os testes verdes. Os testes usam
**resposta real gravada** da Open-Meteo (`tests/fixtures/`) — nenhum deles
depende de internet.

## Licença

MIT · © 2026 MAYCON WILLIAN OLIVEIRA
