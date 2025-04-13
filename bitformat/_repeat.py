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
    def from_params(cls, count: int | str | Expression, fieldtype: FieldType | str) -> Repeat:
        """
        Create a Repeat instance.

        :param count: An Expression or int giving the number of repetitions to do.
        :type count: int or str or Expression
        :param fieldtype: The FieldType to repeat.
        :type fieldtype: FieldType or str
        :return: The Repeat instance.
        :rtype: Repeat
        """
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
        if isinstance(fieldtype, str):
            fieldtype = FieldType.from_string(fieldtype)
        elif not isinstance(fieldtype, FieldType):
            raise ValueError(f"Invalid field of type {type(fieldtype)}.")
        x.field = fieldtype
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
        """
        Create a :class:`Repeat` instance from a string.

        The string should be of the form ``'repeat {expression}: fieldtype'``.
        The fieldtype can be a :class:`Format` to group multiple fields together.

        :param s: The string to parse.
        :type s: str
        :return: The Repeat instance.
        :rtype: Repeat

        .. code-block:: python

            r1 = Repeat.from_string('repeat {5}: u8')
            r2 = Repeat.from_string('repeat {x + 1}: (bool, f64)')

        """
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
        s = f"Repeat.from_params({self.count!r}, "
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

        # TODO: value_iter is unused, and this whole method looks a bit suspect.
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

    @override
    def clear(self) -> None:
        self._concrete_count = None
        self._bits_list = []

    @override
    def info(self) -> str:
        return f"Repeat with count of {self.count}."

    @override
    def is_stretchy(self) -> bool:
        return False

    @override
    def is_const(self) -> bool:
        return self.count.has_const_value and self.field.is_const()

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