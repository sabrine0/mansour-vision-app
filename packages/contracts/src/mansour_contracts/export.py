"""Export the event contract as JSON Schema.

`packages/contracts` is the single source of truth. The Python services import
the pydantic models directly; the TypeScript dashboard consumes types generated
from these schemas. CI regenerates and diffs, so a contract change that is not
propagated to both sides fails the build rather than failing at 2am on the spine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from pydantic import TypeAdapter

from mansour_contracts.events import EVENT_TYPES, SCHEMA_VERSION, Event


def _strip_property_titles(node: Any) -> Any:
    """Remove pydantic's auto-generated per-property `title` keys.

    They carry no information (`"title": "Camera Id"` for a field named
    `camera_id`) and they cause every code generator to hoist each property into
    its own named type. The schema's meaning is unchanged; its generated output
    becomes legible.
    """
    if isinstance(node, dict):
        cleaned = {k: _strip_property_titles(v) for k, v in node.items() if k != "title"}
        return cleaned
    if isinstance(node, list):
        return [_strip_property_titles(item) for item in node]
    return node


def build_schemas() -> dict[str, dict[str, Any]]:
    """Return one JSON Schema per event type, keyed by file stem.

    These are the validators. A consumer that needs to check a single message
    against its declared type loads exactly one of these.
    """
    schemas: dict[str, dict[str, Any]] = {}
    for event_type, model in EVENT_TYPES.items():
        schema = model.model_json_schema(mode="serialization")
        properties = schema.get("properties", {})
        schema["properties"] = {k: _strip_property_titles(v) for k, v in properties.items()}
        schemas[event_type.replace(".", "_")] = schema
    return schemas


def build_bundle() -> dict[str, Any]:
    """One document describing the whole spine, with shared `$defs`.

    Code generators must consume this rather than the per-event files. Compiling
    the five schemas independently emits `DensityLevel`, `DetectionClass` and the
    rest once per file, and the concatenated result does not compile.
    """
    adapter: TypeAdapter[Event] = TypeAdapter(Event)
    raw = adapter.json_schema(mode="serialization", ref_template="#/$defs/{model}")
    bundle: dict[str, Any] = cast("dict[str, Any]", _strip_property_titles(raw))
    bundle["title"] = "SpineEvent"
    bundle["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    bundle["description"] = (
        "Every event carried on the MANSOUR Vision event spine (ADR 0007). "
        "No event carries a track identifier, a person identifier, an embedding, "
        "or any biometric attribute (ADR 0004)."
    )
    return bundle


def build_index() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_types": sorted(EVENT_TYPES),
    }


def write(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for stem, schema in build_schemas().items():
        path = out_dir / f"{stem}.schema.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)

    bundle = out_dir / "spine.schema.json"
    bundle.write_text(json.dumps(build_bundle(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written.append(bundle)

    index = out_dir / "index.json"
    index.write_text(json.dumps(build_index(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written.append(index)

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "schema",
        help="directory to write the schemas into",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the written schemas would differ from those on disk",
    )
    args = parser.parse_args(argv)

    if args.check:
        return _check(args.out)

    for path in write(args.out):
        print(f"wrote {path}")
    return 0


def _check(out_dir: Path) -> int:
    stale: list[str] = []

    for stem, schema in build_schemas().items():
        path = out_dir / f"{stem}.schema.json"
        expected = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            stale.append(path.name)

    bundle = out_dir / "spine.schema.json"
    expected_bundle = json.dumps(build_bundle(), indent=2, sort_keys=True) + "\n"
    if not bundle.exists() or bundle.read_text(encoding="utf-8") != expected_bundle:
        stale.append(bundle.name)

    index = out_dir / "index.json"
    expected_index = json.dumps(build_index(), indent=2, sort_keys=True) + "\n"
    if not index.exists() or index.read_text(encoding="utf-8") != expected_index:
        stale.append(index.name)

    if stale:
        print(f"schemas are out of date: {', '.join(sorted(stale))}", file=sys.stderr)
        print("run: python -m mansour_contracts.export", file=sys.stderr)
        return 1

    print("schemas are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
