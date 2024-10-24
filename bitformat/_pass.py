from __future__ import annotations

from ._field import FieldType
from ._common import _indent, override
from typing import Sequence, Any
from ._bits import Bits

__all__ = ['Pass']


class Pass(FieldType):
    """
    An empty placeholder :class:`FieldType`.

    A Pass field has zero bitlength and no value. It can be used in conditionals when no action is required.
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
    def from_string(cls, s: str = '', /) -> Pass:
        if s != '':
            raise ValueError(f"The Pass field cannot be constructed from a string. Received '{s}'.")
        return cls()

    @override
    def _getbitlength(self):
        return 0

    @override
    def _pack(self, values: Sequence[Any], index: int, vars_: dict[str, Any] | None = None,
              kwargs: dict[str, Any] | None = None) -> tuple[Bits, int]:
        return Bits(), 0

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
    def _getvalue(self) -> Any:
        raise ValueError("A Pass field has no value to get.")

    @override
    def _setvalue(self, val: Any) -> None:
        raise ValueError("A Pass field cannot be set to a value.")

    @override
    def flatten(self) -> list[FieldType]:
        return []

    @override
    def _str(self, indent: int) -> str:
        s = f"{_indent(indent)}Pass"
        return s

    @override
    def _repr(self, indent: int) -> str:
        return f"{self._str(indent)}Pass()"

    @override
    def to_bits(self) -> Bits:
        return Bits()

    value = property(_getvalue, _setvalue)

