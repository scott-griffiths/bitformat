from __future__ import annotations

import re

from ._field import FieldType
from ._common import override, Indenter
from typing import Sequence, Any
from ._bits import Bits

__all__ = ["Repeat"]


class Repeat(FieldType):

    field: FieldType
    count: int

    def __new__(cls, s: str) -> Repeat:
        return cls.from_string(s)

    @classmethod
    def from_params(cls, count: int, field: FieldType | str, name: str = "") -> Repeat:
        x = super().__new__(cls)
        x.count = count
        x._name = name
        if isinstance(field, str):
            field = FieldType.from_string(field)
        elif not isinstance(field, FieldType):
            raise ValueError(f"Invalid field of type {type(field)}.")
        x.field = field
        return x

    @override
    def _get_bit_length(self) -> int:
        return self.field.bit_length * self.count

    @classmethod
    @override
    def from_string(cls, s: str) -> Repeat:
        x = super().from_string(s)
        if not isinstance(x, Repeat):
            raise ValueError(f"Can't parse Repeat field from '{s}'. Instead got '{x}'.")
        return x

    @override
    def _str(self, indent: Indenter, use_colour: bool) -> str:
        # TODO: name is not handled yet.
        count_str = str(self.count)
        s = indent(f"repeat{{{count_str}}}: {self.field._str(indent, use_colour)}")
        return s

    @override
    def _repr(self) -> str:
        count = self.count if self.count is not None else self.count_expression
        s = f"Repeat.from_params({count!r}, "
        s += self.field._repr()
        s += ")"
        return s

    @override
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
        if len(b) - startbit < self.bit_length:
            raise ValueError(
                f"Repeat field '{str(self)}' needs {self.bit_length} bits to parse, but {len(b) - startbit} were available."
            )
        self._bits = b[startbit : startbit + self.bit_length]
        for i in range(self.count):
            startbit += self.field._parse(b, startbit, vars_)
        return self.bit_length

    @override
    def _pack(self, value: Sequence[Any], vars_: dict[str, Any], kwargs: dict[str, Any]) -> None:
        bits_list = []
        for i in range(self.count):
            self.field._pack(value[i], vars_, kwargs)
            bits_list.append(self.field.to_bits())
        self._bits = Bits.from_joined(bits_list)

    @override
    def _copy(self) -> Repeat:
        x = self.__class__.from_params(self.count, self.field._copy(), self.name)
        return x

    @override
    def to_bits(self) -> Bits:
        return self._bits if self._bits is not None else Bits()

    def clear(self) -> None:
        self._bits = None

    @override
    def _get_value(self) -> list[Any] | None:
        if self._bits is None:
            return None
        values = []
        for i in range(self.count):
            value = self.field.unpack(self._bits[i * self.field.bit_length : (i + 1) * self.field.bit_length])
            values.append(value)
        return values

    @override
    def _set_value_with_kwargs(self, val: list[Any], kwargs: dict[str, Any]) -> None:
        self._values = val

    @override
    def __eq__(self, other) -> bool:
        if not isinstance(other, Repeat):
            return False
        if self.count != other.count:
            return False
        if self.field != other.field:
            return False
        return True

    @override
    def _get_name(self) -> None:
        return self._name

    @override
    def _set_name(self, name: str) -> None:
        # TODO: import this function!
        self._name = validate_name(name)