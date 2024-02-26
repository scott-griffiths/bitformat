from __future__ import annotations
import abc
from bitstring import Bits, Dtype, Array

from .common import colour, Expression, indent_size
from typing import Any

class FieldType(abc.ABC):
    @abc.abstractmethod
    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        """Parse the field from the bits, using the vars_ dictionary to resolve any expressions. Return the number of bits used."""
        ...

    def parse(self, b: Bits | bytes | bytearray) -> int:
        if isinstance(b, (bytes, bytearray)):
            b = Bits(b)
        try:
            return self._parse(b, {})
        except ValueError as e:
            raise ValueError(f"Error parsing field {self}: {e}")

    @abc.abstractmethod
    def _build(self, values: list[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        """Build the field from the values list, starting at index. Return the bits and the number of values used."""
        ...

    def build(self, values: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> Bits:
        return self._build([] if values is None else values, 0, {},  {} if kwargs is None else kwargs)[0]

    @abc.abstractmethod
    def bits(self) -> Bits:
        """Return the bits that represent the field."""
        ...

    def bytes(self) -> bytes:
        """Return the bytes that represent the field. Pads with up to 7 zero bits if necessary."""
        b = self.bits()
        return b.tobytes()

    @abc.abstractmethod
    def clear(self) -> None:
        """Clear the value of the field, unless it is a constant."""
        ...

    @abc.abstractmethod
    def _str(self, indent: int) -> str:
        ...

    @abc.abstractmethod
    def flatten(self) -> list[FieldType]:
        """Return a flat list of all the fields in the object."""
        ...

    @abc.abstractmethod
    def _getvalue(self) -> Any:
        ...

    def __str__(self) -> str:
        return self._str(0)

    def __repr__(self) -> str:
        return self.__str__()

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

class SingleDtypeField(FieldType):
    """Holds the common code for other Field classes with a single Dtype.
    This class should not be used directly."""

    def __init__(self, dtype: Dtype | str, name: str = '', value: Any = None, const: bool | None = None) -> None:
        self._bits = None
        self.dtype = dtype
        self.dtype_expression = None
        if isinstance(self.dtype, str):
            p = self.dtype.find('{')
            if p != -1:
                self.dtype_expression = Expression(self.dtype[p:])
                self.dtype = self.dtype[:p]
            else:
                try:
                    self.dtype = Dtype(dtype)
                except ValueError:
                    raise ValueError(f"Can't convert '{dtype}' string to a Dtype.")
        self.name = name

        if self.dtype_expression is None and self.dtype.length == 0:
            raise ValueError(f"A field's dtype cannot have a length of zero (dtype = {self.dtype}).")
        if const is None:
            self.const = value is not None
        else:
            if value is None:
                raise ValueError(f"Can't set a field to be constant if it has no value.")
            self.const = const

    def bits(self) -> Bits:
        return self._bits if self._bits is not None else Bits()

    def clear(self) -> None:
        if not self.const:
            self._setvalue(None)

    def flatten(self) -> list[FieldType]:
        return [self]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.fromstring({self.__str__()})"

    @staticmethod
    def _parse_field_str(dtype_str: str) -> tuple[str, str | None, str, int, bool | None]:
        # The string has the form 'dtype [* items] [<name>] [= value]'
        # But there may be chars inside {} sections that should be ignored.
        # So we scan to find first real *, <, > and =
        asterix_pos = -1
        lessthan_pos = -1
        greaterthan_pos = -1
        equals_pos = -1
        colon_pos = -1
        inside_braces = False
        for pos, char in enumerate(dtype_str):
            if char == '{':
                if inside_braces:
                    raise ValueError(f"Two consecutive opening braces found in '{dtype_str}'.")
                inside_braces = True
            if char == '}':
                if not inside_braces:
                    raise ValueError(f"Closing brace found with no matching opening brace in '{dtype_str}'.")
                inside_braces = False
            if inside_braces:
                continue
            if char == '*':
                if asterix_pos != -1:
                    raise ValueError(f"More than one '*' found in '{dtype_str}'.")
                asterix_pos = pos
            if char == '<':
                if lessthan_pos != -1:
                    raise ValueError(f"More than one '<' found in '{dtype_str}'.")
                lessthan_pos = pos
            if char == '>':
                if greaterthan_pos != -1:
                    raise ValueError(f"More than one '>' found in '{dtype_str}'.")
                greaterthan_pos = pos
            if char == '=':
                if equals_pos != -1:
                    raise ValueError(f"More than one '=' found in '{dtype_str}'.")
                if colon_pos != -1:
                    raise ValueError(f"An '=' found in '{dtype_str}' as well as a ':'.")
                equals_pos = pos
            if char == ':':
                if colon_pos != -1:
                    raise ValueError(f"More than one ':' found in '{dtype_str}'.")
                if equals_pos != -1:
                    raise ValueError(f"A ':' found in '{dtype_str}' as well as an '='.")
                colon_pos = pos

        value = const = None
        name = ''
        items = 1
        # Check to see if it includes a value:
        if equals_pos != -1:
            value = dtype_str[equals_pos + 1:]
            dtype_str = dtype_str[:equals_pos]
            const = True
        if colon_pos != -1:
            value = dtype_str[colon_pos + 1:]
            dtype_str = dtype_str[:colon_pos]
            const = False
        # Check if it has a name:
        if lessthan_pos != -1:
            if greaterthan_pos == -1:
                raise ValueError(
                    f"An opening '<' was supplied in the formatted dtype '{dtype_str} but without a closing '>'.")
            name = dtype_str[lessthan_pos + 1:greaterthan_pos]
            name = name.strip()
            chars_after_name = dtype_str[greaterthan_pos + 1:]
            if chars_after_name != '' and not chars_after_name.isspace():
                raise ValueError(f"There should be no trailing characters after the <name>.")
            dtype_str = dtype_str[:lessthan_pos]
        if asterix_pos != -1:
            items = dtype_str[asterix_pos + 1:]
            dtype_str = dtype_str[:asterix_pos]
        return dtype_str, name, value, items, const

    def _str_common(self, indent: int, dtype, name, value, const, item_str='') -> str:
        d = f"{colour.purple}{dtype}{colour.off}"

        i = f"{colour.purple}{item_str}{colour.off}"
        n = '' if name == '' else f" <{colour.green}{name}{colour.off}>"
        divider = '=' if const else ':'
        if isinstance(value, Array):
            v = f" {divider} {colour.cyan}{value.tolist()}{colour.off}"
        else:
            v = '' if value is None else f" {divider} {colour.cyan}{value}{colour.off}"
        indent_str = ' ' * indent_size * indent
        return f"{indent_str}'{d}{i}{n}{v}'"

    @staticmethod
    def _perhaps_convert_to_expression(s: Any) -> tuple[Any | None, None | Expression]:
        if not isinstance(s, str):
            return s, None
        try:
            e = Expression(s)
        except ValueError:
            return s, None
        return None, e

    def _parse_common(self, b: Bits, vars_: dict[str, Any]) -> int:
        if self.const:
            value = b[:len(self._bits)]
            if value != self._bits:
                raise ValueError(f"Read value '{value}' when '{self._bits}' was expected.")
            return len(self._bits)
        if self.dtype_expression is not None:
            self.dtype = Dtype(self.dtype, self.dtype_expression.safe_eval(vars_))
        self._bits = b[:self.dtype.bitlength]
        if self.name != '':
            vars_[self.name] = self.value
        return self.dtype.bitlength

    def _build_common(self, values: list[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        if self.const and self.value is not None:
            return self._bits, 0
        if self.value_expression is not None:
            self._setvalue(self.value_expression.safe_eval(vars_))
        elif self.name in kwargs.keys():
            self._setvalue(kwargs[self.name])
            return self._bits, 0
        else:
            self._setvalue(values[index])
        if self.name != '':
            vars_[self.name] = self.value
        return self._bits, 1


class Field(SingleDtypeField):
    def __init__(self, dtype: Dtype | str, name: str = '', value: Any = None, const: bool | None = None) -> None:
        super().__init__(dtype, name, value, const)
        self.value, self.value_expression = Field._perhaps_convert_to_expression(value)

    @classmethod
    def fromstring(cls, s: str, /):
        dtype, name, value, items, const = cls._parse_field_str(s)
        if items != 1:
            raise ValueError(f"Field '{s}' should not have a * in its definition. Perhaps you meant to use FieldArray?")
        p = dtype.find('{')
        if p == -1:
            try:
                dtype = Dtype(dtype)
            except ValueError:
                bits = Bits(dtype)  # TODO: change to  bits = Bits.fromstring(dtype)
                return cls(Dtype('bits'), name, bits, const)
        else:
            _ = Dtype(dtype[:p])  # Check that the dtype is valid even though we don't yet know its length.
        return cls(dtype, name, value, const)

    @classmethod
    def frombits(cls, b: Bits | str | bytes | bytearray, /, name: str = ''):
        b = Bits(b)
        return cls(Dtype('bits'), name, b)

    @classmethod
    def frombytes(cls, b: bytes | bytearray, /, name: str = ''):
        return cls(Dtype('bytes'), name, b)

    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        return self._parse_common(b, vars_)

    def _build(self, values: list[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        return self._build_common(values, index, vars_, kwargs)

    def _getvalue(self) -> Any:
        return self.dtype.get_fn(self._bits) if self._bits is not None else None
        # TODO: change to return self.dtype.parse(self._bits) if self._bits is not None else None

    def _setvalue(self, value: Any) -> None:
        if value is None:
            self._bits = None
            return
        try:
            b = Bits()
            self.dtype.set_fn(b, value)
            self._bits = b
            # TODO: Change to    self._bits = self.dtype.build(value)
        except ValueError:
            raise ValueError(f"Can't use the value '{value}' with the dtype {self.dtype}.")

    value = property(_getvalue, _setvalue)

    def _str(self, indent: int) -> str:
        return self._str_common(indent, self.dtype, self.name, self.value, self.const)

    def __eq__(self, other: Any) -> bool:
        if self.dtype != other.dtype:
            return False
        if self._bits != other._bits:
            return False
        return True


class FieldArray(SingleDtypeField):
    def __init__(self, dtype: Dtype | str, items: str | int, name: str = '', value: Any = None, const: bool | None = None) -> None:
        super().__init__(dtype, name, value, const)
        try:
            self.items, self.items_expression = int(items), None
        except ValueError:
            self.items, self.items_expression = FieldArray._perhaps_convert_to_expression(items)
        self.value, self.value_expression = FieldArray._perhaps_convert_to_expression(value)

    @classmethod
    def fromstring(cls, s: str, /):
        dtype, name, value, items, const = cls._parse_field_str(s)
        p = dtype.find('{')
        if p == -1:
            try:
                dtype = Dtype(dtype)
            except ValueError:
                bits = Bits.fromstring(dtype)
                return cls(Dtype('bits'), items, name, bits, const)
        return cls(dtype, items, name, value, const)

    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        if self.items_expression is not None:
            self.items = self.items_expression.safe_eval(vars_)
        return self._parse_common(b, vars_)

    def _build(self, values: list[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        if self.items_expression is not None:
            self.items = self.items_expression.safe_eval(vars_)
        return self._build_common(values, index, vars_, kwargs)

    def _getvalue(self) -> Any:
        return Array(self.dtype, self._bits) if self._bits is not None else None

    def _setvalue(self, value: Any) -> None:
        if value is None:
            self._bits = None
            return
        a = Array(self.dtype, value)
        if len(a) != self.items:
            raise ValueError(f"For FieldArray {self}, {len(a)} values were provided, but expected {self.items}.")
        self._bits = a.data

    value = property(_getvalue, _setvalue)

    def _str(self, indent: int) -> str:
        if self.items_expression is not None:
            item_str = self.items_expression
        else:
            item_str = str(self.items)
        item_str = f" * {item_str}"
        return self._str_common(indent, self.dtype, self.name, self.value, self.const, item_str)

    def __eq__(self, other: Any) -> bool:
        if self.dtype != other.dtype:
            return False
        x = self.value
        y = other.value
        if isinstance(x, Array):
            if not isinstance(y, Array):
                return False
            if not x.equals(y):
                return False
        elif x != y:
            return False
        return True



class Find(FieldType):

    def __init__(self, bits: Bits | str, bytealigned: bool = True, name: str = ''):
        super().__init__()
        self.bits_to_find = Bits(bits)
        self.bytealigned = bytealigned
        self.name = name
        self._value = None

    def _build(self, values: list[Any], index: int, _vars: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        return Bits(), 0

    def bits(self) -> Bits:
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
        return []

    def _str(self, indent: int) -> str:
        indent_str = ' ' * indent_size * indent
        name_str = '' if self.name == '' else f"'{colour.blue}{self.name}{colour.off}',"
        find_str = f"'{colour.green}{str(self.bits_to_find)}{colour.off}'"
        s = f"{indent_str}{self.__class__.__name__}({name_str}{find_str})"
        return s

    def _getvalue(self) -> int | None:
        return self._value

    value = property(_getvalue, None)  # Don't allow the value to be set elsewhere