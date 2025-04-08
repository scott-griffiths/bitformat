from __future__ import annotations

from bitformat import Bits
from ._dtypes import Dtype, DtypeSingle, DtypeArray, DtypeTuple
from ast import literal_eval
from ._common import override, Indenter, Colour, DtypeKind, validate_name, Expression
from typing import Any, Iterable, Self
from ._fieldtype import FieldType
from ._options import Options

__all__ = ["Field"]


class Field(FieldType):
    _const: bool
    _bits: Bits | None
    # The dtype may include expressions that haven't yet been evaluated.
    _dtype: Dtype
    # the concrete type is the real dtype after parsing.
    _concrete_dtype: Dtype | None
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
        x._concrete_dtype = x._dtype if x._dtype.is_concrete() else None

        x.name = name
        if x.const is True and value is None:
            raise ValueError("Fields with no value cannot be set to be const.")
        if isinstance(value, str):
            value_str = value
            # Need to convert non-string types into their correct return types.
            if isinstance(x._dtype, DtypeSingle) and (ret_type := x._dtype._definition.return_type) in (int, float, bytes, bool):
                try:
                    value = ret_type(literal_eval(value_str))
                except ValueError:
                    raise ValueError(f"Can't initialise dtype '{dtype}' with the value string '{value_str}' "
                                     f"as it can't be converted to a {ret_type}.")
        if value is not None:
            x._set_value_no_const_check(value, {})
        return x

    @override
    def _get_bit_length(self) -> int:
        if self._concrete_dtype is None:
            raise ValueError(f"Field '{self}' has no concrete dtype, so can't determine the bit length.")
        if self._concrete_dtype.bit_length is None:
            # For dtypes like just 'bytes' or 'hex' they might not have a dtype length, but still contain bits.
            if self._bits is not None:
                return len(self._bits)
            else:
                raise ValueError(f"Field '{self}' has no concrete dtype and no bits, so can't determine the bit length.")
        return self._concrete_dtype.bit_length

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
            self._concrete_dtype = None
            self._bits = None

    @override
    def is_stretchy(self) -> bool:
        if isinstance(self._dtype, DtypeSingle):
            if not self.const and self._dtype.size == Expression('{None}'):
                return True
        return False


    @override
    def _copy(self) -> Field:
        x = self.__class__.from_params(self.dtype, self.name, self.value, self.const)
        return x

    @staticmethod
    def _make_concrete_dtype(dtype: Dtype, vars_: dict[str, Any]) -> Dtype | None:
        if isinstance(dtype, DtypeSingle) and dtype.size is not None:
            size = dtype._size.evaluate(vars_)
            return DtypeSingle.from_params(dtype.kind, size, dtype.endianness)
        elif isinstance(dtype, DtypeArray):
            size = dtype._dtype_single._size.evaluate(vars_)
            items = dtype._items.evaluate(vars_)
            return DtypeArray.from_params(dtype._dtype_single.kind, size, items, dtype.endianness)
        elif isinstance(dtype, DtypeTuple):
            # Create concrete dtypes for each of the dtypes in the tuple
            concrete_dtypes = []
            for d in dtype._dtypes:
                concrete_dtype = Field._make_concrete_dtype(d, vars_)
                if concrete_dtype is None:
                    return None
                concrete_dtypes.append(concrete_dtype)
            return DtypeTuple.from_params(concrete_dtypes)
        assert False

    @override
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
        if self.const:
            assert self._bits is not None
            value = b[startbit : startbit + len(self._bits)]
            if value != self._bits:
                raise ValueError(f"Read value '{value}' when const value '{self._bits}' was expected.")
            return len(self._bits)
        self._concrete_dtype = Field._make_concrete_dtype(self._dtype, vars_)
        if self._concrete_dtype is None:
            raise ValueError(f"Can't parse field '{self}' as the concrete dtype couldn't be determined.")
        if self._concrete_dtype.bit_length is not None and len(b) - startbit < self._concrete_dtype.bit_length:
            raise ValueError(f"Field '{str(self)}' needs {self._concrete_dtype.bit_length} bits to parse, but {len(b) - startbit} were available.")
        # Deal with a stretchy dtype
        dtype_length = self._concrete_dtype.calculate_bit_length(vars_)
        self._bits = b[startbit : startbit + dtype_length] if dtype_length is not None else b[startbit:]
        if self.name != "":
            if self._bits is None:
                vars_[self.name] = None
            else:
                vars_[self.name] = self._concrete_dtype.unpack(self._bits)
        return len(self._bits)

    @override
    def _pack(self, value: Any, kwargs: dict[str, Any]) -> None:
        if self.name in kwargs:
            self._set_value_with_kwargs(kwargs[self.name], {})
        else:
            self._set_value_with_kwargs(value, kwargs)
        if self.name:
            kwargs[self.name] = self.value

    @override
    def _get_value(self) -> Any | None:
        if self._bits is None:
            return None
        if self._concrete_dtype is None:
            raise ValueError("The Field has no concrete dtype, so can't get the value.")
        return self._concrete_dtype.unpack(self._bits)

    def _set_value_no_const_check(self, value: Any, kwargs: dict[str, Any]) -> None:
        if value is None:
            raise ValueError("Cannot set the value of a Field to None. Perhaps you could use clear()?")
        if self._concrete_dtype is not None:
            self._bits = self._concrete_dtype.pack(value)
        else:
            self._concrete_dtype = Field._make_concrete_dtype(self._dtype, kwargs)
            if self._concrete_dtype is not None:
                self._bits = self._concrete_dtype.pack(value)
            else:
                raise ValueError(f"Field '{self}' cannot compute a concrete dtype with kwargs {kwargs}, so can't set the value.")

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
        if self.const != other.const:
            return False
        if self.name != other.name:
            return False
        if self.dtype != other.dtype:
            return False
        if isinstance(self.dtype, DtypeSingle) and self.dtype.kind is not DtypeKind.PAD and self._bits != other._bits:
            return False
        return True
