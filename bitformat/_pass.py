from __future__ import annotations

from ._field import FieldType
from ._common import override, Indenter
from typing import Any
from ._bits import Bits

__all__ = ["Pass"]


class Pass(FieldType):
    """
    An empty placeholder :class:`FieldType`.

    A Pass field has zero bit_length and no value. It can be used in conditionals when no action is required.
    When used elsewhere in a :class:`Format` it may be removed as an optimisation.
    All Pass fields are identical, so they are implemented as a singleton.

    It is usually created implicitly, for example in an :class:`If` field when no ``else`` field is provided.

    .. code-block:: python

        cond = If.from_params('{ x > 0 }', Pass(), 'bool')

    """

    # All Pass fields are the same, so we make it a singleton.
    _instance = None

    def __new__(cls) -> Pass:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    @override
    def from_params(cls, *args, **kwargs) -> FieldType:
        return cls()

    @override
    def _get_bit_length(self) -> int:
        return 0

    @override
    def _pack(self, value: Any, vars_: dict[str, Any], kwargs: dict[str, Any]) -> None:
        pass

    @override
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
        return 0

    @override
    def _copy(self) -> Pass:
        return self

    @override
    def clear(self) -> None:
        pass

    @override
    def _get_value(self) -> Any:
        raise ValueError("A Pass field has no value to get.")

    @override
    def _set_value_with_kwargs(self, val: Any, kwargs: dict[str, Any]) -> None:
        raise ValueError("A Pass field cannot be set to a value.")

    @override
    def _str(self, indent: Indenter, use_colour: bool) -> str:
        s = indent("pass")
        return s

    @override
    def _repr(self) -> str:
        return "pass"

    @override
    def to_bits(self) -> Bits:
        return Bits()

    @override
    def __eq__(self, other) -> bool:
        return isinstance(other, Pass)
