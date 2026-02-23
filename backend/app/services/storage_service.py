from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from fastapi import UploadFile

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


def get_artifact_storage() -> ArtifactStorage:
    return LocalArtifactStorage()

