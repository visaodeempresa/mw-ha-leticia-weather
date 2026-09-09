#!/usr/bin/env python3
"""Sonda: LÊ as quatro fontes e não grava nada em lugar nenhum.

Regra global 120 desta casa: toda integração com coletor externo precisa de uma
sonda que só lê. Serve para responder «a fonte está no ar?» sem instalar,
sem criar entidade e sem tocar no Home Assistant.

    python3 tools/sondar_fontes.py --lat -15.83985 --lon -48.03618
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import types
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "custom_components" / "mw_leticia_weather"
for _nome, _caminho in (("mww", PASTA), ("mww.fontes", PASTA / "fontes")):
    _p = types.ModuleType(_nome)
    _p.__path__ = [str(_caminho)]
    sys.modules[_nome] = _p

from mww.fontes import ar as fonte_ar  # noqa: E402
from mww.fontes import avisos_inmet, avisos_nws, geocodificacao  # noqa: E402
from mww.fontes import open_meteo as om  # noqa: E402

AGENTE = "mw-ha-leticia-weather/sonda (+https://github.com/visaodeempresa)"
MODELOS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless", "metno_seamless"]


def buscar(url: str) -> tuple[dict | None, float, str]:
    inicio = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(req, timeout=25) as r:
            dados = json.load(r)
        return dados, (time.perf_counter() - inicio) * 1000, "ok"
    except Exception as erro:  # noqa: BLE001 — sonda relata, não trata
        return None, (time.perf_counter() - inicio) * 1000, f"{type(erro).__name__}: {erro}"


def main() -> int:
    p = argparse.ArgumentParser(description="Sonda das fontes do MW Letícia Weather")
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--ibge", default=None)
    p.add_argument("--cidade", default=None, help="testa também a geocodificação")
    args = p.parse_args()

    falhas = 0
    print(f"ponto pedido: {args.lat}, {args.lon}\n")

    previsao, ms, estado = buscar(om.url(args.lat, args.lon, MODELOS, dias=3))
    print(f"[previsão]  {estado}  {ms:.0f} ms")
    if previsao:
        meta = om.metadados(previsao)
        print(f"            grade: {meta['latitude_grade']}, {meta['longitude_grade']}"
              f"  elevação {meta['elevacao_modelo']} m  fuso {meta['fuso']}")
        presentes = om.series_por_modelo(previsao, MODELOS)
        i = om.indice_de(om.eixo_tempo(previsao), __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc))
        temps = om.amostras_em(previsao, list(presentes), "temperature_2m", i)
        print(f"            modelos: {len(presentes)}/{len(MODELOS)}  temperatura {temps}")
        if temps:
            print(f"            amplitude entre modelos: "
                  f"{max(temps.values()) - min(temps.values()):.1f} °C")
        if len(presentes) < 2:
            print("            ⚠ menos de dois modelos: a medida de confiança fica sem sentido")
    else:
        falhas += 1

    ar_bruto, ms, estado = buscar(fonte_ar.url(args.lat, args.lon, dias=1))
    print(f"\n[ar]        {estado}  {ms:.0f} ms")
    if ar_bruto:
        i = 0
        print(f"            {fonte_ar.interpretar(ar_bruto, i)}")
    else:
        falhas += 1

    if -34 <= args.lat <= 6 and -75 <= args.lon <= -33:
        avisos, ms, estado = buscar(avisos_inmet.URL)
        print(f"\n[INMET]     {estado}  {ms:.0f} ms")
        if avisos:
            total = sum(len(avisos.get(g) or []) for g in ("hoje", "futuro"))
            meus = avisos_inmet.interpretar(avisos, args.lat, args.lon, ibge=args.ibge)
            print(f"            {total} aviso(s) ativos no Brasil, {len(meus)} neste ponto")
            for a in meus:
                print(f"            · {a['severidade']:14} {a['titulo']}  "
                      f"{a['inicio']} → {a['fim']}")
            if not meus:
                print("            (nenhum aviso aqui agora — isso é resultado, não falha)")
        else:
            falhas += 1
    elif 18 <= args.lat <= 72 and -170 <= args.lon <= -60:
        avisos, ms, estado = buscar(avisos_nws.url(args.lat, args.lon))
        print(f"\n[NWS]       {estado}  {ms:.0f} ms")
        if avisos:
            print(f"            {len(avisos_nws.interpretar(avisos))} aviso(s) neste ponto")
        else:
            falhas += 1
    else:
        print("\n[oficial]   fora da cobertura de INMET/NWS — só alertas derivados aqui")

    if args.cidade:
        geo, ms, estado = buscar(geocodificacao.url(args.cidade))
        print(f"\n[geo]       {estado}  {ms:.0f} ms")
        if geo:
            achado = geocodificacao.melhor(geocodificacao.interpretar(geo))
            print(f"            {geocodificacao.rotulo(achado) if achado else 'não encontrada'}")
        else:
            falhas += 1

    print(f"\n{'tudo no ar' if not falhas else f'{falhas} fonte(s) fora'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
