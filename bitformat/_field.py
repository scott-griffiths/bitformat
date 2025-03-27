from __future__ import annotations

from bitformat import Bits, DtypeArray
from ._dtypes import Dtype, DtypeSingle, Register
from ast import literal_eval
from ._common import override, Indenter, Colour, DtypeKind, validate_name
from typing import Any, Iterable, Self
from ._fieldtype import FieldType
from ._options import Options

__all__ = ["Field"]


class Field(FieldType):
    _const: bool
    _bits: Bits | None
    _dtype: Dtype
    _name: str

    def __new__(cls, s: str) -> Field:
        return cls.from_string(s)

    @classmethod
    def from_params(cls, dtype: Dtype | str, name: str = "", value: Any = None, const: bool = False) -> Self:
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

        :rtype: Field
        """
        x = super().__new__(cls)
        x._bits = None
        x._const = bool(const)
        if isinstance(dtype, str):
            try:
                x._dtype = Dtype.from_string(dtype)
            except ValueError as e:
                raise ValueError(f"Can't convert the string '{dtype}' to a Dtype: {str(e)}")
        else:
            x._dtype = dtype
        x.name = name
        if x.const is True and value is None:
            raise ValueError("Fields with no value cannot be set to be const.")
        if isinstance(value, str):
            value_str = value
            # Need to convert non-string types into their correct return types.
            if isinstance(x._dtype, DtypeSingle) and (ret_type := x._dtype._definition.return_type) in (int, float, bytes, bool):
                try:
                    value = ret_type(literal_eval(value))
                except ValueError:
                    raise ValueError(f"Can't initialise dtype '{dtype}' with the value string '{value_str}' "
                                     f"as it can't be converted to a {ret_type}.")
            elif isinstance(x._dtype, DtypeSingle) and x._dtype._definition.return_type == Bits:
                value = Bits.from_string(value)
        if value is not None:
            x._set_value_no_const_check(value, {})
        # TODO: This is not a nice condition!
        if isinstance(x._dtype, DtypeSingle) and x._dtype.size.has_const_value and x._dtype.size.const_value is None:
            if x._dtype.kind in [DtypeKind.BITS, DtypeKind.BYTES] and x.value is not None:
                x._dtype = Register().get_single_dtype(x._dtype.kind, len(x.value), x._dtype.endianness)
        return x

    @override
    def _get_bit_length(self) -> int:
        return self._dtype.bit_length

    @classmethod
    @override
    def from_string(cls, s: str, /) -> Self:
        x = super().from_string(s)
        if not isinstance(x, Field):
            raise ValueError(f"Can't parse a Field from '{s}'. Instead got '{x!r}'. "
                             f"If this is the type you want you can use it directly or use the FieldType constructor instead.")
        return x

    @classmethod
    def from_bits(cls, b: Bits | str | Iterable | bytearray | bytes | memoryview, /,
                  name: str = "", const: bool = False) -> Self:
        """
        Create a Field instance from bits.

        :param b: The bits to parse.
        :type b: Bits, str, Iterable, bytearray, bytes, or memoryview
        :param name: The name of the field, optional.
        :type name: str
        :param const: Whether the field is constant, defaults to False.
        :type const: bool
        :return: The Field instance.
        :rtype: Field
        """
        b = Bits._from_any(b)
        if len(b) == 0:
            raise ValueError("Can't create a Field from an empty Bits object.")
        return cls.from_params(DtypeSingle.from_params(DtypeKind.BITS, len(b)), name, b, const)

    @classmethod
    def from_bytes(cls, b: bytes | bytearray, /, name: str = "", const: bool = False) -> Field:
        """
        Create a Field instance from bytes.

        :param b: The bytes to parse.
        :type b: bytes or bytearray
        :param name: The name of the field, optional.
        :type name: str
        :param const: Whether the field is constant, defaults to False.
        :type const: bool
        :return: The Field instance.
        :rtype: Field
        """
        return cls.from_params(DtypeSingle.from_params(DtypeKind.BYTES, len(b)), name, b, const)

    @override
    def to_bits(self) -> Bits:
        if self._bits is None:
            raise ValueError(f"Field '{self}' has no value, so can't be converted to bits.")
        return self._bits

    @override
    def clear(self) -> None:
        if not self.const:
            self._bits = None

    @override
    def _copy(self) -> Field:
        x = self.__class__.from_params(self.dtype, self.name, self.value, self.const)
        return x

    @override
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
        if self.const:
            value = b[startbit : len(self._bits)]
            if value != self._bits:
                raise ValueError(f"Read value '{value}' when const value '{self._bits}' was expected.")
            return len(self._bits)
        # TODO: Hacky, needs to be revised for other dtypes.
        if isinstance(self._dtype, DtypeSingle) and self._dtype.size is not None:
            size = self._dtype._size.evaluate(vars_)
            dtype = DtypeSingle.from_params(self._dtype.kind, size, self._dtype.endianness)
        elif isinstance(self._dtype, DtypeArray):
            size = self._dtype._dtype_single._size.evaluate(vars_)
            items = self._dtype._items.evaluate(vars_)
            dtype = DtypeArray.from_params(self._dtype._dtype_single.kind, size, items, self._dtype.endianness)
        else:
            dtype = self._dtype
        if dtype.bit_length is not None and len(b) - startbit < dtype.bit_length:
            raise ValueError(f"Field '{str(self)}' needs {dtype.bit_length} bits to parse, but {len(b) - startbit} were available.")
        # Deal with a stretchy dtype
        dtype_length = dtype.calculate_bit_length(vars_)
        self._bits = b[startbit : startbit + dtype_length] if dtype_length is not None else b[startbit:]
        if self.name != "":
            if self._bits is None:
                vars_[self.name] = None
            else:
                vars_[self.name] = dtype.unpack(self._bits)
        return len(self._bits)

    @override
    def _pack(self, value: Any, vars_: dict[str, Any], kwargs: dict[str, Any]) -> None:
        if self.name in kwargs:
            self._set_value_with_kwargs(kwargs[self.name], {})
        else:
            self._set_value_with_kwargs(value, kwargs)
        if self.name:
            vars_[self.name] = self.value

    @override
    def _get_value(self) -> Any | None:
        if self._bits is None:
            return None
        return self.dtype.unpack(self._bits)

    def _set_value_no_const_check(self, value: Any, kwargs: dict[str, Any]) -> None:
        if value is None:
            raise ValueError("Cannot set the value of a Field to None. Perhaps you could use clear()?")
        try:
            if not kwargs:
                self._bits = self.dtype.pack(value)
            else:
                pass # TODO
        except ValueError as e:
            raise ValueError(f"Can't use the value '{value}' with the field '{self}': {e}")

    @override
    def _set_value_with_kwargs(self, value: Any, kwargs: dict[str, Any]) -> None:
        if self.const:
            raise ValueError(f"Cannot set the value of a const Field '{self}'.")
        self._set_value_no_const_check(value, kwargs)

    def _get_dtype(self) -> Dtype:
        return self._dtype

    dtype = property(_get_dtype)

    @property
    def const(self) -> bool:
        return self._const

    @override
    def _get_name(self) -> str:
        return self._name

    @override
    def _set_name(self, name: str) -> None:
        self._name = validate_name(name)

    @override
    def _str(self, indent: Indenter, use_colour: bool) -> str:
        colour = Colour(use_colour)
        const_str = f"{colour.const_value}const{colour.off} " if self.const else ""
        dtype_str = str(self._dtype)
        d = f"{const_str}{dtype_str}"
        n = "" if self.name == "" else f"{colour.name}{self.name}{colour.off}: "
        if self.value is None:
            v = ""
        else:
            if self.const:
                v = f" = {colour.const_value}{self.value}{colour.off}"
            else:
                v = f" = {colour.value}{self.value}{colour.off}"
        return indent(f"{n}{d}{v}")

    # This simple repr used when field is part of a larger object
    @override
    def _repr(self) -> str:
        s = self._str(Indenter(0), not Options().no_color)
        return f"'{s}'"

    # This repr is used when the field is the top level object
    def __repr__(self) -> str:
        if isinstance(self.dtype, DtypeSingle) and self.dtype.kind is DtypeKind.BYTES:
            const_str = ", const=True" if self.const else ""
            return f"{self.__class__.__name__}.from_bytes({self.value}{const_str})"
        return f"{self.__class__.__name__}({self._repr()})"

    @override
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Field):
            return False
        if self.dtype != other.dtype:
            return False
        if self.dtype.kind is not DtypeKind.PAD and self._bits != other._bits:
            return False
        if self.const != other.const:
            return False
        if self.name != other.name:
            return False
        return True
