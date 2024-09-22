from __future__ import annotations

from ._bits import Bits
from typing import Sequence, Any, Iterable
import copy
import re

from ._common import colour, _indent, override
from ._field import FieldType, Field

__all__ = ['Format']

format_str_pattern = r"^(?:(?P<name>[^=]+)=)?\s*\[(?P<content>.*)\]\s*$"
compiled_format_str_pattern = re.compile(format_str_pattern, re.DOTALL)


class Format(FieldType):
    """
    A sequence of :class:`FieldType` objects, used to group fields together.

    """

    def __new__(cls,  s: str | None = None) -> Format:
        if s is None:
            x = super().__new__(cls)
            x.fieldtypes = []
            x.name = ''
            x.vars = {}
            return x
        return cls.from_string(s)

    @classmethod
    def from_parameters(cls, fieldtypes: Sequence[FieldType | str] | None = None, name: str = '') -> Format:
        """
        Create a Format instance from parameters.

        :param fieldtypes: The field types to include in the format, optional.
        :type fieldtypes: Sequence[FieldType or str] or None
        :param name: The name of the format, optional.
        :type name: str
        :return: The Format instance.
        :rtype: Format
        """
        x = super().__new__(cls)
        x.fieldtypes = []
        if fieldtypes is None:
            fieldtypes = []
        x.name = name
        x.vars = {}
        for fieldtype in fieldtypes:
            if isinstance(fieldtype, str):
                fieldtype = Field.from_string(fieldtype)
            if not isinstance(fieldtype, FieldType):
                raise ValueError(f"Invalid Field of type {type(fieldtype)}.")
            x.fieldtypes.append(fieldtype)
        return x

    @staticmethod
    def _parse_format_str(format_str: str) -> tuple[str, list[str], str]:
        if match := compiled_format_str_pattern.match(format_str):
            name = match.group('name')
            content = match.group('content')
        else:
            return ('', [], f"Invalid Format string '{format_str}'. It should be in the form '[field1, field2, ...]' or 'name = [field1, field2, ...]'.")
        name = '' if name is None else name.strip()
        field_strs = []
        # split by ',' but ignore any ',' that are inside []
        start = 0
        inside_brackets = 0
        for i, p in enumerate(content):
            if p == '[':
                inside_brackets += 1
            elif p == ']':
                if inside_brackets == 0:
                    return ('', [], f"Unbalanced brackets in Format string '[{content}]'.")
                inside_brackets -= 1
            elif p == ',' or p == '\n':
                if inside_brackets == 0:
                    if s := content[start:i].strip():
                        field_strs.append(s)
                    start = i + 1
        if inside_brackets == 0 and start < len(content):
            if s := content[start:].strip():
                field_strs.append(s)
        if inside_brackets != 0:
            return ('', [], f"Unbalanced brackets in Format string '[{content}]'.")
        return name, field_strs, ''

    @classmethod
    def _from_field_strs(cls, name: str, field_strs: Sequence[str]) -> Format:
        fieldtypes = []
        for field_str in field_strs:
            fieldtypes.append(FieldType.from_string(field_str))
        return Format.from_parameters(fieldtypes, name)

    @classmethod
    @override
    def from_string(cls, s: str) -> Format:
        """
        Create a Format instance from a string.

        :param s: The string to parse.
        :type s: str
        :return: The Format instance.
        :rtype: Format
        """
        name, field_strs, err_msg = cls._parse_format_str(s)
        if err_msg:
            raise ValueError(err_msg)
        return cls._from_field_strs(name, field_strs)

    @override
    def __len__(self):
        """Return the total length of the Format in bits."""
        return sum(len(f) for f in self.fieldtypes)

    @override
    def _pack(self, values: Sequence[Any], index: int, _vars: dict[str, Any] | None = None,
              kwargs: dict[str, Any] | None = None) -> tuple[Bits, int]:
        values_used = 0
        for fieldtype in self.fieldtypes:
            _, v = fieldtype._pack(values[index], index + values_used, _vars, kwargs)
            values_used += v
        return self.to_bits(), values_used

    @override
    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        pos = 0
        for fieldtype in self.fieldtypes:
            pos += fieldtype._parse(b[pos:], vars_)
        return pos

    @override
    def clear(self) -> None:
        for fieldtype in self.fieldtypes:
            fieldtype.clear()

    @override
    def _getvalue(self) -> list[Any]:
        return [f.value for f in self.fieldtypes]

    @override
    def _setvalue(self, val: Sequence[Any]) -> None:
        if len(val) != len(self.fieldtypes):
            raise ValueError(f"Can't set {len(self.fieldtypes)} fields from {len(val)} values.")
        for fieldtype, v in zip(self.fieldtypes, val):
            fieldtype._setvalue(v)

    @override
    def to_bits(self) -> Bits:
        return Bits().join(fieldtype.to_bits() for fieldtype in self.fieldtypes)

    @override
    def flatten(self) -> list[FieldType]:
        # Just return a flat list of fields
        flattened_fields = []
        for fieldtype in self.fieldtypes:
            flattened_fields.extend(fieldtype.flatten())
        return flattened_fields

    def __getitem__(self, key) -> Any:
        if isinstance(key, int):
            fieldtype = self.fieldtypes[key]
            return fieldtype
        elif isinstance(key, slice):
            a = self.__class__()
            a.extend(self.fieldtypes[key])
            return a
        for fieldtype in self.fieldtypes:
            if fieldtype.name == key:
                return fieldtype
        raise KeyError(f"Field '{key}' not found.")

    def __setitem__(self, key, value) -> None:
        if isinstance(value, str):
            try:
                field = FieldType.from_string(value)
            except ValueError as e:
                raise ValueError(f"Can't set field from string: {e}") from None
        elif isinstance(value, FieldType):
            field = value
        else:
            raise ValueError(f"Can't create and set field from type '{type(value)}'.")
        if isinstance(key, int):
            self.fieldtypes[key] = field
            return
        for i in range(len(self.fieldtypes)):
            if self.fieldtypes[i].name == key:
                self.fieldtypes[i] = field
                return
        raise KeyError(f"Field '{key}' not found.")

    value = property(_getvalue, _setvalue)

    @override
    def _str(self, indent: int) -> str:
        name_str = '' if self.name == '' else f"{colour.green}{self.name}{colour.off} = "
        s = f"{_indent(indent)}{name_str}[\n"
        for i, fieldtype in enumerate(self.fieldtypes):
            s += fieldtype._str(indent + 1) + '\n'
        s += f"{_indent(indent)}]"
        return s

    @override
    def _repr(self, indent: int) -> str:
        name_str = '' if self.name == '' else f", {self.name!r}"
        s = f"{_indent(indent)}{self.__class__.__name__}.from_parameters([\n"
        for i, fieldtype in enumerate(self.fieldtypes):
            s += fieldtype._repr(indent + 1)
            if i != len(self.fieldtypes) - 1:
                s += ','
            s += '\n'
        s += f"{_indent(indent)}]{name_str})"
        return s

    def __iadd__(self, other: FieldType | str) -> Format:
        if isinstance(other, str):
            other = FieldType.from_string(other)
        self.fieldtypes.append(copy.copy(other))
        return self

    def __copy__(self) -> Format:
        x = Format()
        x.name = self.name
        x.vars = self.vars
        x.fieldtypes = [copy.copy(f) for f in self.fieldtypes]
        return x

    def __add__(self, other: FieldType | str) -> Format:
        """
        Add a field to a copy of the format.

        :param other: The field to add.
        :type other: FieldType or str
        :return: The updated format.
        :rtype: Format
        """
        x = copy.copy(self)
        x.__iadd__(other)
        return x

    def append(self, value: Any) -> None:
        """
        Append a field to the format.

        :param value: The field to append.
        :type value: Any
        """
        self.__iadd__(value)

    def extend(self, values: Iterable) -> None:
        """
        Extend the format with multiple fields.

        :param values: The fields to add.
        :type values: Iterable
        """
        for value in values:
            self.__iadd__(value)

