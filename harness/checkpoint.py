"""Immutable, uniquely-namespaced local agent checkpoints."""
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]
_VERSION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_PACKAGE_IMPORT_RE = re.compile(
    r"^\s*from\s+([A-Za-z_][A-Za-z0-9_]*)\.policy\s+import\s+agent\s*$",
    re.MULTILINE,
)
# review.md H2 — checkpoints used to default under runs/, which is entirely gitignored
# (consumable replay output); that erased the only record of every accepted regression
# baseline (v0/v1a/v1a'/v1b) from git history, with no way to reconstruct or bisect them.
DEFAULT_CHECKPOINT_ROOT = "checkpoints"


def _hash_package(package_dir: Path) -> str:
    digest = hashlib.sha256()
    # review.md L4: __pycache__ is copied into checkpoints (copytree, below) but must not
    # affect the fingerprint — it's derived, non-deterministic clutter, not source.
    files = (
        source
        for source in package_dir.rglob("*")
        if source.is_file() and "__pycache__" not in source.relative_to(package_dir).parts
    )
    for source in sorted(files, key=lambda path: path.relative_to(package_dir).as_posix()):
        digest.update(source.relative_to(package_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(source.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def agent_fingerprint(agent_spec) -> str:
    """Hash an agent package independently of its checkpoint package name.

    review.md H3: if `agent_spec` is a main.py sitting next to a manifest.json (i.e. a
    checkpoint produced by `create_checkpoint`), verify the checkpoint hasn't been modified
    since creation — a checkpoint edited by accident, a tool, or a merge must not silently
    pass as "the immutable vX" and quietly invalidate every gate compared against it.

    review.md L10 [edge case, not handled here]: this reads from disk every call, but a
    module already imported earlier in this same process (`sys.modules`) keeps running
    whatever it loaded at import time. That can only diverge from a fresh on-disk hash within
    one long-lived process reusing an in-process callable across an edit — never for the
    fresh-process CLI/compare() path this harness actually uses.
    """
    if not isinstance(agent_spec, str):
        identity = f"{getattr(agent_spec, '__module__', '')}:{getattr(agent_spec, '__qualname__', repr(agent_spec))}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    path = Path(agent_spec)
    if not (path.suffix == ".py" and path.exists()):
        return f"builtin:{agent_spec}"

    source = path.read_text(encoding="utf-8")
    match = _PACKAGE_IMPORT_RE.search(source)
    if match:
        package_dir = path.parent / match.group(1)
        if package_dir.is_dir():
            fingerprint = _hash_package(package_dir)
            manifest_path = path.parent / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("fingerprint") != fingerprint:
                    raise ValueError(
                        f"checkpoint at {path.parent} does not match its manifest "
                        f"(expected fingerprint {manifest.get('fingerprint')!r}, got "
                        f"{fingerprint!r}) — the checkpoint package was modified after "
                        "creation and is no longer the immutable version it claims to be"
                    )
            return fingerprint
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def create_checkpoint(
    version: str,
    *,
    source_root: PathLike = ".",
    checkpoint_root: PathLike = DEFAULT_CHECKPOINT_ROOT,
) -> Path:
    """Copy the current agent under a package name unique to ``version``."""
    if not _VERSION_RE.fullmatch(version):
        raise ValueError("version must start with a letter and contain only letters, digits, or underscores")

    source_root = Path(source_root).resolve()
    source_package = source_root / "agent"
    if not source_package.is_dir():
        raise FileNotFoundError(f"Agent package not found: {source_package}")

    destination = Path(checkpoint_root).resolve() / version
    if destination.exists():
        raise FileExistsError(f"Checkpoint already exists: {destination}")

    package_name = f"agent_checkpoint_{version}"
    destination.mkdir(parents=True)
    shutil.copytree(
        source_package,
        destination / package_name,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    main_source = (
        '"""Generated local benchmark checkpoint; not a submission entrypoint."""\n'
        f"from {package_name}.policy import agent\n"
    )
    main_path = destination / "main.py"
    main_path.write_text(main_source, encoding="utf-8")

    manifest = {
        "version": version,
        "package": package_name,
        "fingerprint": _hash_package(destination / package_name),
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return main_path
