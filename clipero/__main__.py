"""Clipero: convierte los VODs de Twitch de Abue en clips verticales.

Uso:
    python -m clipero listar
    python -m clipero procesar               # el VOD más nuevo sin procesar
    python -m clipero procesar --vod 2865569083
    python -m clipero procesar --vod 2865569083 --desde 0 --hasta 600   # solo un tramo
    python -m clipero procesar --con-facecam  # en streams donde usaste cámara
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import momentos, render, subtitulos, vods

RAIZ = Path(__file__).resolve().parent.parent


def cargar_config(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def procesados(salida: Path) -> set[str]:
    return {p.name for p in salida.iterdir() if (p / "manifest.json").exists()} if salida.exists() else set()


def cmd_listar(cfg: dict, _args) -> int:
    hechos = procesados(RAIZ / cfg["carpeta_salida"])
    for v in vods.listar_vods(cfg["canal_twitch"]):
        marca = "listo" if v["id"] in hechos else "nuevo"
        print(f"{v['id']}  {int(v['duracion'] // 60):>4} min  [{marca}]  {v['titulo']}")
    return 0


def cmd_procesar(cfg: dict, args) -> int:
    salida = RAIZ / cfg["carpeta_salida"]
    if args.vod:
        vod = {"id": args.vod, "titulo": args.titulo or "", "url": f"https://www.twitch.tv/videos/{args.vod}"}
    else:
        hechos = procesados(salida)
        nuevos = [v for v in vods.listar_vods(cfg["canal_twitch"]) if v["id"] not in hechos]
        if not nuevos:
            print("No hay VODs nuevos.")
            return 0
        vod = nuevos[0]

    carpeta = salida / vod["id"]
    print(f"Descargando VOD {vod['id']} {vod.get('titulo', '')}...")
    video = vods.descargar_vod(vod["id"], RAIZ / "descargas", desde=args.desde, hasta=args.hasta)

    audio = momentos.leer_audio(video)
    segmentos = None
    sub_cfg = cfg.get("subtitulos") or {}
    if sub_cfg.get("activar") and subtitulos.disponible():
        print("Transcribiendo audio (puede tardar)...")
        segmentos = subtitulos.transcribir(audio, sub_cfg.get("modelo", "small"), sub_cfg.get("idioma", "es"))
    elif sub_cfg.get("activar"):
        print("Aviso: faster-whisper no está instalado, los clips salen sin subtítulos.")

    print("Buscando los mejores momentos...")
    c = cfg["clips"]
    movimiento = momentos.movimiento_por_segundo(video)
    p = momentos.puntaje(momentos.volumen_por_segundo(audio), segmentos, cfg.get("palabras_clave"), movimiento)
    elegidos = momentos.elegir_momentos(p, c["por_stream"], c["duracion"], c["antes_del_pico"], c["separacion_minima"])

    facecam = None
    if args.con_facecam:
        facecam = cfg.get("facecam")
        if not facecam:
            print("Aviso: pediste --con-facecam pero config.yaml no tiene el recuadro 'facecam'; sale sin cámara.")
    carpeta.mkdir(parents=True, exist_ok=True)
    if segmentos is not None:
        (carpeta / "transcripcion.json").write_text(json.dumps(segmentos, ensure_ascii=False), encoding="utf-8")
    clips = []
    for i, m in enumerate(elegidos, 1):
        nombre = f"clip_{i:02d}"
        ass = None
        if segmentos is not None:
            ass = subtitulos.escribir_ass(segmentos, m["inicio"], m["fin"], carpeta / f"{nombre}.ass")
        print(f"  {nombre}: {m['inicio']:.0f}s a {m['fin']:.0f}s (puntaje {m['puntaje']})")
        render.vertical(video, m["inicio"], m["fin"], carpeta / f"{nombre}.mp4", facecam, ass,
                        pico=m["pico"] - m["inicio"])
        offset = args.desde or 0
        clips.append({
            "archivo": f"{nombre}.mp4",
            "inicio_en_vod": m["inicio"] + offset,
            "fin_en_vod": m["fin"] + offset,
            "pico_en_clip": m["pico"] - m["inicio"],
            "puntaje": m["puntaje"],
            "gancho": "",
            "texto": " ".join(s["texto"] for s in (segmentos or [])
                              if s["fin"] > m["inicio"] and s["inicio"] < m["fin"]),
            "estado": "pendiente",  # pendiente | aprobado | descartado | publicado
        })

    manifest = {
        "vod": vod,
        "con_facecam": bool(facecam),
        "desde": args.desde or 0,
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "clips": clips,
    }
    (carpeta / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Listo: {len(clips)} clips en {carpeta}")
    return 0


def cmd_editar(cfg: dict, args) -> int:
    """Vuelve a exportar los clips de un VOD con el gancho escrito en manifest.json."""
    carpeta = RAIZ / cfg["carpeta_salida"] / args.vod
    manifest = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
    video = RAIZ / "descargas" / f"{args.vod}.mp4"
    if not video.exists():
        print("Descargando el VOD otra vez...")
        desde = manifest.get("desde") or None
        video = vods.descargar_vod(args.vod, RAIZ / "descargas", desde=desde)
    trans = carpeta / "transcripcion.json"
    segmentos = json.loads(trans.read_text(encoding="utf-8")) if trans.exists() else []
    facecam = cfg.get("facecam") if manifest.get("con_facecam") else None
    offset = manifest.get("desde") or 0
    for c in manifest["clips"]:
        if args.clip and c["archivo"] != f"clip_{args.clip:02d}.mp4":
            continue
        ini, fin = c["inicio_en_vod"] - offset, c["fin_en_vod"] - offset
        nombre = Path(c["archivo"]).stem
        ass = subtitulos.escribir_ass(segmentos, ini, fin, carpeta / f"{nombre}.ass", c.get("gancho") or None)
        print(f"  {nombre}: gancho '{c.get('gancho', '')}'")
        render.vertical(video, ini, fin, carpeta / c["archivo"], facecam, ass, pico=c.get("pico_en_clip"))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="clipero", description="Clips verticales desde los VODs de Twitch.")
    ap.add_argument("--config", default=str(RAIZ / "config.yaml"))
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("listar", help="Lista los VODs del canal")
    pp = sub.add_parser("procesar", help="Genera clips de un VOD")
    pp.add_argument("--vod", help="ID del VOD (sin la v). Si no se da, toma el más nuevo sin procesar.")
    pp.add_argument("--titulo", help="Título del VOD (opcional, para el manifest)")
    pp.add_argument("--desde", type=float, help="Segundo inicial del tramo a descargar")
    pp.add_argument("--hasta", type=float, help="Segundo final del tramo a descargar")
    pp.add_argument("--con-facecam", action="store_true",
                    help="Pone tu facecam arriba del clip (usa el recuadro 'facecam' de config.yaml)")
    pe = sub.add_parser("editar", help="Re-exporta clips con el gancho escrito en manifest.json")
    pe.add_argument("--vod", required=True)
    pe.add_argument("--clip", type=int, help="Solo este número de clip")
    args = ap.parse_args(argv)
    cfg = cargar_config(Path(args.config))
    return {"listar": cmd_listar, "procesar": cmd_procesar, "editar": cmd_editar}[args.comando](cfg, args)


if __name__ == "__main__":
    sys.exit(main())
