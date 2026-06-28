# SKILL — Wordlists (dicionários por idioma)

## Objetivo
Manter as listas em `wordlists/` e a lógica de seleção em `word_manager.py`.

## Formato
- `wordlists/Idioma.txt` = lista principal; `Idioma_sub.txt` = sublista (ex: `Português_palindromos`).
- 1 palavra por linha, **minúsculas**, acentos **preservados** (normalização é em runtime).
- Descoberta automática: `WordManager.get_languages()` lista arquivos sem `_`.

## Scripts de manutenção (raiz — modo one-off)
- `download_wordlists.py` — baixa/processa listas (FrequencyWords).
- `clean_wordlists.py` — remove palavras com chars inválidos.
- `lowercase_wordlists.py` / `normalize_wordlists.py` — caixa baixa / remove acentos.
- `process_words.py <arquivo>` — strip+lowercase de um arquivo.
- `organize_lists.py`, `filter_gentiles.py` — organização/filtragem.
- `check_words.py` — heurística p/ achar palavras erradas em Português.txt.

> Recomendação: ao criar novos utilitários, coloque em `tools/` com CLI/`--help` (ver `tools/README.md`).

## Lógica de seleção (resumo — ver BUSINESS_RULES)
- `get_word`: resolve idioma → sublista prioritária → candidatos (contém prompt / prefix-suffix) →
  filtros soft → estratégia.
- Índice por comprimento (`len_map`) acelera filtro de tamanho.
- `mark_used` evita repetição; `reset_used` recarrega do disco.

## Boas práticas
- Listas grandes (Português 248k): evite operações O(n) desnecessárias em loop; reuse `len_map`/`lower`.
- Ao editar listas, valide encoding UTF-8 e ausência de linhas em branco/duplicatas.
- Rode `tools/project_stats.py` para conferir tamanhos após mudanças.

## Anti-patterns
- ❌ Maiúsculas ou espaços extras nas listas.
- ❌ Remover acentos no arquivo (a normalização é feita em runtime; remover quebra a exibição).
- ❌ Duplicar palavras.

## Checklist (nova lista)
- [ ] Nome `Idioma.txt`. [ ] minúsculas, 1/linha. [ ] UTF-8. [ ] sem duplicatas/linhas vazias.
- [ ] Aparece em `/api/languages`. [ ] Documentado em FILE_INDEX (tamanhos).
