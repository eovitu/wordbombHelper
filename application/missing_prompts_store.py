"""Registro persistente de prompts confirmados sem palavra no dicionário.

Ferramenta de MANUTENÇÃO do dicionário: quando o solver não acha NENHUMA palavra para
um prompt já confirmado pelo pipeline, gravamos o prompt aqui (com contador de ocorrências)
para o usuário consultar depois e adicionar palavras à wordlist.

Não toca o pipeline de OCR nem o desempenho: só é chamado no caminho "Nenhuma palavra",
que é raro. Thread-safe; persiste em JSON entre execuções.
"""
import json
import logging
import os
import threading

logger = logging.getLogger(__name__)


class MissingPromptsStore:
    def __init__(self, store_file):
        self._store_file = store_file
        self._lock = threading.Lock()
        self._counts = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self._store_file):
                with open(self._store_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    self._counts = {str(k): int(v) for k, v in data.items()}
        except Exception as exc:
            logger.warning("missing_prompts: falha ao carregar (%s)", exc)

    def record(self, prompt):
        """Incrementa o contador do prompt e persiste. Dedup natural pela chave."""
        p = (prompt or "").strip().lower()
        if not p:
            return
        with self._lock:
            self._counts[p] = self._counts.get(p, 0) + 1
            try:
                with open(self._store_file, "w", encoding="utf-8") as fh:
                    json.dump(self._counts, fh, ensure_ascii=False, sort_keys=True, indent=0)
            except Exception as exc:
                logger.warning("missing_prompts: falha ao salvar (%s)", exc)

    def clear(self):
        """Esvazia o registro e apaga o arquivo persistido. Ferramenta de manutenção:
        usar depois de adicionar as palavras faltantes ao dicionário (senão a entrada
        antiga continua aparecendo e confunde)."""
        with self._lock:
            self._counts = {}
            try:
                if os.path.exists(self._store_file):
                    os.remove(self._store_file)
            except Exception as exc:
                logger.warning("missing_prompts: falha ao limpar %s (%s)", self._store_file, exc)

    def snapshot(self, limit=50):
        """Lista [{prompt, count}] ordenada por contagem desc (para exibir/consultar)."""
        with self._lock:
            items = sorted(self._counts.items(), key=lambda kv: (-kv[1], kv[0]))
            return [{"prompt": k, "count": v} for k, v in items[:limit]]

    def ordered_prompts(self):
        """Todos os prompts em MAIÚSCULAS, ordenados por contagem desc (export TXT)."""
        with self._lock:
            items = sorted(self._counts.items(), key=lambda kv: (-kv[1], kv[0]))
            return [k.upper() for k, _ in items]
