"""File hashing helpers."""
from __future__ import annotations

import hashlib
from pathlib import Path


def compute_checksum(path: Path, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """Return the hex digest for a file."""

    hasher = hashlib.new(algorithm)
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
