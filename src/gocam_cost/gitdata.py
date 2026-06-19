"""Acquire the noctua-models timeline from git history.

We only need git for the *timeline* (which model changed, when, in which commit).
A blobless `--shallow-since` clone gives the full per-file commit history in
~114 MB without any file contents; contents are fetched over HTTP (see fetch.py).
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import config as C


@dataclass(frozen=True)
class Version:
    model_id: str
    sha: str
    commit_time: str   # ISO8601 with tz offset
    blob_oid: str      # 40-char git blob oid for this version's file


def ensure_clone(clone_dir: Path = C.CLONE_DIR) -> Path:
    """Create the blobless shallow clone if absent. Returns the clone path."""
    if (clone_dir / ".git").exists():
        return clone_dir
    clone_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--no-checkout",
         f"--shallow-since={C.SHALLOW_SINCE}", C.CLONE_URL, str(clone_dir)],
        check=True,
    )
    return clone_dir


def _raw_log(clone_dir: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(clone_dir), "log", f"--since={C.WINDOW_START}",
         "--raw", "--no-abbrev", "--no-renames",
         "--pretty=format:@%H|%cI", "--", "models/"],
        check=True, capture_output=True, text=True,
    )
    return out.stdout


def enumerate_versions(clone_dir: Path = C.CLONE_DIR) -> list[Version]:
    """Native, non-bulk model versions in the window, newest-first by commit.

    Drops bulk pipeline commits (touching > BULK_THRESHOLD models) and any
    non-native model id.
    """
    versions: list[Version] = []
    sha = ts = None
    buf: list[tuple[str, str]] = []  # (blob_oid, path) for the current commit

    def flush() -> None:
        if not buf or len(buf) > C.BULK_THRESHOLD:
            return
        for oid, path in buf:
            mid = path[len("models/"):-len(".ttl")]
            if path.startswith("models/") and path.endswith(".ttl") and C.NATIVE_ID.match(mid):
                versions.append(Version(mid, sha, ts, oid))

    for line in _raw_log(clone_dir).splitlines():
        if line.startswith("@"):
            flush()
            buf = []
            sha, ts = line[1:].split("|", 1)
        elif line.startswith(":"):
            # :<oldmode> <newmode> <oldoid> <newoid> <status>\t<path>
            parts = line.split()
            new_oid, status = parts[3], parts[4]
            # skip deletions (file absent at this commit -> no content to fetch)
            if status.startswith("D") or set(new_oid) == {"0"}:
                continue
            path = line.split("\t", 1)[1] if "\t" in line else ""
            buf.append((new_oid, path))
    flush()
    return versions
