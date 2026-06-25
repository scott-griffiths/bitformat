from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Union

from tibs import Mutibs, Tibs

TibsLike = Union[Tibs, Mutibs, str, bytearray, bytes, memoryview, Iterable[Any]]


def tibs_from_any(value: TibsLike | None) -> Tibs:
    if isinstance(value, Tibs):
        return value
    if isinstance(value, Mutibs):
        return value.to_tibs()
    return Tibs(value)


def mutibs_from_any(value: TibsLike | None) -> Mutibs:
    if isinstance(value, Mutibs):
        return value.__copy__()
    if isinstance(value, Tibs):
        return value.to_mutibs()
    return Mutibs(value)


def tibs_to_padded_bytes(value: TibsLike) -> bytes:
    bits = tibs_from_any(value)
    padding = -len(bits) % 8
    if padding:
        bits = bits + Tibs.from_zeros(padding)
    return bits.to_bytes()
