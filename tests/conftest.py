"""Os testes falam com os módulos PUROS direto, sem subir um Home Assistant.

É o que permite rodá-los no Mac, onde não há `homeassistant` instalado — e é
também o motivo de `fusao.py`, `alertas.py`, `fala.py`, `codigos.py`,
`montagem.py` e `fontes/` não dependerem do pacote do HA.

⚠️ Não dá para `import mw_leticia_weather`: o `__init__.py` do componente
importa o Home Assistant inteiro. Aqui se monta um PACOTE SINTÉTICO apontando
para a mesma pasta, sem executar o `__init__.py` — os imports relativos
(`from .fusao import …`) continuam funcionando, que é o que o HA precisa.
"""

import json
import sys
import types
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "custom_components" / "mw_leticia_weather"

for _nome, _caminho in (("mww", PASTA), ("mww.fontes", PASTA / "fontes")):
    _pacote = types.ModuleType(_nome)
    _pacote.__path__ = [str(_caminho)]
    sys.modules[_nome] = _pacote


@pytest.fixture(scope="session")
def previsao_bruta() -> dict:
    """Resposta REAL da Open-Meteo para Águas Claras, gravada em 2026-09-09.

    Fixture gravada, não rede: teste que depende de internet reprova por
    motivo errado no dia errado.
    """
    return json.loads(
        (RAIZ / "tests/fixtures/open_meteo_aguas_claras.json").read_text()
    )


@pytest.fixture(scope="session")
def ar_bruto() -> dict:
    return json.loads((RAIZ / "tests/fixtures/ar_aguas_claras.json").read_text())


@pytest.fixture
def modelos() -> list[str]:
    return ["ecmwf_ifs025", "gfs_seamless", "icon_seamless", "metno_seamless"]
