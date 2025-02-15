from __future__ import annotations

import lark.exceptions

from ._bits import Bits
from typing import Sequence, Any, Iterable, Self
import copy
from ._common import override, Indenter, Colour, lark_parser
from ._fieldtype import FieldType
from ._field import Field
from ._dtypes import Dtype, DtypeArray, DtypeSingle, Expression, DtypeName
from ._pass import Pass
from ._repeat import Repeat
from ._if import If
from ._options import Options
from lark import Transformer, UnexpectedInput


__all__ = ["Format"]


class FormatTransformer(Transformer):
    def format(self, items) -> Format:
        items = [i for i in items if i is not None]

        # First item might be format name
        if len(items) >= 2 and isinstance(items[0], str):
            name = items[0]
            fields = items[1:]
        else:
            name = ''
            fields = items

        # Create Format from the field definitions
        return Format.from_params(fields, name)

    def expression(self, items) -> Expression:
        x = Expression('{' + items[0] + '}')
        return x

    def repeat(self, items) -> Repeat:
        expr = items[0]
        count = expr.evaluate()
        return Repeat.from_params(count, items[1])

    def pass_(self, items) -> Pass:
        return Pass()

    def if_(self, items) -> If:
        expr = items[0]
        then_ = items[1]
        else_ = items[2]
        return If.from_params(expr, then_, else_)

    def field_name(self, items) -> str:
        return str(items[0])

    def format_name(self, items) -> str:
        return str(items[0])

    def dtype_name(self, items) -> DtypeName:
        return DtypeName(items[0])

    def dtype_size(self, items) -> int | Expression:
        if isinstance(items[0], Expression):
            return items[0]
        else:
            return int(items[0])

    def dtype_single(self, items) -> DtypeSingle:
        name = items[0]
        size = items[1] if len(items) > 1 else None
        return DtypeSingle.from_params(name, 0 if size is None else size)

    def items(self, items) -> int:
        return int(items[0])

    def dtype_array(self, items) -> DtypeArray:
        dtype = items[0]
        items_count = items[1] if len(items) > 1 else None
        return DtypeArray.from_params(dtype.name, dtype.size, items_count, dtype.endianness)

    def const_field(self, items) -> Field:
        items = [i for i in items if i is not None]
        # Final value is the value itself
        value = items[-1]
        # Penultimate value is the dtype
        dtype = items[-2]
        # Name is the first value if it exists
        name = items[0] if len(items) > 2 else ''
        return Field.from_params(dtype, name, value, const=True)

    def mutable_field(self, items) -> Field:
        items = [i for i in items if i is not None]
        if len(items) == 2:
            if isinstance(items[0], Dtype):
                # dtype and value
                dtype = items[0]
                value = items[1]
                return Field.from_params(dtype, value=value)
            else:
                name = items[0]
                dtype = items[1]
                return Field.from_params(dtype, name)
        elif len(items) == 3:
            name = items[0]
            dtype = items[1]
            value = items[2]
            return Field.from_params(dtype, name, value)
        elif len(items) == 1:
            dtype = items[0]
            return Field.from_params(dtype)
        raise ValueError

    def simple_value(self, items) -> str:
        return str(items[0])

    def list_of_values(self, items):
        return str(items[0])


format_transformer = FormatTransformer()


class FormatSyntaxError(SyntaxError):
    label: str = ''
    def __str__(self):
        context, line, column = self.args
        return '%s at line %s, column %s.\n\n%s' % (self.label, line, column, context)

class FormatMissingValue(FormatSyntaxError):
    label = 'Missing Value'

class FormatUnknownDtype(FormatSyntaxError):
    label = 'Unknown Dtype'

class FormatMissingClosing(FormatSyntaxError):
    label = 'Missing Closing'

class FormatMissingComma(FormatSyntaxError):
    label = 'Missing Comma'




class Format(FieldType):
    """
    A sequence of :class:`FieldType` objects, used to group fields together.

    """
    _fields: list[FieldType]
    name: str
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
                raise ValueError(
                    f"A Field with unknown length may only occur at the end of a Format. Field '{stretchy_field}' is before the end."
                )
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
            if fieldtype.name != "":
                x._field_names[fieldtype.name] = fieldtype
        return x


    @classmethod
    @override
    def from_string(cls, s: str, /) -> Self:
        """
        Create a :class:`Format` instance from a string.

        The string should be of the form ``'[field1, field2, ...]'`` or ``'name = [field1, field2, ...]'``,
        with commas separating strings that will be used to create other :class:`FieldType` instances.

        :param s: The string to parse.
        :type s: str
        :return: The Format instance.
        :rtype: Format

        .. code-block:: python

            f1 = Format.from_string('[u8, bool=True, val: i7]')
            f2 = Format.from_string('my_format = [float16,]')
            f3 = Format.from_string('[u16, another_format = [[u8; 64], [bool; 8]]]')

        """
        try:
            tree = lark_parser.parse(s, start='format')
        except UnexpectedInput as u:
            exc_class = u.match_examples(lark_parser.parse, {
                FormatUnknownDtype: ['[uint8]',
                                     '[[z;]]',
                                     '[u1, [u1, [u1, [u1, penguin]]]]'],
                FormatMissingClosing: ['[u8 = 23',
                                     '[[f16; 6]'],
                FormatMissingComma: ['[i5 i3]'],
            }, use_accepts=False)
            if not exc_class:
                raise
            raise exc_class(u.get_context(s), u.line, u.column)
        try:
            return format_transformer.transform(tree)
        except lark.exceptions.VisitError as e:
            raise ValueError(f"Error parsing format: {e}")

    @override
    def _get_bit_length(self) -> int:
        """Return the total length of the Format in bits."""
        return sum(f.bit_length for f in self._fields)

    @override
    def _pack(
        self,
        values: Sequence[Any],
        _vars: dict[str, Any],
        kwargs: dict[str, Any],
    ) -> None:
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
                raise ValueError(
                    f"When getting Format value, cannot find value of this field:\n{f}"
                )
            vals.append(f.value)
        return vals

    @override
    def _set_value(self, val: Sequence[Any]) -> None:
        if len(val) != len(self._fields):
            raise ValueError(
                f"Can't set {len(self._fields)} fields from {len(val)} values."
            )
        for fieldtype, v in zip(self._fields, val):
            fieldtype._get_value(v)

    value = property(_get_value, _set_value)

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
    def _str(self, indent: Indenter) -> str:
        colour = Colour(not Options().no_color)
        name_str = (
            "" if self.name == "" else f"{colour.green}{self.name}{colour.off} = "
        )
        s = ""
        s += indent(f"{name_str}[\n")
        with indent:
            for i, fieldtype in enumerate(self._fields):
                s += fieldtype._str(indent)
        s += indent("]")
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
