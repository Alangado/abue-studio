"""Encontrar los momentos más intensos de un stream.

Se usa el volumen del audio segundo a segundo (gritos, disparos, emoción) y,
si hay transcripción, las palabras clave que dijo Abue.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

MUESTRAS = 16000  # Hz


def leer_audio(video: Path) -> np.ndarray:
    """Audio mono a 16 kHz como float32 entre -1 y 1."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1",
           "-ar", str(MUESTRAS), "-f", "s16le", "-"]
    crudo = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(crudo, dtype=np.int16).astype(np.float32) / 32768.0


def volumen_por_segundo(audio: np.ndarray) -> np.ndarray:
    """Energía (RMS en dB) de cada segundo de audio."""
    segundos = len(audio) // MUESTRAS
    if segundos == 0:
        return np.zeros(0)
    bloques = audio[: segundos * MUESTRAS].reshape(segundos, MUESTRAS)
    rms = np.sqrt(np.mean(bloques ** 2, axis=1)) + 1e-9
    return 20 * np.log10(rms)


def puntaje(volumen_db: np.ndarray, segmentos: list[dict] | None = None,
            palabras_clave: list[str] | None = None, ventana: int = 5) -> np.ndarray:
    """Puntaje por segundo: volumen normalizado y suavizado, más bonos por palabras clave."""
    if len(volumen_db) == 0:
        return volumen_db
    z = (volumen_db - np.median(volumen_db)) / (np.std(volumen_db) + 1e-6)
    kernel = np.ones(ventana) / ventana
    p = np.convolve(z, kernel, mode="same")
    if segmentos and palabras_clave:
        claves = [c.lower() for c in palabras_clave]
        for s in segmentos:
            texto = s["texto"].lower()
            hits = sum(texto.count(c) for c in claves)
            if hits:
                ini, fin = int(s["inicio"]), int(s["fin"]) + 1
                p[ini:fin] += 1.5 * hits
    return p


def elegir_momentos(p: np.ndarray, cuantos: int, duracion: int, antes: int,
                    separacion: int) -> list[dict]:
    """Elige los picos más altos sin que los clips se encimen."""
    total = len(p)
    if total == 0:
        return []
    orden = np.argsort(p)[::-1]
    elegidos: list[int] = []
    for t in orden:
        if all(abs(int(t) - e) >= separacion for e in elegidos):
            elegidos.append(int(t))
        if len(elegidos) >= cuantos:
            break
    momentos = []
    for pico in sorted(elegidos):
        inicio = max(0, pico - antes)
        fin = min(total, inicio + duracion)
        inicio = max(0, fin - duracion)
        momentos.append({"inicio": float(inicio), "fin": float(fin), "pico": float(pico),
                         "puntaje": round(float(p[pico]), 2)})
    return momentos
