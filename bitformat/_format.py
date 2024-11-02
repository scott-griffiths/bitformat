from __future__ import annotations

import sys

from ._bits import Bits
from typing import Sequence, Any, Iterable, TextIO
import copy
import re

from ._common import override, Indenter, Colour
from ._fieldtype import FieldType
from ._pass import Pass
from ._options import Options

__all__ = ['Format']

format_str_pattern = r"^(?:(?P<name>[^=]+)=)?\s*\((?P<content>.*)\)\s*$"
compiled_format_str_pattern = re.compile(format_str_pattern, re.DOTALL)


class Format(FieldType):
    """
    A sequence of :class:`FieldType` objects, used to group fields together.

    """

    def __new__(cls,  s: str | None = None) -> Format:
        if s is None:
            x = super().__new__(cls)
            x.fields = []
            x.name = ''
            x.vars = {}
            x._field_names = {}
            return x
        return cls.from_string(s)

    @classmethod
    def from_params(cls, fields: Sequence[FieldType | str] | None = None, name: str = '') -> Format:
        """
        Create a Format instance.

        :param fields: The field types to include in the format, optional.
        :type fields: Sequence[FieldType or str] or None
        :param name: The name of the format, optional.
        :type name: str
        :return: The Format instance.
        :rtype: Format
        """
        x = super().__new__(cls)
        x.fields = []
        if fields is None:
            fields = []
        x.name = name
        x.vars = {}
        x._field_names = {}
        stetchy_field = ''
        for fieldtype in fields:
            if stetchy_field:
                raise ValueError(f"A Field with no length can only occur at the end of a Format. Field '{stetchy_field}' is before the end.")
            if isinstance(fieldtype, FieldType):
                fieldtype = fieldtype._copy()
            elif isinstance(fieldtype, str):
                fieldtype = FieldType.from_string(fieldtype)
            else:
                raise ValueError(f"Invalid Field of type {type(fieldtype)}.")
            if fieldtype is Pass():
                # Don't bother appending if it's the Pass singleton.
                continue
            try:
                if fieldtype.bitlength == 0:
                    stetchy_field = str(fieldtype)
            except ValueError:
                pass
            x.fields.append(fieldtype)
            if fieldtype.name != '':
                x._field_names[fieldtype.name] = fieldtype
        return x

    @staticmethod
    def _parse_format_str(format_str: str) -> tuple[str, list[str], str]:
        if match := compiled_format_str_pattern.match(format_str):
            name = match.group('name')
            content = match.group('content')
        else:
            return '', [], f"Invalid Format string '{format_str}'. It should be in the form '(field1, field2, ...)' or 'name = (field1, field2, ...)'."
        name = '' if name is None else name.strip()
        field_strs = []
        # split by ',' but ignore any ',' that are inside ()
        start = 0
        inside_brackets = 0
        for i, p in enumerate(content):
            if p == '(':
                inside_brackets += 1
            elif p == ')':
                if inside_brackets == 0:
                    return '', [], f"Unbalanced parenthesis in Format string '({content})'."
                inside_brackets -= 1
            elif p == ',' or p == '\n':
                if inside_brackets == 0:
                    if s := content[start:i].strip():
                        field_strs.append(s)
                    start = i + 1
        if inside_brackets == 0:
            s = content[start:].strip()
            if len(field_strs) == 0:
                if s == '':
                    raise ValueError("Format strings must contain a comma even when empty. Try '(,)' instead.")
                else:
                    raise ValueError(f"Format strings must contain a comma even with only one item. Try '({content},)' instead.")
            if s:
                field_strs.append(s)
        if inside_brackets != 0:
            return '', [], f"Unbalanced parenthesis in Format string '[{content}]'."
        return name, field_strs, ''

    @classmethod
    @override
    def from_string(cls, s: str, /) -> Format:
        """
        Create a :class:`Format` instance from a string.

        The string should be of the form ``'(field1, field2, ...)'`` or ``'name = (field1, field2, ...)'``,
        with commas separating strings that will be used to create other :class:`FieldType` instances.

        At least one comma must be present, even if less than two fields are present.

        :param s: The string to parse.
        :type s: str
        :return: The Format instance.
        :rtype: Format

        .. code-block:: python

            f1 = Format.from_string('(u8, bool=True, val: i7)')
            f2 = Format.from_string('my_format = (float16,)')
            f3 = Format.from_string('(u16, another_format = ([u8; 64], [bool; 8]))')

        """
        name, field_strs, err_msg = cls._parse_format_str(s)
        if err_msg:
            raise ValueError(err_msg)

        fieldtypes = []
        for fs in field_strs:
            try:
                f = FieldType.from_string(fs)
            except ValueError as e:
                no_of_notes = len(getattr(e, '__notes__', []))
                max_notes = 2
                if no_of_notes < max_notes:
                    e.add_note(f" -- when parsing Format string '{s}'.")
                if no_of_notes == max_notes:
                    e.add_note(" -- ...")
                raise e
            else:
                fieldtypes.append(f)
        return cls.from_params(fieldtypes, name)

    @override
    def _getbitlength(self) -> int:
        """Return the total length of the Format in bits."""
        return sum(f.bitlength for f in self.fields)

    @override
    def _pack(self, values: Sequence[Any], index: int, _vars: dict[str, Any] | None = None,
              kwargs: dict[str, Any] | None = None) -> tuple[Bits, int]:
        values_used = 0
        for fieldtype in self.fields:
            _, v = fieldtype._pack(values[index], index + values_used, _vars, kwargs)
            values_used += v
        return self.to_bits(), values_used

    @override
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
        pos = startbit
        for fieldtype in self.fields:
            pos += fieldtype._parse(b, pos, vars_)
        return pos - startbit

    @override
    def _copy(self) -> Format:
        x = Format()
        x.name = self.name
        x.fields = [f._copy() for f in self.fields]
        x._field_names = {}
        for field in x.fields:
            if field.name != '':
                x._field_names[field.name] = field
        return x

    @override
    def clear(self) -> None:
        for fieldtype in self.fields:
            fieldtype.clear()

    @override
    def _getvalue(self) -> list[Any]:
        vals = []
        for i, f in enumerate(self.fields):
            if f.value is None:
                raise ValueError(f"When getting Format value, cannot find value of this field:\n{f}")
            vals.append(f.value)
        return vals

    @override
    def _setvalue(self, val: Sequence[Any]) -> None:
        if len(val) != len(self.fields):
            raise ValueError(f"Can't set {len(self.fields)} fields from {len(val)} values.")
        for fieldtype, v in zip(self.fields, val):
            fieldtype._setvalue(v)

    value = property(_getvalue, _setvalue)

    @override
    def to_bits(self) -> Bits:
        return Bits().join(fieldtype.to_bits() for fieldtype in self.fields)

    def __len__(self) -> int:
        return len(self.fields)

    def __getitem__(self, name: str) -> Any:
        try:
            return self._field_names[name]
        except KeyError:
            raise KeyError(f"Field with name '{name}' not found.")

    def __setitem__(self, name: str, value: str | FieldType) -> None:
        if isinstance(value, str):
            try:
                field = FieldType.from_string(value)
            except ValueError as e:
                raise ValueError(f"Can't set field from string: {e}") from None
        elif isinstance(value, FieldType):
            field = value
        else:
            raise ValueError(f"Can't create and set field from type '{type(value)}'.")
        for i in range(len(self.fields)):
            if self.fields[i].name == name:
                self.fields[i] = field
                return
        raise KeyError(f"Field with name '{name}' not found.")

    @override
    def _str(self, indent: Indenter) -> str:
        colour = Colour(not Options().no_color)
        name_str = '' if self.name == '' else f"{colour.green}{self.name}{colour.off} = "
        s = ''
        s += indent(f"{name_str}(\n")
        with indent:
            for i, fieldtype in enumerate(self.fields):
                s += fieldtype._str(indent)
        s += indent(')')
        return s

    @override
    def _repr(self) -> str:
        name_str = '' if self.name == '' else f", {self.name!r}"
        s = f"{self.__class__.__name__}.from_params(["
        for i, fieldtype in enumerate(self.fields):
            s += fieldtype._repr()
            if i != len(self.fields) - 1:
                s += ', '
        s += f"]{name_str})"
        return s

    def __iadd__(self, other: FieldType | str) -> Format:
        if isinstance(other, str):
            other = FieldType.from_string(other)
        if other.name != '':
            self._field_names[other.name] = other
        self.fields.append(copy.copy(other))
        return self

    def __copy__(self) -> Format:
        x = Format()
        x.name = self.name
        x.vars = self.vars
        x.fields = [copy.copy(f) for f in self.fields]
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

    @override
    def __eq__(self, other) -> bool:
        if not isinstance(other, Format):
            return False
        if self.name != other.name:
            return False
        if self.vars != other.vars:
            return False
        if self.fields != other.fields:
            return False
        return True


