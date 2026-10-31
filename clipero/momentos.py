"""Encontrar los momentos más intensos de un stream.

Se usa el volumen del audio segundo a segundo (gritos, disparos, emoción) y,
si hay transcripción, las palabras clave que dijo Abue.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

MUESTRAS = 16000  # Hz
UMBRAL_QUIETO = 8.0  # movimiento promedio debajo del cual la pantalla se considera menú o lobby


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


def movimiento_por_segundo(video: Path, fps: int = 2) -> np.ndarray:
    """Cuánto cambia la imagen cada segundo (0 = pantalla quieta, como menús o lobby)."""
    ancho, alto = 64, 36
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-an",
           "-vf", f"fps={fps},scale={ancho}:{alto},format=gray", "-f", "rawvideo", "-"]
    crudo = subprocess.run(cmd, check=True, capture_output=True).stdout
    cuadros = np.frombuffer(crudo, dtype=np.uint8).reshape(-1, alto, ancho).astype(np.float32)
    if len(cuadros) < 2:
        return np.zeros(len(cuadros) // fps)
    dif = np.abs(np.diff(cuadros, axis=0)).mean(axis=(1, 2))
    dif = np.concatenate([[dif[0]], dif])
    segundos = len(dif) // fps
    return dif[: segundos * fps].reshape(segundos, fps).mean(axis=1)


def puntaje(volumen_db: np.ndarray, segmentos: list[dict] | None = None,
            palabras_clave: list[str] | None = None, movimiento: np.ndarray | None = None,
            ventana: int = 5) -> np.ndarray:
    """Puntaje por segundo: volumen normalizado y suavizado, bonos por palabras clave,
    y castigo a los tramos sin acción en pantalla (menús, lobby, pantallas de carga)."""
    if len(volumen_db) == 0:
        return volumen_db
    z = (volumen_db - np.median(volumen_db)) / (np.std(volumen_db) + 1e-6)
    kernel = np.ones(ventana) / ventana
    p = np.convolve(z, kernel, mode="same")
    if movimiento is not None and len(movimiento):
        n = min(len(p), len(movimiento))
        mov = np.convolve(movimiento[:n], np.ones(15) / 15, mode="same")
        quieto = mov < UMBRAL_QUIETO
        p = p[:n]
        p[quieto] -= 4.0
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
