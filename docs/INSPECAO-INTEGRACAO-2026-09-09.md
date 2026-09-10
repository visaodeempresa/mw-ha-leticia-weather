# Inspeção de integração — `mw_leticia_weather`

**Data:** 2026-09-09 · **Alvo:** `custom_components/mw_leticia_weather` (repo `mw-ha-leticia-weather`)
**HA:** 2026.9.1 (Yellow, aarch64) · **Entry auditada:** `01M22TKZ9BRD12CQJ05RKBV37B`
**Método:** régua estática + medição contra o HA vivo e contra os provedores reais. Nada foi reiniciado, nada foi alterado.

---

## 0. Calibração na régua (regra 140)

Antes de julgar o alvo, a régua inteira rodou em `PROJECTS/mw-ha-leticia-health/` — integração já aceita pelo dono.

| Eixo | Resultado no health | Ajuste na régua |
|---|---|---|
| `ruff check custom_components tests tools` | `All checks passed!` | — |
| `pytest -q` | 23 testes verdes | — |
| Ordem de chave do manifest | OK | — |
| `manifest.json` == `pyproject.toml` | 0.2.0 == 0.2.0 | — |
| I/O bloqueante no event loop | 0 ocorrências | — |
| Sessão HTTP única | **N/A** — integração é webhook de entrada, não faz saída de rede | eixo marcado N/A, não reprova |
| Setup < 2 s | trivialmente sim (sem rede no setup) | — |
| Listener no unload | `async_on_unload` + `async_on_remove` nos 2 `async_track_time_interval` | — |
| `unique_id` não derivado de nome | `entry_id`-based | — |
| Diagnóstico redige | **redige por construção** (`segredo_ativo: bool`), **não** usa `async_redact_data` | eixo reescrito: o critério é *o dado sensível não sai*, não *usa a função helper* |
| `# noqa` sem justificativa | 7 ocorrências, todas `E402` em `tools/` por bootstrap de `sys.path` | eixo restrito a `custom_components/`; `tools/` com E402 de bootstrap é aceito |

**Conclusão da calibração:** dois limites estavam errados e foram consertados (sessão HTTP como N/A para integração sem saída de rede; diagnóstico julgado pelo vazamento e não pelo helper). Com a régua corrigida, o health passa em 100% dos eixos aplicáveis. É essa régua corrigida que foi aplicada ao alvo.

---

## 1. Achados

### BLOQUEIA — o "recuo com jitter" acelera em vez de recuar

Na primeira falha do provedor o intervalo **cai** de 900 s para ~124 s. O teto do recuo (8,4 min) nunca alcança o intervalo normal de 15 min, então a integração nunca recua: ela só acelera, e acelera mais justamente quando o provedor está caindo — o oposto do que o próprio comentário do código diz estar prevenindo.

```
onde: custom_components/mw_leticia_weather/coordinator.py:131-133
medida: simulação da fórmula real do código (min(2**falhas, 8) * 60 + random.uniform(0,30)):
        falhas=1 → 124 s → 87 req/h   (normal: 900 s → 12 req/h) — 7,3× mais carga
        falhas=2 → 265 s → 41 req/h
        falhas=3+ → ~493 s (8,2 min) → 22 req/h  ← teto; nunca chega aos 900 s
        viola o piso de 5 min da régua para fonte pública gratuita em falhas=1 e falhas=2
conserto: partir do intervalo normal em vez de partir de 2 min —
        base = self.update_interval_normal.total_seconds()   # 900
        atraso = min(base * 2**self._falhas, 6*3600) + random.uniform(0, 60)
        guardar o intervalo normal num atributo no __init__ (hoje ele é recalculado
        do config a cada sucesso, o que já é o lugar certo para lê-lo uma vez).
```

### IMPORTANTE — setup do config entry acima do limite

O `async_setup_entry` espera o primeiro refresh, que é rede. Duas medições independentes concordam.

```
onde: custom_components/mw_leticia_weather/__init__.py:47-49
medida: setup_times do próprio HA (via /api/diagnostics/config_entry/<id>, instalação viva):
          config_entry_setup    = 28,41 s (relógio, durante boot congestionado)
          wait_import_platforms = -25,81 s
          → tempo atribuível à integração = 2,60 s   (limite da régua: 2 s)
        medição independente do ciclo completo, rodando o CoordenadorClima real:
          ciclo 1 (frio) 3244 ms · ciclo 2 (quente) 2555 ms
conserto: não esperar a rede para declarar o entry pronto. Trocar
        `await coordenador.async_config_entry_first_refresh()` por
        `await coordenador.async_refresh()` + `hass.async_create_task(...)` não serve
        (perde o ConfigEntryNotReady). O caminho que serve é encolher o payload
        (achados seguintes): com forecast em 30,3 KiB e INMET fora do caminho crítico
        do setup, o ciclo cai para a faixa de 1,3-1,6 s e o eixo passa sem mudar o contrato.
```

