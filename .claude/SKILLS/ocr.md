# SKILL — OCR e Visão Computacional

## Objetivo
Entender e ajustar a detecção de turno ("SUA VEZ") e a leitura da sílaba em `screen_reader.py`.

## Quando usar
Auto-play não detecta a vez, lê sílaba errada, falsos positivos, ou mudança de tema do jogo.

## Pipeline (`_capture_and_ocr`)
1. `mss.grab` da região calibrada (`turn_region`).
2. **Frame hash cache**: se bytes idênticos ao último, retorna resultado cacheado.
3. Crop de borda 12px (não detectar a moldura do overlay).
4. Máscaras HSV (amarelo/azul/vermelho) na imagem pequena → **early-exit** se quase sem cor.
5. Upscale 2x. Top Zone (0–65%) = prompt; Bottom Zone (55–100%) = indicador de turno.
6. Máscara de branco (letras) + cores → denoise (medianBlur) → inverte → Otsu threshold.
7. OCR Tesseract `por+eng`, `--psm 7`, whitelist A-Za-z, `--tessdata-dir tessdata`.
8. Turno: cor forte (>8000) OU cor moderada (>2000)+keyword. Sílaba: candidato 2–4 letras com confiança.

## Parâmetros que você vai mexer
- Ranges HSV (`lower_/upper_` yellow/blue/red/white) — dependem do tema do jogo.
- Thresholds de pixels (100 early-exit, 1000/2000/8000 turno).
- Faixa de tamanho da sílaba (2–4).
- Thresholds de confiança (55 / 35+cor).
- `tess_lang` se jogar em outro idioma.

## Boas práticas
- Ative `screen_reader.save_debug_screenshots = True` e inspecione `debug_screenshots/last_processed.png`.
- Use `tools/ocr_extract.py` para testar Tesseract numa imagem isolada antes de mexer no pipeline.
- Ajuste um parâmetro por vez; verifique com a tela real.
- Preserve as proteções: frame cache, ghost-prompt, confirm streaks.

## Anti-patterns
- ❌ Baixar thresholds a ponto de detectar o fundo como turno.
- ❌ Remover o crop de borda (passa a ler a própria moldura).
- ❌ Assumir resolução/zoom fixos sem testar.

## Checklist de troubleshooting
- [ ] Região calibrada cobre prompt + "SUA VEZ"? (`calibration_region.json`)
- [ ] Tesseract instalado e no caminho? (`pytesseract.pytesseract.tesseract_cmd`)
- [ ] Cores do tema batem com os ranges HSV?
- [ ] Sílaba tem 2–4 letras?
- [ ] `last_processed.png` mostra texto legível?
