"""Deterministic ids are what make at-least-once delivery idempotent (ADR 0007)."""

from __future__ import annotations

import pytest

from mansour_common.ids import correlation_id, deterministic_id, new_id


def test_new_id_is_unique() -> None:
    assert len({new_id() for _ in range(1000)}) == 1000


def test_deterministic_id_is_stable_across_calls() -> None:
    first = deterministic_id("camera.tick", "cam-14", 1_752_000_000)
    second = deterministic_id("camera.tick", "cam-14", 1_752_000_000)
    assert first == second


def test_deterministic_id_is_stable_across_processes() -> None:
    """Pinned literal. If this changes, every consumer's deduplication silently
    breaks on deploy, because redelivered events get new ids and insert twice."""
    assert str(deterministic_id("camera.tick", "cam-14", 1_752_000_000)) == (
        "ced9a856-ecf3-52ff-99c1-853bc078a9a8"
    )


def test_deterministic_id_varies_with_every_part() -> None:
    base = deterministic_id("camera.tick", "cam-14", 1)
    assert deterministic_id("zone.tick", "cam-14", 1) != base
    assert deterministic_id("camera.tick", "cam-15", 1) != base
    assert deterministic_id("camera.tick", "cam-14", 2) != base


def test_deterministic_id_is_not_ambiguous_across_part_boundaries() -> None:
    """('a|b', 'c') and ('a', 'b|c') must not collide, whatever separator is used."""
    assert deterministic_id("a|b", "c") != deterministic_id("a", "b|c")
    assert deterministic_id("a\x1f", "b") != deterministic_id("a", "\x1fb")


def test_deterministic_id_accepts_ints_and_strs_interchangeably() -> None:
    assert deterministic_id("x", 1) == deterministic_id("x", "1")


def test_deterministic_id_requires_parts() -> None:
    with pytest.raises(ValueError, match="at least one part"):
        deterministic_id()


def test_correlation_id_is_hex_and_unique() -> None:
    value = correlation_id()
    assert len(value) == 32
    int(value, 16)
    assert value != correlation_id()