### IMPORTANTE — INMET: 621,6 KiB a cada 15 min para 4 avisos no país inteiro

O endpoint `/avisos/ativos` não aceita filtro; ele devolve o Brasil inteiro, com os polígonos GeoJSON. A integração o baixa acoplado ao ciclo de temperatura, que é 15 min. Aviso meteorológico oficial não muda de 15 em 15 minutos.

```
onde: custom_components/mw_leticia_weather/coordinator.py:154-162 (chamado por _async_update_data)
medida: 621,6 KiB por ciclo · 4 avisos ativos no país no momento da medição
        96 ciclos/dia × 621,6 KiB = 58,3 MiB/dia contra uma API pública de órgão federal
        (o total da integração hoje é 737,7 KiB/ciclo = 69,2 MiB/dia)
        json.loads desses 621,6 KiB: 2,7 ms (M1) — no event loop, mas dentro do orçamento
conserto: desacoplar a cadência do aviso da cadência da temperatura. Guardar
        self._avisos_cache e self._avisos_em (timestamp); refazer a busca só quando
        passaram ≥ 60 min, devolvendo o cache no resto. Reduz para 24 buscas/dia
        (14,6 MiB/dia) e derruba o ciclo de 3 para 2 requisições em 3 de cada 4 ciclos.
```

### IMPORTANTE — Open-Meteo: 88% das linhas horárias são baixadas e jogadas fora

`forecast_days=16` traz 408 linhas horárias. `montagem.montar` publica `horas_a_publicar=48`. As outras 360 linhas atravessam a rede, o parser JSON e a memória para serem descartadas.

```
onde: custom_components/mw_leticia_weather/fontes/open_meteo.py:66-90 (dias: int = 16)
medida: pedido atual                          113,2 KiB · hourly=408 linhas · daily=17
        forecast_hours=48 + past_hours=24      30,3 KiB · hourly= 72 linhas · daily=16
        (as duas medidas contra a API real, 2026-09-09) → 73% menos banda
        das 408 linhas horárias, 48 chegam a virar entidade (montagem.py:192,205)
conserto: trocar `"past_days": "1"` por `"forecast_hours": "48", "past_hours": "24"`,
        mantendo forecast_days=16 para o bloco diário. Verificado: o bloco daily
        continua vindo (16 dias) e as 24 h de passado do barômetro continuam vindo.
        Atenção: cai de 17 para 16 linhas diárias — se os 17 dias importam,
        forecast_days=17.
```

### IMPORTANTE — constante depreciada, com aviso no log ao vivo

```
onde: custom_components/mw_leticia_weather/sensor.py (import de CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)
medida: WARNING no log da instalação, 2 vezes na janela observada
        (2026-09-09 07:15:06 e 07:20:25, [homeassistant.const]):
        "The deprecated constant CONCENTRATION_MICROGRAMS_PER_CUBIC_METER was used from
         mw_leticia_weather. It will be removed in HA Core 2027.8"
conserto: `from homeassistant.const import UnitOfDensity` e usar
        `UnitOfDensity.MICROGRAMS_PER_CUBIC_METER` no descritor do sensor pm25.
```

### IMPORTANTE — o interruptor de calibração local não é lido por ninguém

A tela de opções oferece a seção «calibração» com o toggle `calibrar` e o seletor `sensor_local`. Nenhum consumidor existe: `SECAO_CALIBRACAO`, `CONF_CALIBRAR` e `CONF_SENSOR_LOCAL` aparecem só no `const.py` e no `config_flow.py`. Ligar o toggle não muda nada, e não avisa que não mudou nada.

```
onde: custom_components/mw_leticia_weather/config_flow.py:159-176 (oferta)
       — sem nenhum leitor em coordinator.py, sensor.py, weather.py ou montagem.py
medida: 0 referências fora de const.py e config_flow.py (grep em custom_components/)
conserto: escolher um dos dois. (a) implementar: ler o sensor local no coordinator e
       publicar `sensor.<local>_temperatura_calibrada` separada, como o __init__.py promete;
       (b) retirar a seção do config_flow até existir implementação. A regra 120 exige que
       nasça desligada — e nasce (CALIBRAR_PADRAO=False) — mas não autoriza controle morto.
```

