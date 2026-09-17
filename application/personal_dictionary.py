"""Dicionário pessoal local, separado das wordlists distribuídas com o projeto.

Cada idioma é persistido em um arquivo UTF-8 próprio. O módulo não conhece HTTP nem
WordManager: quem fizer a integração pode chamar :meth:`get_words` para compor a
lista em memória sem alterar os arquivos rastreados em ``wordlists/``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import threading
import unicodedata
from typing import Iterable, Mapping


class PersonalDictionaryError(Exception):
    """Erro base para operações do dicionário pessoal."""


class ValidationError(PersonalDictionaryError):
    """Entrada inválida; nenhum arquivo foi alterado."""


class NotFoundError(PersonalDictionaryError):
    """A palavra solicitada não existe no idioma informado."""


class UndoUnavailableError(PersonalDictionaryError):
    """Não há uma operação local anterior que possa ser desfeita."""


@dataclass(frozen=True)
class ImportPreview:
    """Resultado imutável de uma prévia de importação.

    ``new_words`` contém somente entradas válidas que ainda não pertenciam ao
    idioma. ``duplicates`` inclui repetidas no arquivo importado ou já presentes.
    Linhas são numeradas a partir de 1 para a UI exibir erros com precisão.
    """

    language: str
    new_words: tuple[str, ...]
    duplicates: tuple[tuple[int, str], ...]
    invalid_lines: tuple[tuple[int, str, str], ...]


class PersonalDictionary:
    """Armazena palavras pessoais por idioma com escrita atômica e undo persistente."""

    _UNDO_FILE = ".last_undo.json"

    def __init__(self, storage_dir: str | Path = "personal_wordlists") -> None:
        self.storage_dir = Path(storage_dir)
        self._lock = threading.RLock()

    @staticmethod
    def validate_language(language: str) -> str:
        if not isinstance(language, str):
            raise ValidationError("O idioma deve ser texto.")
        if language != language.strip():
            raise ValidationError("O idioma contém caracteres inválidos.")
        value = unicodedata.normalize("NFC", language)
        if not value:
            raise ValidationError("Informe um idioma.")
        if any(char in value for char in "<>:\"/\\|?*\x00\r\n") or value in {".", ".."}:
            raise ValidationError("O idioma contém caracteres inválidos.")
        return value

    @staticmethod
    def validate_word(word: str) -> str:
        """Valida uma única palavra compatível com as wordlists atuais.

        Espaços, quebras de linha, números e símbolos são recusados. Letras Unicode,
        hífen e apóstrofo são aceitos porque aparecem nas listas do jogo.
        """
        if not isinstance(word, str):
            raise ValidationError("A palavra deve ser texto.")
        value = unicodedata.normalize("NFC", word)
        if not value:
            raise ValidationError("A palavra não pode estar vazia.")
        if value != value.strip() or any(char.isspace() for char in value):
            raise ValidationError("Informe exatamente uma palavra, sem espaços ou linhas extras.")
        value = value.replace("’", "'").replace("‘", "'").replace("´", "'").replace("`", "'")
        if not any(char.isalpha() for char in value):
            raise ValidationError("A palavra precisa conter ao menos uma letra.")
        if any(not (char.isalpha() or char in "-'") for char in value):
            raise ValidationError("A palavra só pode conter letras, hífen e apóstrofo.")
        return value.lower()

    def get_words(self, language: str) -> list[str]:
        """Retorna uma cópia das palavras pessoais daquele idioma, na ordem gravada."""
        language = self.validate_language(language)
        with self._lock:
            return list(self._read_words_locked(language))

    def add(self, language: str, word: str) -> str:
        language = self.validate_language(language)
        word = self.validate_word(word)
        with self._lock:
            before = self._read_words_locked(language)
            if word in before:
                raise ValidationError("A palavra já existe no dicionário pessoal.")
            after = [*before, word]
            self._replace_words_and_record_undo_locked(language, before, after, "add")
        return word

    def prepend(self, language: str, word: str) -> str:
        """Adiciona no topo para que palavras aprendidas automaticamente sejam revisáveis."""
        language = self.validate_language(language)
        word = self.validate_word(word)
        with self._lock:
            before = self._read_words_locked(language)
            if word in before:
                raise ValidationError("A palavra já existe no dicionário pessoal.")
            self._replace_words_and_record_undo_locked(
                language, before, [word, *before], "automatic_add")
        return word

    def edit(self, language: str, previous_word: str, replacement_word: str) -> str:
        language = self.validate_language(language)
        previous_word = self.validate_word(previous_word)
        replacement_word = self.validate_word(replacement_word)
        with self._lock:
            before = self._read_words_locked(language)
            try:
                index = before.index(previous_word)
            except ValueError as exc:
                raise NotFoundError("A palavra original não existe no dicionário pessoal.") from exc
            if replacement_word != previous_word and replacement_word in before:
                raise ValidationError("A palavra substituta já existe no dicionário pessoal.")
            after = list(before)
            after[index] = replacement_word
            self._replace_words_and_record_undo_locked(language, before, after, "edit")
        return replacement_word

    def delete(self, language: str, word: str) -> None:
        language = self.validate_language(language)
        word = self.validate_word(word)
        with self._lock:
            before = self._read_words_locked(language)
            try:
                before.index(word)
            except ValueError as exc:
                raise NotFoundError("A palavra não existe no dicionário pessoal.") from exc
            after = [item for item in before if item != word]
            self._replace_words_and_record_undo_locked(language, before, after, "delete")

    def preview_import(self, language: str, text: str) -> ImportPreview:
        language = self.validate_language(language)
        if not isinstance(text, str):
            raise ValidationError("O conteúdo importado deve ser texto.")
        with self._lock:
            existing = set(self._read_words_locked(language))
        new_words: list[str] = []
        duplicates: list[tuple[int, str]] = []
        invalid_lines: list[tuple[int, str, str]] = []
        seen = set(existing)
        # Colagens vindas de listas costumam separar palavras por espaço ou por linha.
        # Cada token de espaço em branco representa uma palavra independente.
        tokens = text.split()
        for line_number, line in enumerate(tokens, start=1):
            try:
                word = self.validate_word(line)
            except ValidationError as exc:
                invalid_lines.append((line_number, line, str(exc)))
                continue
            if word in seen:
                duplicates.append((line_number, word))
                continue
            seen.add(word)
            new_words.append(word)
        # splitlines() devolve [] para texto vazio, mas uma importação vazia deve ser
        # explicitamente visível para a UI e não virar uma operação de undo vazia.
        if not tokens:
            invalid_lines.append((1, "", "A palavra não pode estar vazia."))
        return ImportPreview(language, tuple(new_words), tuple(duplicates), tuple(invalid_lines))

    def apply_import(self, preview: ImportPreview) -> list[str]:
        """Aplica uma prévia limpa como uma única operação passível de undo.

        A prévia precisa ter sido criada para este módulo. Linhas inválidas impedem
        toda a importação, evitando persistência parcial por um arquivo malformado.
        """
        if not isinstance(preview, ImportPreview):
            raise ValidationError("Use o resultado de preview_import para importar.")
        if preview.invalid_lines:
            raise ValidationError("Corrija as linhas inválidas antes de importar.")
        language = self.validate_language(preview.language)
        proposed = self._validated_unique_words(preview.new_words)
        with self._lock:
            before = self._read_words_locked(language)
            existing = set(before)
            additions = [word for word in proposed if word not in existing]
            if not additions:
                return []
            after = [*before, *additions]
            self._replace_words_and_record_undo_locked(language, before, after, "import")
        return additions

    def undo(self) -> Mapping[str, object]:
        """Desfaz a operação mutável mais recente, inclusive após reiniciar o processo."""
        with self._lock:
            record = self._read_undo_locked()
            if record is None:
                raise UndoUnavailableError("Não há operação para desfazer.")
            language = self.validate_language(record.get("language"))
            before = record.get("before")
            if not isinstance(before, list) or any(not isinstance(word, str) for word in before):
                raise PersonalDictionaryError("O registro de undo está inválido.")
            words = self._validated_unique_words(before)
            self._write_words_atomic_locked(language, words)
            self._undo_path.unlink(missing_ok=True)
            return {"operation": record.get("operation"), "language": language, "words": list(words)}

    def _replace_words_and_record_undo_locked(
        self, language: str, before: list[str], after: list[str], operation: str
    ) -> None:
        self._write_words_atomic_locked(language, after)
        self._write_json_atomic_locked(
            self._undo_path,
            {"operation": operation, "language": language, "before": before},
        )

    @property
    def _undo_path(self) -> Path:
        return self.storage_dir / self._UNDO_FILE

    def _word_path(self, language: str) -> Path:
        return self.storage_dir / f"{language}.txt"

    def _read_words_locked(self, language: str) -> list[str]:
        path = self._word_path(language)
        if not path.exists():
            return []
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PersonalDictionaryError(f"Não foi possível ler {path.name}.") from exc
        if content and not content.endswith("\n"):
            raise PersonalDictionaryError(f"{path.name} não termina com quebra de linha UTF-8 válida.")
        lines = content.splitlines()
        return self._validated_unique_words(lines)

    def _validated_unique_words(self, words: Iterable[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for word in words:
            validated = self.validate_word(word)
            if validated in seen:
                raise PersonalDictionaryError("O arquivo do dicionário contém palavras duplicadas.")
            seen.add(validated)
            result.append(validated)
        return result

    def _write_words_atomic_locked(self, language: str, words: Iterable[str]) -> None:
        verified = self._validated_unique_words(words)
        payload = "".join(f"{word}\n" for word in verified)
        self._write_text_atomic_locked(self._word_path(language), payload)

    def _read_undo_locked(self) -> dict[str, object] | None:
        path = self._undo_path
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PersonalDictionaryError("O registro de undo está corrompido.") from exc
        if not isinstance(data, dict):
            raise PersonalDictionaryError("O registro de undo está inválido.")
        return data

    def _write_json_atomic_locked(self, path: Path, data: object) -> None:
        self._write_text_atomic_locked(path, json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")

    def _write_text_atomic_locked(self, path: Path, content: str) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=self.storage_dir, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
            # A sincronização do diretório melhora a durabilidade em plataformas POSIX.
            if hasattr(os, "O_DIRECTORY"):
                try:
                    directory_fd = os.open(str(self.storage_dir), os.O_DIRECTORY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                except OSError:
                    pass
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
