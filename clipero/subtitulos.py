"""Transcripción con faster-whisper (opcional) y subtítulos ASS para los clips."""
from __future__ import annotations

from pathlib import Path


def disponible() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def transcribir(audio, modelo: str = "small", idioma: str = "es") -> list[dict]:
    """Recibe audio mono 16 kHz (numpy float32) y devuelve segmentos [{inicio, fin, texto}]."""
    from faster_whisper import WhisperModel

    m = WhisperModel(modelo, device="auto", compute_type="int8")
    segmentos, _ = m.transcribe(audio, language=idioma, vad_filter=True)
    return [{"inicio": s.start, "fin": s.end, "texto": s.text.strip()} for s in segmentos]


def _tiempo_ass(seg: float) -> str:
    seg = max(0.0, seg)
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _escapar(texto: str) -> str:
    return texto.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def escribir_ass(segmentos: list[dict], inicio: float, fin: float, destino: Path,
                 gancho: str | None = None) -> Path:
    """Subtítulos del tramo [inicio, fin], con tiempos relativos al clip.

    `gancho` se muestra arriba durante los primeros 3 segundos.
    """
    cabecera = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,5,0,2,60,60,420,1
Style: Gancho,Arial,72,&H0000F0FF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,0,8,60,60,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lineas = []
    if gancho:
        lineas.append(f"Dialogue: 1,{_tiempo_ass(0)},{_tiempo_ass(3)},Gancho,,0,0,0,,{_escapar(gancho)}")
    for s in segmentos:
        if s["fin"] <= inicio or s["inicio"] >= fin:
            continue
        a = max(s["inicio"], inicio) - inicio
        b = min(s["fin"], fin) - inicio
        lineas.append(f"Dialogue: 0,{_tiempo_ass(a)},{_tiempo_ass(b)},Sub,,0,0,0,,{_escapar(s['texto'])}")
    destino.write_text(cabecera + "\n".join(lineas) + "\n", encoding="utf-8")
    return destino
