from __future__ import annotations

from ._fieldtype import FieldType
from ._common import override, Indenter, Expression
from typing import Sequence, Any
from ._bits import Bits

__all__ = ["Repeat"]


class Repeat(FieldType):

    field: FieldType
    count: Expression
    _concrete_count: int | None
    _bits_list: list[Bits]

    def __new__(cls, s: str) -> Repeat:
        return cls.from_string(s)

    @classmethod
    def from_params(cls, count: int | str | Expression, field: FieldType | str) -> Repeat:
        x = super().__new__(cls)
        if isinstance(count, str):
            count = Expression(count)
        if isinstance(count, int):
            count = Expression.from_int(count)
        x.count = count
        x._concrete_count = None
        if x.count.has_const_value:
            if isinstance(x.count.const_value, int):
                x._concrete_count = x.count.const_value
            else:
                raise ValueError(f"Repeat count must be an integer, not {type(x.count.const_value)}.")
        x._bits_list = []
        if isinstance(field, str):
            field = FieldType.from_string(field)
        elif not isinstance(field, FieldType):
            raise ValueError(f"Invalid field of type {type(field)}.")
        x.field = field
        return x

    @override
    def _get_bit_length(self) -> int:
        if self._concrete_count is None:
            raise ValueError("Repeat count is not concrete, cannot calculate bit length.")
        try:
            field_const_length = self.field.bit_length
        except ValueError:
            raise ValueError("Field being repeated does not have a concrete bit length.")
        return field_const_length * self._concrete_count

    @classmethod
    @override
    def from_string(cls, s: str) -> Repeat:
        x = super().from_string(s)
        if not isinstance(x, Repeat):
            raise ValueError(f"Can't parse Repeat field from '{s}'. Instead got '{x}'.")
        return x

    @override
    def _str(self, indent: Indenter, use_colour: bool) -> str:
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
    def _parse(self, b: Bits, startbit: int, kwargs: dict[str, Any]) -> int:
        self._bits_list = []
        pos = startbit
        if self._concrete_count is None:
            self._concrete_count = self.count.evaluate(kwargs)
        for i in range(self._concrete_count):
            pos += self.field._parse(b, pos, kwargs)
            self._bits_list.append(self.field.to_bits())
        return pos - startbit

    @override
    def _pack(self, values: Sequence[Any], kwargs: dict[str, Any]) -> None:
        self._bits_list = []
        if self._concrete_count is None:
            self._concrete_count = self.count.evaluate(kwargs)

        if self.field.value is not None:
            if len(values) > 0:
                raise ValueError("Values passed to Repeat will be unused as the field is constant.")
            # It's just a const value repeated.
            self._bits_list = [self.field.to_bits()] * self._concrete_count
            return

        value_iter = iter(values)
        for i in range(self._concrete_count):

            self.field._pack(values[i], kwargs)
            self._bits_list.append(self.field.to_bits())

    @override
    def _copy(self) -> Repeat:
        x = self.__class__.from_params(self.count, self.field._copy())
        return x

    @override
    def to_bits(self) -> Bits:
        return Bits.from_joined(self._bits_list)

    def clear(self) -> None:
        self._concrete_count = None
        self._bits_list = []

    @override
    def is_stretchy(self) -> bool:
        return False

    @override
    def _get_value(self) -> list[Any] | None:
        if not self._bits_list:
            return None
        return [self.field.unpack(bits) for bits in self._bits_list]

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
        return None

    @override
    def _set_name(self, name: str) -> None:
        raise AttributeError("The Repeat field has no 'name' property.")