#
# class Repeat(FieldType):
#
#     def __init__(self, count: int | str | Iterable, fieldtype: FieldType | str | Dtype | Bits | Sequence[FieldType | str]):
#         super().__init__()
#         self._bits = None
#         self.count = count
#         if isinstance(fieldtype, str):
#             self.fieldtype = Field.from_string(fieldtype)
#         elif isinstance(fieldtype, Bits):
#             self.fieldtype = Field.from_bits(fieldtype)
#         elif isinstance(fieldtype, Dtype):
#             self.fieldtype = Field(fieldtype)
#         elif isinstance(fieldtype, Sequence):
#             self.fieldtype = Format(fieldtype)
#         else:
#             self.fieldtype = fieldtype
#         if not isinstance(self.fieldtype, FieldType):
#             raise ValueError(f"Invalid Field of type {type(fieldtype)}.")
#         self._values = []
#
#     @classmethod
#     @override
#     def from_string(cls, s: str) -> Repeat:
#         return Repeat()  # TODO
#
#     @override
#     def _str(self, indent: int) -> str:
#         count_str = str(self.count)
#         count_str = f'({count_str})'
#
#         s = f"{_indent(indent)}{self.__class__.__name__}{count_str}\n"
#         s += self.fieldtype._str(indent + 1)
#         return s
#
#     @override
#     def _repr(self, indent: int) -> str:
#         count = self.count if self.count is not None else self.count_expression
#         s = f"{_indent(indent)}{self.__class__.__name__}({count!r},\n"
#         s += self.fieldtype._repr(indent + 1)
#         s += f"\n{_indent(indent)})"
#         return s
#
#     @override
#     def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
#         index = 0
#         if self.count_expression is not None:
#             self.count = self.count_expression.safe_eval(vars_)
#         if isinstance(self.count, int):
#             self.count = range(self.count)
#         for _ in self.count:
#             index += self.fieldtype.unpack(b[index:])
#             self._values.append(self.fieldtype.value)
#         return index
#
#     @override
#     def _pack(self, values: Sequence[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
#         self._bits = Bits()
#         if self.count_expression is not None:
#             self.count = self.count_expression.safe_eval(vars_)
#         if isinstance(self.count, int):
#             self.count = range(self.count)
#         values_used = 0
#         for _ in self.count:
#             bits, v = self.fieldtype._pack(values[0], index + values_used, vars_, kwargs)
#             self._bits += bits
#             values_used += v
#         return self._bits, values_used
#
#     @override
#     def flatten(self) -> list[FieldType]:
#         # TODO: This needs values in it. This won't work.
#         flattened_fields = []
#         for _ in self.count:
#             flattened_fields.extend(self.fieldtype.flatten())
#         return flattened_fields
#
#     @override
#     def to_bits(self) -> Bits:
#         return self._bits if self._bits is not None else Bits()
#
#     def clear(self) -> None:
#         self._bits = None
#
#     @override
#     def _getvalue(self) -> list[Any]:
#         return self._values
#
#     value = property(_getvalue, None)
