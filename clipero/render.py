"""Cortar un tramo del VOD y convertirlo a video vertical 1080x1920."""
from __future__ import annotations

import subprocess
from pathlib import Path


def _ruta_filtro(ruta: Path) -> str:
    """Escapa una ruta para usarla dentro de un filtro de ffmpeg (también en Windows)."""
    s = ruta.resolve().as_posix()
    return s.replace(":", r"\:").replace("'", r"\'")


def vertical(video: Path, inicio: float, fin: float, destino: Path,
             facecam: dict | None = None, ass: Path | None = None) -> Path:
    """Fondo desenfocado + juego centrado; facecam arriba si está configurada."""
    duracion = fin - inicio
    if facecam:
        fc = facecam
        filtro = (
            "[0:v]split=3[a][b][c];"
            "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[fondo];"
            "[b]scale=1080:-2[juego];"
            f"[c]crop={fc['w']}:{fc['h']}:{fc['x']}:{fc['y']},scale=1080:-2[cara];"
            "[fondo][cara]overlay=0:120[t1];"
            "[t1][juego]overlay=0:(H-h)/2+220[v0]"
        )
    else:
        filtro = (
            "[0:v]split=2[a][b];"
            "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[fondo];"
            "[b]scale=1080:-2[juego];"
            "[fondo][juego]overlay=0:(H-h)/2[v0]"
        )
    if ass is not None:
        filtro += f";[v0]ass='{_ruta_filtro(ass)}'[v]"
    else:
        filtro += ";[v0]null[v]"
    destino.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-v", "error", "-y", "-ss", f"{inicio:.2f}", "-i", str(video),
        "-t", f"{duracion:.2f}", "-filter_complex", filtro, "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(destino),
    ]
    subprocess.run(cmd, check=True)
    return destino
