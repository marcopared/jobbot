"""Local file-backed loaders for resume evidence inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.resumes._serialization import canonical_json_hash

SUPPORTED_INPUT_EXTENSIONS = (".yaml", ".yml", ".json", ".md", ".txt")


@dataclass(frozen=True)
class LocalInputRecord:
    """Normalized text record extracted from a local evidence source."""

    text: str
    tags: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    attributes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class LocalInputDocument:
    """Loaded local input document with normalized records."""

    path: Path
    format: str
    records: tuple[LocalInputRecord, ...]
    content_hash: str


def find_optional_input_file(base_dir: str | Path, base_name: str) -> Path | None:
    """Find a single optional input file by basename with deterministic extension precedence."""
    root = Path(base_dir)
    matches = [
        root / f"{base_name}{extension}"
        for extension in SUPPORTED_INPUT_EXTENSIONS
        if (root / f"{base_name}{extension}").is_file()
    ]
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous resume input for {base_name}: {[str(path) for path in matches]}"
        )
    return matches[0] if matches else None


def list_supported_input_files(directory: str | Path) -> tuple[Path, ...]:
    """List supported files in a directory with deterministic ordering."""
    root = Path(directory)
    if not root.is_dir():
        return ()
    return tuple(
        sorted(
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS
        )
    )


def load_local_input_document(path: str | Path) -> LocalInputDocument:
    """Load a yaml/json/md/txt local evidence document into normalized records."""
    resolved = Path(path)
    raw = resolved.read_text(encoding="utf-8")
    suffix = resolved.suffix.lower()

    if suffix in (".yaml", ".yml"):
        data = yaml.safe_load(raw)
        records = _records_from_structured_payload(data)
        format_name = "yaml"
        content_hash = canonical_json_hash({"format": format_name, "data": data}, length=32)
    elif suffix == ".json":
        data = yaml.safe_load(raw)
        records = _records_from_structured_payload(data)
        format_name = "json"
        content_hash = canonical_json_hash({"format": format_name, "data": data}, length=32)
    elif suffix == ".md":
        records = tuple(LocalInputRecord(text=text) for text in _extract_text_blocks(raw))
        format_name = "md"
        content_hash = canonical_json_hash(
            {"format": format_name, "blocks": [record.text for record in records]}, length=32
        )
    elif suffix == ".txt":
        records = tuple(LocalInputRecord(text=text) for text in _extract_text_blocks(raw))
        format_name = "txt"
        content_hash = canonical_json_hash(
            {"format": format_name, "blocks": [record.text for record in records]}, length=32
        )
    else:
        raise ValueError(f"Unsupported resume input format: {path}")

    return LocalInputDocument(
        path=resolved,
        format=format_name,
        records=records,
        content_hash=content_hash,
    )


def _records_from_structured_payload(payload: Any) -> tuple[LocalInputRecord, ...]:
    normalized = _normalize_structured_value(payload)
    return tuple(record for record in normalized if record.text.strip())


def _normalize_structured_value(value: Any) -> list[LocalInputRecord]:
    if value is None:
        return []
    if isinstance(value, str):
        return [LocalInputRecord(text=value.strip())] if value.strip() else []
    if isinstance(value, list):
        records: list[LocalInputRecord] = []
        for item in value:
            records.extend(_normalize_structured_value(item))
        return records
    if isinstance(value, dict):
        if "items" in value:
            return _normalize_structured_value(value.get("items"))
        if "bullets" in value:
            return _normalize_structured_value(value.get("bullets"))
        if "entries" in value:
            return _normalize_structured_value(value.get("entries"))
        if "projects" in value:
            return _normalize_structured_value(value.get("projects"))
        if "text" in value:
            text = str(value.get("text", "")).strip()
            if not text:
                return []
            tags = tuple(str(tag) for tag in _ensure_list(value.get("tags")))
            metrics = tuple(str(metric) for metric in _ensure_list(value.get("metrics")))
            attributes = tuple(
                sorted(
                    (
                        str(key),
                        str(raw_value),
                    )
                    for key, raw_value in value.items()
                    if key not in {"text", "tags", "metrics"}
                    and raw_value is not None
                    and not isinstance(raw_value, (dict, list))
                )
            )
            return [
                LocalInputRecord(
                    text=text,
                    tags=tags,
                    metrics=metrics,
                    attributes=attributes,
                )
            ]
        if "body" in value:
            return _normalize_structured_value(value.get("body"))
        if "content" in value:
            return _normalize_structured_value(value.get("content"))
    raise ValueError(f"Unsupported structured resume input payload: {value!r}")


def _extract_text_blocks(raw: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if current:
            block = " ".join(current).strip()
            if block:
                blocks.append(block)
            current = []

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if line.startswith(("# ", "## ", "### ")):
            flush()
            header = line.lstrip("#").strip()
            if header:
                current.append(header)
            continue
        if line.startswith(("- ", "* ")):
            flush()
            bullet = line[2:].strip()
            if bullet:
                blocks.append(bullet)
            continue
        current.append(line)

    flush()
    return blocks


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
