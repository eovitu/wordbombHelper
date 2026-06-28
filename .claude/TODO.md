# TODO — Próximos passos sugeridos

> Sugestões da análise inicial. Não são ordens — priorize com o dono do projeto.

## Higiene / dívida técnica
- [ ] Mover scripts utilitários da raiz para `tools/` (ou `scripts/`) e dar-lhes CLI/`--help` uniformes.
- [ ] Remover/gitignore arquivos temporários versionados: `_check_line_out.txt`, `_np_names.txt`.
- [ ] Avaliar remoção de `overlay_manager.py` (shim vazio) e de `scratch/append_words_batch*` já consumidos.
- [ ] Resolver a duplicação de `presets_repository` (manter um caminho canônico).
- [ ] Fixar versões em `requirements.txt` (ou usar `pip freeze`/lock) para reprodutibilidade.

## Robustez
- [ ] Tornar caminhos independentes de CWD (usar paths relativos a `__file__` em `screen_reader.py`/`region_store.py`).
- [ ] Tornar `tess_lang` e os ranges HSV **configuráveis** (por idioma/tema do jogo).
- [ ] Permitir sílabas de 1 e 5+ chars no OCR (hoje restrito a 2–4).
- [ ] Refatorar `WordManager.get_word` (>170 linhas) em estratégias/pipeline de filtros.

## Qualidade
- [ ] Introduzir `pytest` e cobrir: `shared/parsing.py`, `WordManager.get_word` (com lista fixture), `PresetService`, `AutoplayStateService`.
- [ ] Promover `debug_typer.py` a testes determinísticos (seed do `random`).

## Documentação
- [ ] Atualizar `README.md` (remover "janela vermelha" Tk; descrever overlay HTML).
- [ ] Adicionar diagramas (fluxograma do auto-play) — pode usar `tools/` p/ gerar.

## Features (se desejado)
- [ ] Indicador visual de confiança do OCR no front.
- [ ] Histórico de palavras digitadas por partida.
- [ ] Suporte explícito ao modo Letter Link (já existe `Typer.drag_path`, sem UI/fluxo completo).
