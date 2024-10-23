from __future__ import annotations

from ._bits import Bits
from typing import Sequence, Any, Iterable
import copy
import re

from ._common import colour, _indent, override
from ._field import FieldType, Field
from ._pass import Pass

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
            x.fieldtypes = []
            x.name = ''
            x.vars = {}
            return x
        return cls.from_string(s)

    @classmethod
    def from_params(cls, fieldtypes: Sequence[FieldType | str] | None = None, name: str = '') -> Format:
        """
        Create a Format instance.

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
        stetchy_field = ''
        for fieldtype in fieldtypes:
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
            x.fieldtypes.append(fieldtype)
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
    def _getbitlength(self):
        """Return the total length of the Format in bits."""
        return sum(f.bitlength for f in self.fieldtypes)

    bitlength = property(_getbitlength)

    @override
    def _pack(self, values: Sequence[Any], index: int, _vars: dict[str, Any] | None = None,
              kwargs: dict[str, Any] | None = None) -> tuple[Bits, int]:
        values_used = 0
        for fieldtype in self.fieldtypes:
            _, v = fieldtype._pack(values[index], index + values_used, _vars, kwargs)
            values_used += v
        return self.to_bits(), values_used

    @override
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
        pos = startbit
        for fieldtype in self.fieldtypes:
            pos += fieldtype._parse(b, pos, vars_)
        return pos - startbit

    @override
    def _copy(self) -> Format:
        x = Format()
        x.name = self.name
        x.fieldtypes = [f._copy() for f in self.fieldtypes]
        return x

    @override
    def clear(self) -> None:
        for fieldtype in self.fieldtypes:
            fieldtype.clear()

    @override
    def _getvalue(self) -> list[Any]:
        vals = []
        for i, f in enumerate(self.fieldtypes):
            if f.value is None:
                raise ValueError(f"When getting Format value, cannot find value of this field:\n{f}")
            vals.append(f.value)
        return vals

    @override
    def _setvalue(self, val: Sequence[Any]) -> None:
        if len(val) != len(self.fieldtypes):
            raise ValueError(f"Can't set {len(self.fieldtypes)} fields from {len(val)} values.")
        for fieldtype, v in zip(self.fieldtypes, val):
            fieldtype._setvalue(v)

    value = property(_getvalue, _setvalue)

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

    def __len__(self) -> int:
        return len(self.fieldtypes)

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
        raise KeyError(f"Field with name '{name}' not found.")


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

    @override
    def _str(self, indent: int) -> str:
        name_str = '' if self.name == '' else f"{colour.green}{self.name}{colour.off} = "
        s = f"{_indent(indent)}{name_str}(\n"
        for i, fieldtype in enumerate(self.fieldtypes):
            s += fieldtype._str(indent + 1) + '\n'
        s += f"{_indent(indent)})"
        return s

    @override
    def _repr(self, indent: int) -> str:
        name_str = '' if self.name == '' else f", {self.name!r}"
        s = f"{_indent(indent)}{self.__class__.__name__}.from_params((\n"
        for i, fieldtype in enumerate(self.fieldtypes):
            s += fieldtype._repr(indent + 1)
            if i != len(self.fieldtypes) - 1:
                s += ','
            s += '\n'
        s += f"{_indent(indent)}){name_str})"
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
