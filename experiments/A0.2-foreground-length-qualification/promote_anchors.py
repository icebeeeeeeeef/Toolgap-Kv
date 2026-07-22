"""Promote one passing foreground qualification bundle into a tracked anchor."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from qualification import BUNDLE_FILES, TARGET_FULL_PREFIX_TOKENS, promoted_anchor_from_bundle


def _read_bundle(directory: Path) -> dict[str, Any]:
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    return {
        name: json.loads((directory / name).read_text(encoding="utf-8"))
        for name in BUNDLE_FILES
    }


def _write_anchor(destination: Path, anchor: dict[str, Any]) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".foreground-anchor-", suffix=".json", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(anchor, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def promote(target: int, bundle_directory: Path, output: Path) -> dict[str, Any]:
    """Derive and publish one immutable tracked anchor from raw pass evidence."""
    if target not in TARGET_FULL_PREFIX_TOKENS:
        raise ValueError("target must be registered")
    anchor = promoted_anchor_from_bundle(_read_bundle(bundle_directory))
    if anchor["target_full_prefix_tokens"] != target:
        raise ValueError("requested target does not match bundle evidence")
    _write_anchor(output, anchor)
    return anchor


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, choices=TARGET_FULL_PREFIX_TOKENS, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    promote(args.target, args.bundle, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
