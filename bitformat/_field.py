from __future__ import annotations

import re
from bitformat import Bits
from ._dtypes import Dtype, DtypeSingle, Register
from ast import literal_eval
from ._common import override, Indenter, Colour, lark_parser, DtypeName, Expression
from typing import Any, Iterable
from ._fieldtype import FieldType
from ._options import Options
from lark import Visitor


__all__ = ["Field"]


class FieldVisitor(Visitor):
    def __init__(self):
        self._values = []
        self._dtype_names = []
        self._dtype_sizes = []
        self._dtype_items = []
        self._const = None
        self._field_name = ''

    def simple_dtype(self, tree):
        name = tree.children[0].children[0].value
        size = 0 if tree.children[1] is None else tree.children[1].children[0].value
        self._dtype_names.append(name)
        self._dtype_sizes.append(size)
        self._dtype_items.append(None)

    def mutable_field(self, tree):
        self._const = False

    def const_field(self, tree):
        self._const = True

    def simple_value(self, tree):
        self._values.append(tree.children[0].value)

    def field_name(self, tree):
        self._field_name = tree.children[0].value

    def items(self, tree):
        # This will already have parsed the simple_dtype, so replace
        # the None value for items.
        self._dtype_items.pop()
        self._dtype_items.append(tree.children[0].value)


