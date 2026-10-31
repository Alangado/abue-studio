"""Transcripción con faster-whisper (opcional) y subtítulos ASS palabra por palabra."""
from __future__ import annotations

from pathlib import Path

# Vocabulario que ayuda a Whisper a escribir bien la jerga del stream.
CONTEXTO = ("Stream de Warzone en español de México. Rebirth, loadout, clutch, compa, "
            "no mames, wey, torneo, squad, gulag, killfeed, rotar, pushear.")

PALABRAS_POR_LINEA = 3
PAUSA_CORTE = 0.45  # segundos de silencio que cortan una línea


def disponible() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def transcribir(audio, modelo: str = "small", idioma: str = "es") -> list[dict]:
    """Recibe audio mono 16 kHz (numpy float32).

    Devuelve segmentos [{inicio, fin, texto, palabras: [{inicio, fin, texto}]}].
    """
    from faster_whisper import WhisperModel

    m = WhisperModel(modelo, device="auto", compute_type="int8")
    segmentos, _ = m.transcribe(audio, language=idioma, vad_filter=True,
                                word_timestamps=True, initial_prompt=CONTEXTO,
                                condition_on_previous_text=False)
    salida = []
    for s in segmentos:
        palabras = [{"inicio": w.start, "fin": w.end, "texto": w.word.strip()}
                    for w in (s.words or []) if w.word.strip()]
        salida.append({"inicio": s.start, "fin": s.end, "texto": s.text.strip(), "palabras": palabras})
    return salida


def _tiempo_ass(seg: float) -> str:
    seg = max(0.0, seg)
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _escapar(texto: str) -> str:
    return texto.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _lineas(palabras: list[dict]) -> list[list[dict]]:
    """Agrupa palabras en líneas cortas, cortando en pausas y al llegar al máximo."""
    lineas, actual = [], []
    for w in palabras:
        if actual and (len(actual) >= PALABRAS_POR_LINEA or w["inicio"] - actual[-1]["fin"] > PAUSA_CORTE):
            lineas.append(actual)
            actual = []
        actual.append(w)
    if actual:
        lineas.append(actual)
    return lineas


def escribir_ass(segmentos: list[dict], inicio: float, fin: float, destino: Path,
                 gancho: str | None = None) -> Path:
    """Subtítulos del tramo [inicio, fin] con tiempos relativos al clip.

    Muestra 1 a 3 palabras a la vez, en mayúsculas, y resalta en amarillo la
    palabra que se está diciendo. `gancho` va arriba durante los primeros 3 s.
    """
    cabecera = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Arial Black,86,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,7,3,2,60,60,330,1
Style: Gancho,Arial Black,72,&H00FFFFFF,&H000000FF,&H00000000,&HC0000000,-1,0,0,0,100,100,0,0,3,18,0,8,70,70,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    eventos = []
    if gancho:
        eventos.append(f"Dialogue: 2,{_tiempo_ass(0)},{_tiempo_ass(3)},Gancho,,0,0,0,,"
                       f"{{\\fad(0,250)}}{_escapar(gancho).upper()}")
    palabras = [w for s in segmentos for w in s.get("palabras", [])
                if w["fin"] > inicio and w["inicio"] < fin]
    for linea in _lineas(palabras):
        textos = [_escapar(w["texto"]).upper() for w in linea]
        for i, w in enumerate(linea):
            a = max(w["inicio"], inicio) - inicio
            # cada palabra se queda hasta que empieza la siguiente de la línea
            b = (linea[i + 1]["inicio"] if i + 1 < len(linea) else w["fin"]) - inicio
            b = min(max(b, a + 0.08), fin - inicio)
            partes = [("{\\c&H00E5FF&}" + t + "{\\c&HFFFFFF&}") if j == i else t
                      for j, t in enumerate(textos)]
            pop = "{\\fscx108\\fscy108\\t(0,90,\\fscx100\\fscy100)}" if i == 0 else ""
            eventos.append(f"Dialogue: 0,{_tiempo_ass(a)},{_tiempo_ass(b)},Sub,,0,0,0,,{pop}{' '.join(partes)}")
    destino.write_text(cabecera + "\n".join(eventos) + "\n", encoding="utf-8")
    return destino
