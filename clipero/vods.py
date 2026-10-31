"""Listar y descargar VODs del canal de Twitch con yt-dlp."""
from __future__ import annotations

from pathlib import Path

import yt_dlp


def listar_vods(canal: str, limite: int = 20) -> list[dict]:
    """Devuelve las transmisiones guardadas del canal, de la más nueva a la más vieja."""
    url = f"https://www.twitch.tv/{canal}/videos?filter=archives&sort=time"
    opciones = {"extract_flat": True, "quiet": True, "playlistend": limite}
    with yt_dlp.YoutubeDL(opciones) as ydl:
        info = ydl.extract_info(url, download=False)
    vods = []
    for e in info.get("entries") or []:
        vods.append({
            "id": str(e["id"]).lstrip("v"),
            "titulo": e.get("title") or "",
            "duracion": float(e.get("duration") or 0),
            "url": f"https://www.twitch.tv/videos/{str(e['id']).lstrip('v')}",
        })
    return vods


def descargar_vod(vod_id: str, carpeta: Path, calidad: str = "1080p60/1080p/best",
                  desde: float | None = None, hasta: float | None = None) -> Path:
    """Descarga el VOD (o solo un tramo) como MP4 y devuelve la ruta."""
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{vod_id}.mp4"
    if destino.exists():
        return destino
    opciones = {
        "format": calidad,
        "outtmpl": str(carpeta / f"{vod_id}.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "noprogress": True,
    }
    if desde is not None or hasta is not None:
        opciones["download_ranges"] = yt_dlp.utils.download_range_func(
            None, [(desde or 0, hasta or float("inf"))])
        opciones["force_keyframes_at_cuts"] = True
    with yt_dlp.YoutubeDL(opciones) as ydl:
        ydl.download([f"https://www.twitch.tv/videos/{vod_id}"])
    if not destino.exists():
        raise FileNotFoundError(f"No se generó {destino}")
    return destino
