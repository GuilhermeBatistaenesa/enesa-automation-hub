from __future__ import annotations

import hashlib
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from fastapi import UploadFile
try:
    import yaml
except Exception:  # noqa: BLE001
    yaml = None

from app.core.config import get_settings

settings = get_settings()


@dataclass(slots=True)
class StoredArtifact:
    artifact_type: str
    absolute_path: str
    relative_path: str
    sha256: str


class ArtifactStorage(Protocol):
    async def save_robot_version_artifact(self, robot_id: UUID, version: str, upload: UploadFile) -> StoredArtifact:
        ...


class LocalArtifactStorage:
    async def save_robot_version_artifact(self, robot_id: UUID, version: str, upload: UploadFile) -> StoredArtifact:
        suffix = _resolve_suffix(upload.filename or "")
        artifact_type = "ZIP" if suffix == ".zip" else "EXE"
        destination_dir = Path(settings.artifacts_root) / "robots" / str(robot_id) / version
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_file = destination_dir / f"artifact{suffix}"

        upload.file.seek(0)
        with destination_file.open("wb") as output_file:
            shutil.copyfileobj(upload.file, output_file)

        sha256 = _file_sha256(destination_file)
        relative_path = destination_file.relative_to(Path(settings.artifacts_root)).as_posix()
        return StoredArtifact(
            artifact_type=artifact_type,
            absolute_path=str(destination_file.resolve()),
            relative_path=relative_path,
            sha256=sha256,
        )


def _resolve_suffix(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".zip"):
        return ".zip"
    if lowered.endswith(".exe"):
        return ".exe"
    raise ValueError("Only .zip and .exe artifacts are supported.")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def extract_required_env_keys_from_artifact(artifact_path: str, artifact_type: str) -> list[str]:
    if artifact_type != "ZIP":
        return []
    if yaml is None:
        return []
    path = Path(artifact_path)
    if not path.exists():
        return []

    try:
        with zipfile.ZipFile(path, "r") as zipped:
            robot_yaml_name = _find_robot_yaml(zipped.namelist())
            if not robot_yaml_name:
                return []
            with zipped.open(robot_yaml_name, "r") as handle:
                payload = yaml.safe_load(handle.read().decode("utf-8")) or {}
    except Exception:  # noqa: BLE001
        return []

    return _parse_required_env_keys(payload)


def _find_robot_yaml(names: list[str]) -> str | None:
    lowered = {item.lower(): item for item in names}
    for candidate in ("robot.yaml", "robot.yml", "./robot.yaml", "./robot.yml"):
        if candidate in lowered:
            return lowered[candidate]
    for original in names:
        base = original.split("/")[-1].lower()
        if base in {"robot.yaml", "robot.yml"}:
            return original
    return None


def _parse_required_env_keys(payload: dict) -> list[str]:
    keys: list[str] = []
    sections = [
        payload.get("required_env"),
        (payload.get("env") or {}).get("required") if isinstance(payload.get("env"), dict) else None,
        ((payload.get("requirements") or {}).get("env") if isinstance(payload.get("requirements"), dict) else None),
    ]
    for section in sections:
        if isinstance(section, list):
            for item in section:
                if isinstance(item, str) and item.strip():
                    keys.append(item.strip())
    return sorted(set(keys))


def get_artifact_storage() -> ArtifactStorage:
    return LocalArtifactStorage()
