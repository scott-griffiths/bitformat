from __future__ import annotations

from ._field import FieldType
from ._common import override, Indenter
from typing import Sequence, Any
from ._bits import Bits

__all__ = ['Repeat']


class Repeat(FieldType):

    def __new__(cls, s: str) -> Repeat:
        return cls.from_string(s)

    @classmethod
    def from_params(cls, count: int, field: FieldType | str, name: str = '') -> Repeat:
        x = super().__new__(cls)
        x.count = count
        x.name = name
        if isinstance(field, str):
            field = FieldType.from_string(field)
        elif not isinstance(field, FieldType):
            raise ValueError(f"Invalid field of type {type(field)}.")
        x.field = field
        return x

    @override
    def _getbitlength(self) -> int:
        return self.field.bitlength * self.count

    @classmethod
    @override
    def from_string(cls, s: str) -> Repeat:
        # TODO: name is not handled yet.
        s = s.strip()
        if not s.startswith('Repeat(') or not s.endswith(')'):
            raise ValueError(f"Can't parse Repeat field from '{s}'")
        s = s[7:-1].strip()
        count, fieldtype = s.split(',', 1)
        count = int(count)
        fieldtype = FieldType.from_string(fieldtype)
        return cls.from_params(count, fieldtype)

    @override
    def _str(self, indent: Indenter) -> str:
        # TODO: name is not handled yet.
        count_str = str(self.count)
        s = indent(f"Repeat({count_str},\n")
        with indent:
            s += self.field._str(indent)
        s += indent(')')
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
        if len(b) - startbit < self.bitlength:
            raise ValueError(f"Repeat field '{str(self)}' needs {self.bitlength} bits to parse, but {len(b) - startbit} were available.")
        self._bits = b[startbit:startbit + self.bitlength]
        for i in range(self.count):
            startbit += self.field._parse(b, startbit, vars_)
        return self.bitlength

    @override
    def _pack(self, values: Sequence[Any], index: int, vars_: dict[str, Any] | None = None,
              kwargs: dict[str, Any] | None = None) -> tuple[Bits, int]:
        self._bits = Bits()
        values_used = 0
        for i in range(self.count):
            bits, v = self.field._pack(values[0], index + values_used, vars_, kwargs)
            self._bits += bits
            values_used += v
        return self._bits, values_used

    @override
    def flatten(self) -> list[FieldType]:
        # TODO: This needs values in it. This won't work.
        flattened_fields = []
        for _ in self.count:
            flattened_fields.extend(self.field.flatten())
        return flattened_fields

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
    def _getvalue(self) -> list[Any] | None:
        if self._bits is None:
            return None
        values = []
        for i in range(self.count):
            value = self.field.unpack(self._bits[i * self.field.bitlength:(i + 1) * self.field.bitlength])
            values.append(value)
        return values

    @override
    def _setvalue(self, val: list[Any]) -> None:
        self._values = val

    value = property(_getvalue, _setvalue)
