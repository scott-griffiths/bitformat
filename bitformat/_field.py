from __future__ import annotations
import abc
import re
from ._bits import Bits
from ._dtypes import Dtype

from ._common import colour, Expression, _indent, override, final
from typing import Any, Sequence, Iterable

__all__ = ['Field', 'FieldType']


def _perhaps_convert_to_expression(s: Any) -> tuple[Any | None, None | Expression]:
    if not isinstance(s, str):
        return s, None
    try:
        e = Expression(s)
    except ValueError:
        return s, None
    return None, e

class DtypeWithExpression(Dtype):
    """Used internally. A Dtype that can contain an Expression instead of fixed values for length or items."""
    pass


class FieldType(abc.ABC):

    @final
    def parse(self, b: Bits | bytes | bytearray) -> int:
        if isinstance(b, (bytes, bytearray)):
            b = Bits.from_bytes(b)
        try:
            return self._parse(b, {})
        except ValueError as e:
            raise ValueError(f"Error parsing field {self}: {e}")

    @final
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

    @final
    def __str__(self) -> str:
        return self._str(0)

    @final
    def __repr__(self) -> str:
        return self._repr(0)

    @classmethod
    def from_string(cls, s: str) -> FieldType:
        try:
            return Field.from_string(s)
        except ValueError:
            from ._format import Format
            return Format.from_string(s)

    @abc.abstractmethod
    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        """Parse the field from the bits, using the vars_ dictionary to resolve any expressions.

        Return the number of bits used.

        """
        ...

    @abc.abstractmethod
    def _build(self, values: Sequence[Any], index: int, vars_: dict[str, Any],
               kwargs: dict[str, Any]) -> tuple[Bits, int]:
        """Build the field from the values list, starting at index.

        Return the bits and the number of values used.

        """
        ...

    @abc.abstractmethod
    def to_bits(self) -> Bits:
        """Return the bits that represent the field."""
        ...

    @final
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
    def _setvalue(self, value: Any) -> None:
        ...

    @abc.abstractmethod
    def __len__(self) -> int:
        """The length of the FieldType in bits."""
        ...

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

    def __new__(cls, token: str | None = None) -> Field:
        if token is None:
            x = super().__new__(cls)
            return x
        return cls.from_string(token)

    @classmethod
    def from_parameters(cls, dtype: Dtype | str, name: str = '', value: Any = None, const: bool | None = None) -> Field:
        x = super().__new__(cls)
        x._bits = None
        x._dtype = dtype
        if isinstance(x._dtype, str):
            try:
                x._dtype = Dtype.from_string(dtype)
            except ValueError as e:
                raise ValueError(f"Can't convert the string '{dtype}' to a Dtype: {str(e)}")
        x.name = name
        if const is True and value is None:
            raise ValueError(f"Fields with no value cannot be set to be const.")
        x.const = const
        x.value = value
        if x._dtype.length == 0:
            if x._dtype.name in ['bits', 'bytes'] and x.value is not None:
                x._dtype = Dtype.from_parameters(x._dtype.name, len(x.value))
            else:
                raise ValueError(f"The dtype must have a known length to create a Field. Received '{str(dtype)}'.")
        return x

    @override
    def __len__(self) -> int:
        return len(self._dtype)

    @classmethod
    @override
    def from_string(cls, s: str, /) -> Field:
        dtype_str, name, value, const = cls._parse_field_str(s)
        return cls.from_parameters(dtype_str, name, value, const)

    @classmethod
    def from_bits(cls, b: Bits | str | Iterable | bytearray | bytes | memoryview, /, name: str = '') -> Field:
        b = Bits.from_auto(b)
        return cls.from_parameters(Dtype.from_parameters('bits', len(b)), name, b, const=True)

    @classmethod
    def from_bytes(cls, b: bytes | bytearray, /, name: str = '') -> Field:
        return cls.from_parameters(Dtype.from_parameters('bytes', len(b)), name, b, const=True)

    @override
    def to_bits(self) -> Bits:
        if self._bits is None:
            raise ValueError(f"Field '{self}' has no value, so can't be converted to bits.")
        return self._bits

    @override
    def clear(self) -> None:
        if not self.const:
            self._setvalue(None)

    @override
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

    @override
    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        if self.const:
            value = b[:len(self._bits)]
            if value != self._bits:
                raise ValueError(f"Read value '{value}' when const value '{self._bits}' was expected.")
            return len(self._bits)
        if len(b) < len(self):
            raise ValueError(f"Field '{str(self)}' needs {len(self)} bits to parse, but only {len(b)} were available.")
        self._bits = b[:len(self)]
        if self.name != '':
            vars_[self.name] = self.value
        return len(self)

    @override
    def _build(self, values: Sequence[Any], index: int, vars_: dict[str, Any],
               kwargs: dict[str, Any]) -> tuple[Bits, int]:
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

    @override
    def _getvalue(self) -> Any:
        return self._dtype.unpack(self._bits) if self._bits is not None else None

    @override
    def _setvalue(self, value: Any) -> None:
        if value is None:
            self._bits = None
            return
        try:
            self._bits = self._dtype.pack(value)
        except ValueError as e:
            raise ValueError(f"Can't use the value '{value}' with the field '{self}': {e}")

    value = property(_getvalue, _setvalue)

    def _getdtype(self) -> Dtype:
        return self._dtype

    def _setdtype(self, dtype: Dtype | str) -> None:
        if isinstance(dtype, str):
            dtype = Dtype.from_string(dtype)
        self._dtype = dtype

    dtype = property(_getdtype, _setdtype)

    @override
    def _str(self, indent: int) -> str:
        const_str = 'const ' if self.const else ''
        d = f"{colour.purple}{const_str}{self._dtype}{colour.off}"
        n = '' if self.name == '' else f"{colour.green}{self.name}{colour.off}: "
        v = '' if self.value is None else f" = {colour.cyan}{self.value}{colour.off}"
        return f"{_indent(indent)}{n}{d}{v}"

    # This simple repr used when field is part of a larger object
    @override
    def _repr(self, indent: int) -> str:
        const_str = 'const ' if self.const else ''
        n = '' if self.name == '' else f"{self.name}: "
        dtype = f"{const_str}{self._dtype}"
        v = '' if self.value is None else f" = {self.value}"
        return f"{_indent(indent)}'{n}{dtype}{v}'"

    # This repr is used when the field is the top level object
    @override  # TODO - this shouldn't be here. Should be _repr(0).
    def __repr__(self) -> str:
        if self._dtype.name == 'bytes':
            return f"{self.__class__.__name__}.from_bytes({self.value})"
        return f"{self.__class__.__name__}('{self.__str__()}')"

    def __eq__(self, other: Any) -> bool:
        try:
            if self._dtype != other._dtype:
                return False
            if self._dtype.name != 'pad' and self._bits != other._bits:
                return False
        except AttributeError:
            return False
        return True


class Find(FieldType):

    def __init__(self, bits: Bits | str, bytealigned: bool = True, name: str = '') -> None:
        super().__init__()
        self.bits_to_find = Bits.from_string(bits)
        self.bytealigned = bytealigned
        self.name = name
        self._value = None

    def _build(self, values: Sequence[Any], index: int, _vars: dict[str, Any],
               kwargs: dict[str, Any]) -> tuple[Bits, int]:
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
