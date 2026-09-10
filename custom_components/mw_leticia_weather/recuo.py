"""O recuo depois de uma falha de rede. Módulo puro, de propósito.

Ele existe separado porque a primeira versão desta conta estava INVERTIDA e
ninguém percebeu lendo o código: `min(2**falhas, 8) * 60` dá 120 s na primeira
falha, oito vezes MAIS rápido que os 900 s normais. Um "backoff" que acelera é
um acelerador — o provedor tremendo passaria a receber 87 requisições por hora
em vez de 12.

Fora do coordinator, a conta tem teste de mesa e não pode inverter de novo em
silêncio.
"""

from __future__ import annotations

TETO_SEGUNDOS = 2 * 3600


def atraso(base_segundos: float, falhas: int, *, teto: float = TETO_SEGUNDOS) -> float:
    """Intervalo até a próxima tentativa, em segundos.

    Cresce a partir do intervalo NORMAL — nunca abaixo dele — dobrando a cada
    falha, até o teto. `falhas` é a contagem já incrementada (1 na primeira).
    """
    base = max(float(base_segundos), 1.0)
    n = max(int(falhas), 1)
    return min(base * 2 ** (n - 1), float(teto))