### IMPORTANTE — a atribuição credita uma fonte que nunca é consultada

`ATRIBUICAO` sai no atributo `attribution` das 21 entidades e diz «… INMET · NWS · MeteoAlarm». O módulo MeteoAlarm existe e nunca é importado: `_avisos_oficiais` cobre só Brasil e EUA, e devolve lista vazia fora dessas caixas.

```
onde: const.py:78-80 (ATRIBUICAO) · fontes/avisos_meteoalarm.py (módulo órfão)
       coordinator.py:41 importa apenas avisos_inmet e avisos_nws
medida: 'meteoalarm' tem 1 ocorrência em todo custom_components/, dentro do próprio módulo
        21 entidades ao vivo carregam a atribuição que cita MeteoAlarm
conserto: ligar o MeteoAlarm em _avisos_oficiais (a caixa da Europa) ou tirar o nome
        da ATRIBUICAO. Creditar fonte não consultada é o mesmo defeito que a integração
        se propõe a combater: número com autoridade emprestada.
```

### IMPORTANTE — a versão que roda não é a versão do repo

```
onde: /config/custom_components/mw_leticia_weather/manifest.json (no HA) × manifest.json (repo)
medida: instalado 0.1.0 · repo 0.1.1 · pyproject 0.1.1
        os 22 arquivos .py são byte-idênticos (md5 conferido um a um) — só o manifest ficou para trás
conserto: copiar o manifest.json para /config/custom_components/mw_leticia_weather/.
        Sem isso o HACS não oferece a atualização e o diagnóstico anexado a um issue
        relata a versão errada. (O eixo "manifest == pyproject" passa no repo; o que
        reprova é o deploy não verificado.)
```

### POLIMENTO — o comentário sobre o bloco diário está errado

```
onde: fontes/open_meteo.py:45-47 ("Diárias vêm só do modelo padrão (best_match)")
medida: a resposta real traz 57 colunas diárias — 14 variáveis × 4 modelos + time.
        As chaves são sufixadas: 'temperature_2m_max_ecmwf_ifs025'. O parâmetro `models`
        do Open-Meteo vale para a requisição inteira; não dá para escopá-lo por bloco.
        Custo real do engano: 8,1 KiB por ciclo — pequeno, mas o comentário desinforma
        quem for mexer no orçamento depois.
conserto: corrigir o comentário para dizer que o daily também vem por modelo e que
        montagem.py resolve a coluna sufixada.
```

### POLIMENTO — constantes mortas e altitude que não é usada

```
onde: const.py:25 (CONF_ALTITUDE) e const.py:74 (SINAL_DADOS) — 0 leitores
medida: o HA declara elevação 1197 m; a Open-Meteo, sem o parâmetro, resolve 1211 m.
        Medido o efeito de mandar elevation=1197 nos 4 modelos: delta de +0,0 a +0,1 °C.
conserto: remover as duas constantes. Não vale ligar o parâmetro `elevation`:
        a medição mostra que ele não move o número (≤0,1 °C), e a integração inteira
        existe para não trocar número por número sem ganho demonstrado.
```

### POLIMENTO — 4 sensores de desvio nascem sempre vazios

```
onde: sensor.py:220-248 (DIAGNOSTICOS itera MODELOS_ROTULO, que tem 8 modelos)
medida: 8 entidades de desvio no registry, 8 desabilitadas por padrão;
        só 4 modelos estão configurados, então 4 delas retornariam None se ligadas
conserto: iterar sobre coordenador.modelos em vez de MODELOS_ROTULO, ou aceitar
        como está — desabilitadas por padrão, não poluem tela nem recorder.
```

---

## 2. O que passou, com o número

