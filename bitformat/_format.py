from __future__ import annotations

from ._bits import Bits
from typing import Sequence, Any, Iterable, Self
import copy
from ._common import override, Indenter, Colour, validate_name
from ._fieldtype import FieldType
from ._pass import Pass



__all__ = ["Format"]


class Format(FieldType):
    """
    A sequence of :class:`FieldType` objects, used to group fields together.

    """
    _name: str
    _fields: list[FieldType]
    _field_names: dict[str, FieldType]
    vars: dict[str, Any]

    def __new__(cls, s: str | None = None) -> Self:
        if s is None:
            x = super().__new__(cls)
            x._fields = []
            x.name = ""
            x.vars = {}
            x._field_names = {}
            return x
        return cls.from_string(s)

    @classmethod
    def from_params(cls, fields: Sequence[FieldType | str] | None = None, name: str = "") -> Self:
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
        x._fields = []
        if fields is None:
            fields = []
        x.name = name
        x.vars = {}
        x._field_names = {}
        stretchy_field = ""
        for fieldtype in fields:
            if stretchy_field:
                raise ValueError(f"A Field with unknown length may only occur at the end of a Format. "
                                 f"Field '{stretchy_field}' is before the end.")
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
                if fieldtype.is_stretchy():
                    stretchy_field = str(fieldtype)
            except ValueError:
                pass
            x._fields.append(fieldtype)
            if (field_name := fieldtype.get_name()) is not None:
                x._field_names[field_name] = fieldtype
        return x


    @classmethod
    @override
    def from_string(cls, s: str, /) -> Self:
        """
        Create a :class:`Format` instance from a string.

        The string should be of the form ``'{field1, field2, ...}'`` or ``'name = {field1, field2, ...}'``,
        with commas separating strings that will be used to create other :class:`FieldType` instances.

        :param s: The string to parse.
        :type s: str
        :return: The Format instance.
        :rtype: Format

        .. code-block:: python

            f1 = Format.from_string('{u8, bool=True, val: i7}')
            f2 = Format.from_string('my_format = {float16,}')
            f3 = Format.from_string('{u16, another_format = {[u8; 64], [bool; 8]}}')

        """
        x = super().from_string(s)
        if not isinstance(x, Format):
            raise ValueError(f"Can't parse Format field from '{s}'. Instead got '{x}'.")
        return x

    @override
    def _get_bit_length(self) -> int:
        """Return the total length of the Format in bits."""
        return sum(f.bit_length for f in self._fields)

    @override
    def _pack(self, values: Sequence[Any], _vars: dict[str, Any], kwargs: dict[str, Any]) -> None:
        if not isinstance(values, Sequence):
            raise TypeError(f"Format.pack needs a sequence to pack, but received {type(values)}.")

        fields = iter(self._fields)
        for value in values:
            next_field = next(fields)
            while hasattr(next_field, 'const') and next_field.const:
                next_field = next(fields)
            next_field._pack(value, _vars, kwargs)

    @override
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
        pos = startbit
        for fieldtype in self._fields:
            pos += fieldtype._parse(b, pos, vars_)
        return pos - startbit

    @override
    def _copy(self) -> Format:
        x = Format()
        x.name = self.name
        x._fields = [f._copy() for f in self._fields]
        x._field_names = {}
        for field in x._fields:
            if field.name != "":
                x._field_names[field.name] = field
        return x

    @override
    def clear(self) -> None:
        for fieldtype in self._fields:
            fieldtype.clear()

    @override
    def _get_value(self) -> list[Any]:
        vals = []
        for i, f in enumerate(self._fields):
            if f.value is None:
                raise ValueError(f"When getting Format value, cannot find value of this field:\n{f}")
            vals.append(f.value)
        return vals

    @override
    def _set_value_with_kwargs(self, val: Sequence[Any], kwargs: dict[str, Any]) -> None:
        if len(val) != len(self._fields):
            raise ValueError(f"Can't set {len(self._fields)} fields from {len(val)} values.")
        for fieldtype, v in zip(self._fields, val):
            fieldtype._set_value_with_kwargs(v, kwargs)

    @override
    def to_bits(self) -> Bits:
        return Bits().from_joined(fieldtype.to_bits() for fieldtype in self._fields)

    def __len__(self) -> int:
        return len(self._fields)

    def __getitem__(self, key: slice | str | int) -> Any:
        if isinstance(key, int):
            return self._fields[key]
        if isinstance(key, slice):
            return self.__class__.from_params(self._fields[key])
        try:
            return self._field_names[key]
        except KeyError:
            raise KeyError(f"Field with name '{key}' not found.")

    def __setitem__(self, key: slice | str | int, value: str | FieldType) -> None:
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
            self._fields[key] = field
        elif isinstance(key, slice):
            self._fields[key] = field
        elif isinstance(key, str):
            for i in range(len(self._fields)):
                if self._fields[i].name == key:
                    self._fields[i] = field
                    return
            raise KeyError(f"Field with name '{key}' not found.")
        else:
            raise TypeError(f"Invalid key type {type(key)}.")

    def __delitem__(self, key: slice | int | str):
        if isinstance(key, int):
            del self._fields[key]
        elif isinstance(key, slice):
            del self._fields[key]
        elif isinstance(key, str):
            for i in range(len(self._fields)):
                # TODO: Can we use _field_names here?
                if self._fields[i].name == key:
                    del self._fields[i]
                    return
            raise KeyError(f"Field with name '{key}' not found.")
        else:
            raise TypeError(f"Invalid key type {type(key)}.")

    @override
    def _str(self, indent: Indenter, use_colour: bool) -> str:
        colour = Colour(use_colour)
        name_str = (
            "" if self.name == "" else f"{colour.name}{self.name}{colour.off} = "
        )
        s = ""
        s += indent(f"{name_str}{{\n")
        with indent:
            for i, fieldtype in enumerate(self._fields):
                s += fieldtype._str(indent, use_colour)
        s += indent("}")
        return s

    @override
    def _repr(self) -> str:
        name_str = "" if self.name == "" else f", {self.name!r}"
        s = f"{self.__class__.__name__}.from_params(["
        for i, fieldtype in enumerate(self._fields):
            s += fieldtype._repr()
            if i != len(self._fields) - 1:
                s += ", "
        s += f"]{name_str})"
        return s

    def __iadd__(self, other: FieldType | str) -> Format:
        if isinstance(other, str):
            other = FieldType.from_string(other)
        if other.name != "":
            self._field_names[other.name] = other
        self._fields.append(copy.copy(other))
        return self

    def __copy__(self) -> Format:
        x = Format()
        x.name = self.name
        x.vars = self.vars
        x._fields = [copy.copy(f) for f in self._fields]
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
        if self._fields != other._fields:
            return False
        return True

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = validate_name(name)