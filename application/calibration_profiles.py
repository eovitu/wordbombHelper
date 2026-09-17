"""Perfis locais de calibração para as regiões do prompt e do painel SOLVE.

O serviço não conhece Flask, ScreenReader ou os stores atuais. A camada de rota escolhe
quando ativar um perfil e aplica as duas regiões aos seus consumidores.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import threading
import unicodedata
import uuid

from shared.parsing import normalize_capture_region


class CalibrationProfilesError(Exception):
    """Erro base para dados persistidos ou operações de perfis."""


class CalibrationProfileValidationError(CalibrationProfilesError):
    """Dados de perfil inválidos; nenhuma alteração foi persistida."""


class CalibrationProfileNotFoundError(CalibrationProfilesError):
    """O perfil solicitado não existe."""


_UNSET = object()


class CalibrationProfiles:
    """CRUD persistente e atômico de perfis de regiões de captura.

    A região principal é obrigatória. A região SOLVE é opcional porque o scanner do
    painel já é opcional no produto, mas quando informada passa pela mesma validação.
    """

    VERSION = 1

    def __init__(self, store_file: str | Path = "calibration_profiles.json") -> None:
        self._store_file = Path(store_file)
        self._lock = threading.RLock()
        self._profiles: dict[str, dict[str, object]] = {}
        self._active_profile_id: str | None = None
        with self._lock:
            self._load_locked()

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str):
            raise CalibrationProfileValidationError("O nome do perfil deve ser texto.")
        value = unicodedata.normalize("NFC", name)
        if not value or value != value.strip() or len(value) > 80:
            raise CalibrationProfileValidationError("Informe um nome de perfil entre 1 e 80 caracteres.")
        if any(char in value for char in "\x00\r\n"):
            raise CalibrationProfileValidationError("O nome do perfil contém caracteres inválidos.")
        return value

    @staticmethod
    def _validate_region(region, label: str, required: bool):
        if region is None and not required:
            return None
        normalized = normalize_capture_region(region)
        if not normalized:
            suffix = " é obrigatória" if required else " é inválida"
            raise CalibrationProfileValidationError("A região " + label + suffix + ".")
        return normalized

    @staticmethod
    def _copy_profile(profile: dict[str, object], active: bool) -> dict[str, object]:
        return {
            "id": profile["id"],
            "name": profile["name"],
            "turn_region": dict(profile["turn_region"]),
            "solve_region": dict(profile["solve_region"]) if profile["solve_region"] else None,
            "active": active,
        }

    def list_profiles(self) -> list[dict[str, object]]:
        """Retorna cópias dos perfis, por nome, incluindo o marcador ``active``."""
        with self._lock:
            return [
                self._copy_profile(profile, profile_id == self._active_profile_id)
                for profile_id, profile in sorted(
                    self._profiles.items(), key=lambda item: (str(item[1]["name"]).casefold(), item[0])
                )
            ]

    def get_profile(self, profile_id: str) -> dict[str, object]:
        with self._lock:
            profile = self._profile_locked(profile_id)
            return self._copy_profile(profile, profile_id == self._active_profile_id)

    def get_active_profile(self) -> dict[str, object] | None:
        with self._lock:
            if self._active_profile_id is None:
                return None
            profile = self._profiles.get(self._active_profile_id)
            if profile is None:
                return None
            return self._copy_profile(profile, True)

    def create(self, name: str, turn_region, solve_region=None) -> dict[str, object]:
        """Cria um perfil e retorna sua cópia; o primeiro perfil vira o ativo."""
        validated_name = self._validate_name(name)
        validated_turn = self._validate_region(turn_region, "do prompt", required=True)
        validated_solve = self._validate_region(solve_region, "do painel SOLVE", required=False)
        with self._lock:
            self._ensure_name_available_locked(validated_name)
            profile_id = uuid.uuid4().hex
            self._profiles[profile_id] = {
                "id": profile_id,
                "name": validated_name,
                "turn_region": validated_turn,
                "solve_region": validated_solve,
            }
            if self._active_profile_id is None:
                self._active_profile_id = profile_id
            self._persist_locked()
            return self._copy_profile(self._profiles[profile_id], profile_id == self._active_profile_id)

    def update(self, profile_id: str, *, name=_UNSET, turn_region=_UNSET, solve_region=_UNSET) -> dict[str, object]:
        """Atualiza somente os campos informados. ``solve_region=None`` remove a região."""
        with self._lock:
            profile = self._profile_locked(profile_id)
            next_name = profile["name"] if name is _UNSET else self._validate_name(name)
            if next_name != profile["name"]:
                self._ensure_name_available_locked(next_name, excluding_id=profile_id)
            next_turn = profile["turn_region"] if turn_region is _UNSET else self._validate_region(
                turn_region, "do prompt", required=True)
            next_solve = profile["solve_region"] if solve_region is _UNSET else self._validate_region(
                solve_region, "do painel SOLVE", required=False)
            profile.update({"name": next_name, "turn_region": next_turn, "solve_region": next_solve})
            self._persist_locked()
            return self._copy_profile(profile, profile_id == self._active_profile_id)

    def delete(self, profile_id: str) -> None:
        """Remove um perfil; ao apagar o ativo, deixa a aplicação sem perfil ativo."""
        with self._lock:
            self._profile_locked(profile_id)
            del self._profiles[profile_id]
            if self._active_profile_id == profile_id:
                self._active_profile_id = None
            self._persist_locked()

    def activate(self, profile_id: str) -> dict[str, object]:
        """Marca um perfil existente como ativo e o retorna."""
        with self._lock:
            profile = self._profile_locked(profile_id)
            self._active_profile_id = profile_id
            self._persist_locked()
            return self._copy_profile(profile, True)

    def _profile_locked(self, profile_id: str) -> dict[str, object]:
        if not isinstance(profile_id, str) or not profile_id:
            raise CalibrationProfileNotFoundError("Perfil de calibração não encontrado.")
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise CalibrationProfileNotFoundError("Perfil de calibração não encontrado.")
        return profile

    def _ensure_name_available_locked(self, name: str, excluding_id: str | None = None) -> None:
        normalized = name.casefold()
        if any(
            profile_id != excluding_id and str(profile["name"]).casefold() == normalized
            for profile_id, profile in self._profiles.items()
        ):
            raise CalibrationProfileValidationError("Já existe um perfil com esse nome.")

    def _load_locked(self) -> None:
        if not self._store_file.exists():
            return
        try:
            raw = json.loads(self._store_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CalibrationProfilesError("Não foi possível ler os perfis de calibração.") from exc
        if not isinstance(raw, dict) or raw.get("version") != self.VERSION or not isinstance(raw.get("profiles"), list):
            raise CalibrationProfilesError("O arquivo de perfis de calibração é inválido.")
        loaded: dict[str, dict[str, object]] = {}
        for item in raw["profiles"]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
                raise CalibrationProfilesError("O arquivo de perfis de calibração é inválido.")
            profile_id = item["id"]
            if profile_id in loaded:
                raise CalibrationProfilesError("O arquivo de perfis de calibração contém IDs duplicados.")
            try:
                name = self._validate_name(item.get("name"))
                turn_region = self._validate_region(item.get("turn_region"), "do prompt", required=True)
                solve_region = self._validate_region(item.get("solve_region"), "do painel SOLVE", required=False)
            except CalibrationProfileValidationError as exc:
                raise CalibrationProfilesError("O arquivo de perfis de calibração é inválido.") from exc
            if any(existing["name"].casefold() == name.casefold() for existing in loaded.values()):
                raise CalibrationProfilesError("O arquivo de perfis de calibração contém nomes duplicados.")
            loaded[profile_id] = {
                "id": profile_id,
                "name": name,
                "turn_region": turn_region,
                "solve_region": solve_region,
            }
        active = raw.get("active_profile_id")
        if active is not None and active not in loaded:
            raise CalibrationProfilesError("O perfil ativo persistido não existe.")
        self._profiles = loaded
        self._active_profile_id = active

    def _persist_locked(self) -> None:
        payload = {
            "version": self.VERSION,
            "active_profile_id": self._active_profile_id,
            "profiles": [
                {
                    "id": profile["id"],
                    "name": profile["name"],
                    "turn_region": profile["turn_region"],
                    "solve_region": profile["solve_region"],
                }
                for _, profile in sorted(self._profiles.items())
            ],
        }
        self._store_file.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix="." + self._store_file.name + ".", suffix=".tmp", dir=self._store_file.parent, text=True
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self._store_file)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