| Eixo | Medida |
|---|---|
| `ruff check custom_components tests tools` | `All checks passed!` |
| `pytest -q` | 38 testes verdes |
| Ordem de chave do manifest | OK (domain, name, depois alfabética) |
| `manifest.json` == `pyproject.toml` **no repo** | 0.1.1 == 0.1.1 |
| Requisições por ciclo por local | **3** (limite 4) — contadas rodando o `_async_update_data` real com sessão instrumentada, 2 ciclos consecutivos |
| `update_interval` declarado | 900 s = 15 min (piso 5 min) — confirmado no diagnóstico vivo: `intervalo_s: 900.0` |
| Sessão HTTP | 1, de `async_get_clientsession(hass)`, em 2 pontos de uso; **0** sessão própria |
| I/O bloqueante no event loop | **0** — `urllib` aparece só como `urlencode`; a sonda é CLI fora do HA |
| CPU no event loop | `montagem.montar` vai para o executor; mediana 10,9 ms (min 8,4 / max 18,1, M1) |
| `ConfigEntryNotReady` no setup | sim, por `async_config_entry_first_refresh()` convertendo `UpdateFailed` |
| Falha de rede vira `UpdateFailed` | sim; fonte secundária que cai não derruba o ciclo (`_buscar` devolve `None`) |
| `unique_id` | `entry_id`-based; **0** de 29 entidades sem `unique_id`; unique_id do entry é a coordenada, não o nome |
| `_attr_has_entity_name` | `True` na classe base |
| `DeviceInfo` | **1** device por entry: «Tempo — Águas Claras» / Visão de Empresa |
| Unidade declarada | 100% dos sensores com grandeza física (°C, %, hPa, km/h, °, µg/m³); `weather` declara as 5 unidades nativas |
| Diagnóstico redige | ao vivo: 6 `**REDACTED**`, **0** vazamento de `-15.8`, `-48.0`, `5300108` ou «Águas Claras» no arquivo de 7480 bytes |
| Regra 120 | calibração nasce desligada (`CALIBRAR_PADRAO=False`); sonda `tools/sondar_fontes.py` só lê |
| Tradução sem `<…>` | 0 ocorrências em `strings.json`, `en.json`, `pt-BR.json` |
| Erros da integração no log | **0** menções em 20 017 linhas (janela 14:26→16:04) além do aviso de constante depreciada |
| `# noqa` novo em `custom_components/` | 0 |

---

## 3. O que eu **não** consegui medir

- **Recuo em falha real.** Não houve queda de provedor durante a auditoria: os 3 endpoints responderam 200 nas duas rodadas. O achado BLOQUEIA vem de simular a fórmula exata do código, não de observar produção.
- **`async_unload_entry`.** Instalar → remover → conferir tarefa órfã exigiria mexer na instalação (proibido, regra 170). A revisão estática não achou `async_track_time_interval` nem webhook, o `add_update_listener` está sob `async_on_unload`, as plataformas são descarregadas e os serviços só somem na última entry — mas **não há prova de execução**.
- **`Setup of domain … took` no log.** A instalação retém só WARNING e ERROR (342 e 60 na janela); a linha INFO não existe. O número de setup veio do `setup_times` do diagnóstico, que é a contabilidade do próprio HA — e o valor de 28,41 s é relógio durante um boot com dezenas de integrações concorrendo, não custo isolado. Os 2,60 s atribuíveis são a subtração que o próprio HA propõe, e batem com os 2,56-3,24 s medidos à parte.
- **MeteoAlarm, NWS e geocodificação** não foram exercitados contra a rede: o local auditado cai na caixa do Brasil, então só o INMET roda.
- **`hassfest`** não foi executado (não há container HA nesta máquina). A ordem de chave do manifest foi conferida pela checagem caseira, que é o que o hassfest reprova sem dizer qual chave.
- **Segundo local.** A integração está com 1 entry; o comportamento com 2 locais (orçamento dobrado, `remover()` só na última) foi revisado no código, não observado.

---

## 4. Veredito

**Não entrega ainda — falta um conserto de uma linha e meia.** A integração está muito acima da média do que se instala como custom component: 3 requisições por ciclo contra um teto de 4, sessão única do HA, zero I/O bloqueante, montagem pesada no executor, diagnóstico que comprovadamente não vaza a coordenada da casa, 38 testes e ruff limpos, unidades declaradas em tudo, um device por local e nenhum erro no log ao vivo. O que a reprova é um defeito único e objetivo: o recuo que o código chama de backoff é um acelerador — na primeira falha do provedor a integração passa a bater 87 vezes por hora em vez de 12, e o teto do recuo nunca alcança sequer o intervalo normal, de modo que uma instabilidade da Open-Meteo vira exatamente o bloqueio que o comentário do próprio arquivo diz querer evitar; enquanto isso o orçamento de banda está 4× inflado por escolhas que a medição mostra serem gratuitas de corrigir (73% a menos no forecast trocando dois parâmetros, 75% a menos no INMET desacoplando a cadência do aviso da cadência da temperatura), e três controles mentem para o usuário — o toggle de calibração que ninguém lê, a atribuição que credita o MeteoAlarm nunca consultado e o manifest 0.1.0 rodando enquanto o repo diz 0.1.1. Consertados o recuo (bloqueante) e os dois orçamentos (que de quebra colocam o setup abaixo dos 2 s), o resto é higiene de meia hora e a integração entrega com folga.