class Field(FieldType):
    const: bool
    _bits: Bits | None
    _dtype: Dtype
    _size_expr: Expression | None

    def __new__(cls, s: str) -> Field:
        return cls.from_string(s)

    @classmethod
    def from_params(cls, dtype: Dtype | str, name: str = "", value: Any = None, const: bool = False,
                    size_expr: Expression | None = None, comment: str = "") -> Field:
        """
        Create a Field instance from parameters.

        :param dtype: The data type of the field.
        :type dtype: Dtype or str
        :param name: The name of the field, optional.
        :type name: str
        :param value: The value of the field, optional.
        :type value: Any
        :param const: Whether the field is constant, optional.
        :type const: bool
        :return: The Field instance.
        :param comment: An optional comment string
        :type comment: str

        :rtype: Field
        """
        x = super().__new__(cls)
        x._bits = None
        x.const = const
        x._size_expr = size_expr
        x.comment = comment.strip()
        if isinstance(dtype, str):
            try:
                x._dtype = Dtype.from_string(dtype)
            except ValueError as e:
                raise ValueError(f"Can't convert the string '{dtype}' to a Dtype: {str(e)}")
        else:
            x._dtype = dtype
        x.name = name
        if const is True and value is None:
            raise ValueError("Fields with no value cannot be set to be const.")
        if isinstance(value, str):
            # Special cases converting from strings to bytes and bools.
            value_str = value
            if x._dtype.return_type is bytes:
                try:
                    value = literal_eval(value)
                    if not isinstance(value, bytes):
                        raise ValueError()
                except ValueError:
                    raise ValueError(
                        f"Can't initialise dtype '{dtype}' with the value string '{value_str}' "
                        f"as it can't be converted to a bytes object."
                    )
            if x._dtype.return_type is bool:
                try:
                    value = literal_eval(value)
                    if not isinstance(value, int) or value not in (0, 1):
                        raise ValueError()
                except ValueError:
                    raise ValueError(
                        f"Can't initialise dtype '{dtype}' with the value string '{value_str}' "
                        f"as it can't be converted to a bool."
                    )
        if value is not None:
            x._set_value_no_const_check(value)
        if isinstance(x._dtype, DtypeSingle) and x._dtype.size == 0:
            if x._dtype.name in [DtypeName.BITS, DtypeName.BYTES] and x.value is not None:
                x._dtype = Register().get_single_dtype(x._dtype.name, len(x.value), x._dtype.endianness)
        return x

    @override
    def _get_bit_length(self) -> int:
        return self._dtype.bit_length

    @classmethod
    def from_string_lark(cls, s: str, /) -> Field:
        x = lark_parser.parse(s, start='field')
        visitor = FieldVisitor()
        visitor.visit(x)
        if len(visitor._dtype_names) == 1:
            items = visitor._dtype_items[0]
            dtype = Dtype.from_params(visitor._dtype_names[0],
                                      visitor._dtype_sizes[0],
                                      items is not None,
                                      items)
            if not visitor._values:
                values = None
            else:
                values = visitor._values[0]
            return cls.from_params(dtype, visitor._field_name, values, visitor._const)

    @classmethod
    @override
    def from_string(cls, s: str, /) -> Field:
        s, comment = s.split("#", 1) if "#" in s else (s, "")
        comment = comment.strip()
        dtype_str, name, value, const = cls._parse_field_str(s)
        if (p := dtype_str.find("{")) == -1:
            size_expr = None
        else:
            q = dtype_str.find("}")
            if q == -1 or q < p:
                raise ValueError(f"Field string '{s}' has mismatched braces.")
            size_expr = Expression(dtype_str[p:q + 1])
            dtype_str = dtype_str[:p] + dtype_str[q + 1:]
        return cls.from_params(dtype_str, name, value, const, size_expr, comment)

    @classmethod
    def from_bits(
        cls,
        b: Bits | str | Iterable | bytearray | bytes | memoryview,
        /,
        name: str = "",
    ) -> Field:
        """
        Create a Field instance from bits.

        :param b: The bits to parse.
        :type b: Bits, str, Iterable, bytearray, bytes, or memoryview
        :param name: The name of the field, optional.
        :type name: str
        :return: The Field instance.
        :rtype: Field
        """
        b = Bits._from_any(b)
        if len(b) == 0:
            raise ValueError("Can't create a Field from an empty Bits object.")
        return cls.from_params(DtypeSingle.from_params(DtypeName.BITS, len(b)), name, b, const=True)

    @classmethod
    def from_bytes(
        cls, b: bytes | bytearray, /, name: str = "", const: bool = False
    ) -> Field:
        """
        Create a Field instance from bytes.

        :param b: The bytes to parse.
        :type b: bytes or bytearray
        :param name: The name of the field, optional.
        :type name: str
        :param const: Whether the field is constant, optional.
        :type const: bool
        :return: The Field instance.
        :rtype: Field
        """
        return cls.from_params(DtypeSingle.from_params(DtypeName.BYTES, len(b)), name, b, const)

    @override
    def to_bits(self) -> Bits:
        if self._bits is None:
            raise ValueError(
                f"Field '{self}' has no value, so can't be converted to bits."
            )
        return self._bits

    @override
    def clear(self) -> None:
        if not self.const:
            self._bits = None

    @override
    def _copy(self) -> Field:
        x = self.__class__.from_params(
            self.dtype, self.name, self.value, self.const, self._size_expr, self.comment
        )
        return x

    @staticmethod
    def _parse_field_str(field_str: str) -> tuple[str, str, str, bool | None]:
        if "\n" in field_str:
            raise ValueError("Field strings should not contain newline characters.")
        pattern = r"^(?:(?P<name>.*):)?\s*(?P<const>const\s)?(?P<dtype>[^=]+)\s*(?:=\s*(?P<value>.*))?$"
        compiled_pattern = re.compile(pattern, re.DOTALL)
        match = compiled_pattern.match(field_str)
        if match:
            name = match.group("name")
            const = match.group("const") is not None
            dtype_str = match.group("dtype").strip()
            value = match.group("value")
        else:
            raise ValueError(f"Invalid field string '{field_str}'.")
        name = "" if name is None else name.strip()
        return dtype_str, name, value, const

    @override
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
        if self.const:
            value = b[startbit : len(self._bits)]
            if value != self._bits:
                raise ValueError(
                    f"Read value '{value}' when const value '{self._bits}' was expected."
                )
            return len(self._bits)
        if self._size_expr is not None:
            size = self._size_expr.evaluate(vars_)
            # TODO: A bit hacky, needs to be revised for other dtypes.
            dtype = DtypeSingle.from_params(self._dtype.name, size, self._dtype.endianness)
        else:
            dtype = self._dtype
        if len(b) - startbit < dtype.bit_length:
            raise ValueError(
                f"Field '{str(self)}' needs {dtype.bit_length} bits to parse, but {len(b) - startbit} were available."
            )
        # Deal with a stretchy dtype
        self._bits = (
            b[startbit : startbit + dtype.bit_length]
            if dtype.bit_length != 0
            else b[startbit:]
        )
        if self.name != "":
            vars_[self.name] = self.value
        return len(self._bits)

    @override
    def _pack(
        self,
        value: Any,
        vars_: dict[str, Any],
        kwargs: dict[str, Any],
    ) -> None:
        if self.name in kwargs:
            self._set_value(kwargs[self.name])
        else:
            self._set_value(value)
        if self.name:
            vars_[self.name] = self.value

    @override
    def _get_value(self) -> Any | None:
        if self._bits is None:
            return None
        return self.dtype.unpack(self._bits)

    def _set_value_no_const_check(self, value: Any) -> None:
        if value is None:
            raise ValueError(
                "Cannot set the value of a Field to None. Perhaps you could use clear()?"
            )
        try:
            self._bits = self.dtype.pack(value)
        except ValueError as e:
            raise ValueError(
                f"Can't use the value '{value}' with the field '{self}': {e}"
            )

    @override
    def _set_value(self, value: Any) -> None:
        if self.const:
            raise ValueError(
                f"Cannot set the value of a const Field '{self}'. "
                f"To change the value, first set the const property of the Field to False."
            )
        self._set_value_no_const_check(value)

    value = property(_get_value, _set_value)

    def _get_dtype(self) -> Dtype:
        return self._dtype

    dtype = property(_get_dtype)

    @override
    def _str(self, indent: Indenter) -> str:
        colour = Colour(not Options().no_color)
        const_str = "const " if self.const else ""
        dtype_str = str(self._dtype) + ("" if self._size_expr is None else str(self._size_expr))
        d = f"{colour.purple}{const_str}{dtype_str}{colour.off}"
        n = "" if self.name == "" else f"{colour.green}{self.name}{colour.off}: "
        v = "" if self.value is None else f" = {colour.cyan}{self.value}{colour.off}"
        comment = "" if self.comment == "" else f"  # {self.comment}"
        return indent(f"{n}{d}{v}{comment}")

    # This simple repr used when field is part of a larger object
    @override
    def _repr(self) -> str:
        const_str = "const " if self.const else ""
        n = "" if self.name == "" else f"{self.name}: "
        dtype = f"{const_str}{self._dtype}" + ("" if self._size_expr is None else str(self._size_expr))
        v = "" if self.value is None else f" = {self.value}"
        return f"'{n}{dtype}{v}'"

    # This repr is used when the field is the top level object
    def __repr__(self) -> str:
        if self.dtype.name == DtypeName.BYTES:
            const_str = ", const=True" if self.const else ""
            return f"{self.__class__.__name__}.from_bytes({self.value}{const_str})"
        return f"{self.__class__.__name__}({self._repr()})"

    @override
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Field):
            return False
        if self.dtype != other.dtype:
            return False
        if self.dtype.name != DtypeName.PAD and self._bits != other._bits:
            return False
        if self.const != other.const:
            return False
        if self.name != other.name:
            return False
        return True
