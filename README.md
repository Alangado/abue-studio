# Abue Studio

Sistema personal de Abue para convertir sus streams de Twitch (abuegod) en clips verticales y publicarlos en sus propias cuentas de TikTok, Instagram y Facebook.

- `docs/`: sitio público (GitHub Pages) con la página de la app, la política de privacidad y los términos que pide TikTok.
- `clipero/`: toma un VOD de Twitch, encuentra los momentos más intensos y los exporta como clips verticales 1080x1920 con subtítulos.

## Instalar en Windows (una sola vez)

1. Instala Python 3.11 o más nuevo desde https://www.python.org/downloads/ (marca "Add python to PATH").
2. Instala ffmpeg: abre PowerShell y corre `winget install Gyan.FFmpeg`.
3. En la carpeta del proyecto:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install faster-whisper   # para los subtítulos
```

## Usar el Clipero

```powershell
python -m clipero listar                      # tus VODs y cuáles ya tienen clips
python -m clipero procesar                    # el VOD más nuevo sin procesar
python -m clipero procesar --vod 2868862053   # uno en particular
python -m clipero procesar --con-facecam      # stream donde usaste cámara
```

Los clips quedan en `clips/<id del VOD>/` junto con `manifest.json`, donde cada clip empieza como `pendiente` hasta que lo apruebes.

## Ajustes (`config.yaml`)

- `clips.por_stream`, `clips.duracion`: cuántos clips y de cuántos segundos.
- `facecam`: el recuadro de tu cámara en el video original. Solo se usa con `--con-facecam`: la cámara va arriba y el juego abajo.
- `subtitulos.modelo`: `small` es buen balance; `medium` es más preciso pero más lento.
- `palabras_clave`: frases que, si las dices, suben el puntaje de ese momento.

## Cómo elige los momentos

Mide el volumen de cada segundo (gritos, disparos, emoción) y le suma puntos a los tramos donde dices alguna palabra clave. Toma los picos más altos con al menos 60 segundos entre ellos.
