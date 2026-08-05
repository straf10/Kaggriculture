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


def _hash_package(package_dir: Path) -> str:
    digest = hashlib.sha256()
    for source in sorted(package_dir.rglob("*.py"), key=lambda path: path.as_posix()):
        digest.update(source.relative_to(package_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(source.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def agent_fingerprint(agent_spec) -> str:
    """Hash an agent package independently of its checkpoint package name."""
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
            return _hash_package(package_dir)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def create_checkpoint(
    version: str,
    *,
    source_root: PathLike = ".",
    checkpoint_root: PathLike = "runs/checkpoints",
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
    shutil.copytree(source_package, destination / package_name)
    main_source = (
        '"""Generated local benchmark checkpoint; not a submission entrypoint."""\n'
        f"from {package_name}.policy import agent\n"
    )
    main_path = destination / "main.py"
    main_path.write_text(main_source, encoding="utf-8")

    manifest = {
        "version": version,
        "package": package_name,
        "fingerprint": _hash_package(source_package),
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return main_path
