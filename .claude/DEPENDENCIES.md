# DEPENDENCIES

Em [`requirements.txt`](../requirements.txt) (sem versões fixadas — o projeto é enxuto e local).

| Pacote | Para quê | Usado em |
|---|---|---|
| **flask** | Web server local + templates + rotas. | `app_factory.py`, `api/routes.py`, `shared/parsing.py`, `shared/security.py` |
| **pyautogui** | Pressionar teclas/Alt+Tab, mover/clicar mouse (drag_path), FAILSAFE. | `typer.py` |
| **keyboard** | Escrever texto (`keyboard.write`), hook global da tecla Insert (abort). | `typer.py` |
| **pytesseract** | Wrapper do Tesseract OCR (lê sílaba e "SUA VEZ"). | `screen_reader.py` |
| **Pillow (PIL)** | Converter arrays/numpy ↔ imagem para o Tesseract. | `screen_reader.py` |
| **pynput** | Listener de cliques de mouse durante a calibração. | `screen_reader.py` |
| **opencv-python (cv2)** | Visão: conversão de cor, máscaras HSV, resize, threshold, blur. | `screen_reader.py` |
| **numpy** | Arrays de pixels, ranges de cor HSV. | `screen_reader.py` |
| **mss** | Captura de tela rápida da região calibrada. | `screen_reader.py` |

## Dependência de sistema (não-pip)
- **Tesseract OCR** instalado no SO + traineddata `por`/`eng`. No Windows procura
  `C:\Program Files\Tesseract-OCR\tesseract.exe`; senão usa PATH. Em Unix tenta
  `/usr/bin`, `/usr/local/bin`, `/opt/homebrew/bin`, senão PATH. Os traineddata também estão versionados em [`tessdata/`](../tessdata/) e são passados via `--tessdata-dir`.

## Stdlib relevante
`threading` (locks, threads, eventos), `logging`, `json`, `os`, `unicodedata` (normalização de acentos),
`random`, `time`, `platform`, `shutil`, `dataclasses`, `functools.wraps`.

## Observações
- **Sem dependências de teste** (pytest etc.) — não há suíte automatizada.
- **Sem dependências de build/front** — front-end é vanilla, servido estático pelo Flask.
- Antes de adicionar qualquer pacote novo, confirme necessidade real (princípio "enxuto").
- `pyautogui`/`keyboard`/`pynput` são **específicas de ambiente desktop** — não rodam em servidor headless. Isso reforça que a ferramenta é local.
