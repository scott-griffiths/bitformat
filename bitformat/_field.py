from __future__ import annotations
import abc
import re
from ._array import Array
from ._bits import Bits
from ._dtypes import Dtype

from ._common import colour, Expression, _indent
from typing import Any, Sequence


__all__ = ['Field']

def _perhaps_convert_to_expression(s: Any) -> tuple[Any | None, None | Expression]:
    if not isinstance(s, str):
        return s, None
    try:
        e = Expression(s)
    except ValueError:
        return s, None
    return None, e


class FieldType(abc.ABC):
    @abc.abstractmethod
    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        """Parse the field from the bits, using the vars_ dictionary to resolve any expressions.

        Return the number of bits used.

        """
        ...

    def parse(self, b: Bits | bytes | bytearray) -> int:
        if isinstance(b, (bytes, bytearray)):
            b = Bits.from_bytes(b)
        try:
            return self._parse(b, {})
        except ValueError as e:
            raise ValueError(f"Error parsing field {self}: {e}")

    @abc.abstractmethod
    def _build(self, values: Sequence[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        """Build the field from the values list, starting at index.

        Return the bits and the number of values used.

        """
        ...

    def build(self, values: Any | None = None, /,  **kwargs) -> Bits:
        if kwargs is None:
            kwargs = {}
        if values is None:
            return self._build([], 0, {}, kwargs)[0]
        try:
            bits, values_used = self._build([values], 0, {}, kwargs)
        except TypeError as e:
            if not isinstance(values, Sequence):
                raise TypeError(f"The values parameter must be a sequence (e.g. a list or tuple), not a {type(values)}.")
            raise e
        return bits

    @abc.abstractmethod
    def to_bits(self) -> Bits:
        """Return the bits that represent the field."""
        ...

    def to_bytes(self) -> bytes:
        """Return the bytes that represent the field. Pads with up to 7 zero bits if necessary."""
        b = self.to_bits()
        return b.to_bytes()

    @abc.abstractmethod
    def clear(self) -> None:
        """Clear the value of the field, unless it is a constant."""
        ...

    @abc.abstractmethod
    def _str(self, indent: int) -> str:
        ...

    @abc.abstractmethod
    def _repr(self, indent: int) -> str:
        ...

    @abc.abstractmethod
    def flatten(self) -> list[FieldType]:
        """Return a flat list of all the fields in the object."""
        ...

    @abc.abstractmethod
    def _getvalue(self) -> Any:
        ...

    @abc.abstractmethod
    def __len__(self) -> int:
        ...

    def __str__(self) -> str:
        return self._str(0)

    def __repr__(self) -> str:
        return self._repr(0)

    def __eq__(self, other) -> bool:
        return self.flatten() == other.flatten()

    def _get_name(self) -> str:
        return self._name

    def _set_name(self, val: str) -> None:
        if val != '':
            if not val.isidentifier():
                raise ValueError(f"The FieldType name '{val}' is not a valid Python identifier.")
            if '__' in val:
                raise ValueError(f"The FieldType name '{val}' contains a double underscore which is not permitted.")
        self._name = val
    name = property(_get_name, _set_name)


class Field(FieldType):

    def __init__(self, dtype: Dtype | str, name: str = '', value: Any = None, const: bool | None = None) -> None:
        super().__init__()
        self._bits = None
        self.dtype = dtype
        if isinstance(self.dtype, str):
            try:
                self.dtype = Dtype.from_string(dtype)
            except ValueError as e:
                raise ValueError(f"Can't convert the string '{dtype}' to a Dtype: {str(e)}")
        self.name = name
        if const is True and value is None:
            raise ValueError(f"Can't set a field to be constant if it has no value.")
        self.const = const
        self.value = value
        if self.dtype.length == 0:
            if self.value is not None:
                self.dtype.length == len(self.value)
            else:
                raise ValueError(f"The dtype must have a known length to create a Field. Received '{str(dtype)}'.")

    def __len__(self) -> int:
        return self.dtype.total_bitlength

    @classmethod
    def from_string(cls, s: str, /):
        dtype_str, name, value, const = cls._parse_field_str(s)
        try:
            dtype = Dtype.from_string(dtype_str)
        except ValueError:
            bits = Bits.from_string(dtype_str)
            const = True  # If it's a bit literal, then set it to const.
            return cls(Dtype.from_parameters('bits'), name, bits, const)
        return cls(dtype, name, value, const)

    @classmethod
    def from_bits(cls, b: Bits, /, name: str = ''):
        return cls(Dtype.from_parameters('bits'), name, b, const=True)

    @classmethod
    def from_bytes(cls, b: bytes | bytearray, /, name: str = ''):
        return cls(Dtype.from_parameters('bytes'), name, b, const=True)

    def to_bits(self) -> Bits:
        if self._bits is None:
            raise ValueError(f"Field '{self}' has no value, so can't be converted to bits.")
        return self._bits

    def clear(self) -> None:
        if not self.const:
            self._setvalue(None)

    def flatten(self) -> list[FieldType]:
        return [self]

    @staticmethod
    def _parse_field_str(field_str: str) -> tuple[str, str, str, bool | None]:
        pattern = r"^(?:(?P<name>.*):)?\s*(?P<const>const\s)?(?P<dtype>[^=]+)\s*(?:=\s*(?P<value>.*))?$"
        match = re.match(pattern, field_str)
        if match:
            name = match.group('name')
            const = match.group('const') is not None
            dtype_str = match.group('dtype').strip()
            value = match.group('value')
        else:
            raise ValueError(f"Invalid field string '{field_str}'.")
        name = '' if name is None else name.strip()
        return dtype_str, name, value, const

    @staticmethod
    def _str_common(dtype, name, value, const, item_str='') -> str:
        const_str = 'const ' if const else ''
        d = f"{colour.purple}{const_str}{dtype}{colour.off}"
        n = '' if name == '' else f"{colour.green}{name}{colour.off}: "
        if isinstance(value, Array):
            v = f" = {colour.cyan}{value.to_list()}{colour.off}"
        else:
            v = '' if value is None else f" = {colour.cyan}{value}{colour.off}"
        return f"{n}{d}{v}"

    @staticmethod
    def _repr_common(dtype, name, value, const, item_str='') -> str:
        const_str = 'const ' if const else ''
        if name != '':
            name = f"{name}: "
        dtype = f"{const_str}{dtype}"
        if isinstance(value, Array):
            v = f" = {value.to_list()}"
        else:
            v = '' if value is None else f" = {value}"
        return f"'{name}{dtype}{v}'"

    def _parse_common(self, b: Bits, vars_: dict[str, Any]) -> int:
        if self.const:
            value = b[:len(self._bits)]
            if value != self._bits:
                raise ValueError(f"Read value '{value}' when '{self._bits}' was expected.")
            return len(self._bits)
        if len(b) < self.dtype.total_bitlength:
            raise ValueError(f"Field '{str(self)}' needs {self.dtype.total_bitlength} bits to parse, but only {len(b)} were available.")
        self._bits = b[:self.dtype.total_bitlength]
        if self.name != '':
            vars_[self.name] = self.value
        return self.dtype.total_bitlength

    def _build_common(self, values: Sequence[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        if self.const and self.value is not None:
            if self.name != '':
                vars_[self.name] = self.value
            return self._bits, 0
        if self.name in kwargs.keys():
            self._setvalue(kwargs[self.name])
            vars_[self.name] = self.value
            return self._bits, 0
        else:
            self._setvalue(values[index])
        if self.name != '':
            vars_[self.name] = self.value
        return self._bits, 1

    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        return self._parse_common(b, vars_)

    def _build(self, values: Sequence[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        return self._build_common(values, index, vars_, kwargs)

    def _getvalue(self) -> Any:
        return self.dtype.unpack(self._bits) if self._bits is not None else None

    def _setvalue(self, value: Any) -> None:
        if value is None:
            self._bits = None
            return
        try:
            self._bits = self.dtype.pack(value)
        except ValueError as e:
            raise ValueError(f"Can't use the value '{value}' with the field '{self}': {e}")

    value = property(_getvalue, _setvalue)

    def _str(self, indent: int) -> str:
        return f"{_indent(indent)}{self._str_common(self.dtype, self.name, self.value, self.const)}"

    # This simple repr used when field is part of a larger object
    def _repr(self, indent: int) -> str:
        return f"{_indent(indent)}{self._repr_common(self.dtype, self.name, self.value, self.const)}"

    # This repr is used when the field is the top level object
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.from_string('{self.__str__()}')"

    def __eq__(self, other: Any) -> bool:
        try:
            if self.dtype != other.dtype:
                return False
            if self._bits != other._bits:
                return False
        except AttributeError:
            return False
        return True


class Find(FieldType):

    def __init__(self, bits: Bits | str, bytealigned: bool = True, name: str = ''):
        super().__init__()
        self.bits_to_find = Bits.from_string(bits)
        self.bytealigned = bytealigned
        self.name = name
        self._value = None

    def _build(self, values: Sequence[Any], index: int, _vars: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        return Bits(), 0

    def to_bits(self) -> Bits:
        return Bits()

    def clear(self) -> None:
        self._value = None

    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        p = b.find(self.bits_to_find, bytealigned=self.bytealigned)
        if p:
            self._value = p[0]
            return p[0]
        self._value = None
        return 0

    def flatten(self) -> list[FieldType]:
        # TODO
        return []

    def _str(self, indent: int) -> str:
        name_str = '' if self.name == '' else f"'{colour.blue}{self.name}{colour.off}',"
        find_str = f"'{colour.green}{str(self.bits_to_find)}{colour.off}'"
        s = f"{_indent(indent)}{self.__class__.__name__}({name_str}{find_str})"
        return s

    def _repr(self, indent: int) -> str:
        return self._str(indent)

    def _getvalue(self) -> int | None:
        return self._value

    value = property(_getvalue, None)
