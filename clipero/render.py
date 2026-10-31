"""Cortar un tramo del VOD y convertirlo a video vertical 1080x1920 con edición básica."""
from __future__ import annotations

import subprocess
from pathlib import Path

ANCHO, ALTO = 1080, 1920
JUEGO_ALTO = 1080        # alto del juego en el clip (se recortan los lados del 16:9)
ZOOM = 1.18              # acercamiento en el momento fuerte
FPS = 30


def _ruta_filtro(ruta: Path) -> str:
    """Escapa una ruta para usarla dentro de un filtro de ffmpeg (también en Windows)."""
    s = ruta.resolve().as_posix()
    return s.replace(":", r"\:").replace("'", r"\'")


def _zoom_expr(pico: float | None) -> str:
    """Acercamiento rápido 0.3 s antes del pico, se sostiene ~1.6 s y regresa suave."""
    if pico is None:
        return "1"
    a, b = pico - 0.3, pico + 1.6
    sube = f"clip((in_time-{a:.2f})/0.25,0,1)"
    baja = f"clip(({b:.2f}+0.5-in_time)/0.5,0,1)"
    return f"1+{ZOOM - 1:.2f}*{sube}*{baja}"


def vertical(video: Path, inicio: float, fin: float, destino: Path,
             facecam: dict | None = None, ass: Path | None = None,
             pico: float | None = None) -> Path:
    """Fondo desenfocado + juego grande al centro, zoom en el pico, facecam arriba si se pide.

    `pico` es el segundo del momento fuerte, relativo al inicio del clip.
    """
    duracion = fin - inicio
    ancho_juego = round(JUEGO_ALTO * 16 / 9 / 2) * 2
    zoom = _zoom_expr(pico)
    juego = (
        f"scale={ancho_juego}:{JUEGO_ALTO},crop={ANCHO}:{JUEGO_ALTO},"
        f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={ANCHO}x{JUEGO_ALTO}:fps={FPS}"
    )
    fondo = (f"scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,crop={ANCHO}:{ALTO},"
             "boxblur=24:2,eq=brightness=-0.12")
    if facecam:
        fc = facecam
        alto_cara = 560
        filtro = (
            "[0:v]fps=30,split=3[a][b][c];"
            f"[a]{fondo}[fondo];"
            f"[b]{juego}[juego];"
            f"[c]crop={fc['w']}:{fc['h']}:{fc['x']}:{fc['y']},scale={ANCHO}:{alto_cara}:force_original_aspect_ratio=increase,crop={ANCHO}:{alto_cara}[cara];"
            "[fondo][cara]overlay=0:0[t1];"
            f"[t1][juego]overlay=0:{alto_cara}[v0]"
        )
    else:
        filtro = (
            "[0:v]fps=30,split=2[a][b];"
            f"[a]{fondo}[fondo];"
            f"[b]{juego}[juego];"
            f"[fondo][juego]overlay=0:(H-h)/2[v0]"
        )
    if ass is not None:
        filtro += f";[v0]ass='{_ruta_filtro(ass)}'[v]"
    else:
        filtro += ";[v0]null[v]"
    destino.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-v", "error", "-y", "-ss", f"{inicio:.2f}", "-i", str(video),
        "-t", f"{duracion:.2f}", "-filter_complex", filtro, "-map", "[v]", "-map", "0:a?",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(destino),
    ]
    subprocess.run(cmd, check=True)
    return destino
