from __future__ import annotations

from ._field import FieldType
from ._common import _indent, override
from typing import Sequence, Any
from ._bits import Bits

__all__ = ['Pass']


class Pass(FieldType):
    """
    An empty placeholder :cls:`FieldType`.

    A Pass field has no length and no value. It can be used in conditionals when no action is required.
    When used elsewhere in a Format it may be removed as an optimisation.

    It is usually created implicitly, for example in an :cls:`If` field when no ``else`` is provided.

    .. code-block:: python

    cond = If.from_parameters('{ x > 0 }', Pass(), 'bool')


    """

    def __new__(cls) -> Pass:
        x = super().__new__(cls)
        return x

    @classmethod
    @override
    def from_string(cls, s: str = '', /) -> Pass:
        if s != '':
            raise ValueError(f"The Pass field cannot be constructed from a string. Received '{s}'.")
        return cls()

    @override
    def __len__(self):
        return 0

    @override
    def _pack(self, values: Sequence[Any], index: int, _vars: dict[str, Any] | None = None,
              kwargs: dict[str, Any] | None = None) -> tuple[Bits, int]:
        return Bits(), 0

    @override
    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
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

