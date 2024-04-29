from __future__ import annotations
import abc
from bitstring import Bits, Dtype, Array

from .common import colour, Expression, _indent
from typing import Any, Sequence


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
    def _build(self, values: Sequence[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        """Build the field from the values list, starting at index. Return the bits and the number of values used."""
        ...

    def build(self, values: Sequence[Any] | None = None, /,  **kwargs) -> Bits:
        if kwargs is None:
            kwargs = {}
        if values is None:
            return self._build([], 0, {}, kwargs)[0]
        try:
            bits, values_used = self._build(values, 0, {}, kwargs)
        except TypeError as e:
            if not isinstance(values, Sequence):
                raise TypeError(f"The values parameter must be a sequence (e.g. a list or tuple), not a {type(values)}.")
            raise e
        return bits

    @abc.abstractmethod
    def tobits(self) -> Bits:
        """Return the bits that represent the field."""
        ...

    def tobytes(self) -> bytes:
        """Return the bytes that represent the field. Pads with up to 7 zero bits if necessary."""
        b = self.tobits()
        return b.tobytes()

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


class SingleDtypeField(FieldType):
    """Holds the common code for other Field classes with a single Dtype.
    This class should not be used directly."""

    def __init__(self, dtype: Dtype | str, name: str = '', value: Any = None, const: bool | None = None) -> None:
        self._bits = None
        self.dtype = dtype
        self.dtype_length_expression = None
        if isinstance(self.dtype, str):
            p = self.dtype.find('{')
            if p != -1:
                self.dtype_length_expression = Expression(self.dtype[p:])
                self.dtype = Dtype(self.dtype[:p])
            else:
                try:
                    self.dtype = Dtype(dtype)
                except ValueError:
                    raise ValueError(f"Can't convert '{dtype}' string to a Dtype.")
        self.name = name

        if self.dtype_length_expression is None and self.dtype.length == 0:
            raise ValueError(f"A field's dtype cannot have a length of zero (dtype = {self.dtype}).")
        if const is None:
            self.const = value is not None
        else:
            if value is None:
                raise ValueError(f"Can't set a field to be constant if it has no value.")
            self.const = const

    def tobits(self) -> Bits:
        return self._bits if self._bits is not None else Bits()

    def clear(self) -> None:
        if not self.const:
            self._setvalue(None)

    def flatten(self) -> list[FieldType]:
        return [self]

    @staticmethod
    def _find_symbols(s: str) -> dict[str, int | None]:
        symbols = [s for s in ":=~[];"]
        symbol_pos: dict[str, int | None] = {symbol: None for symbol in symbols}
        inside_braces = False
        before_equals = True
        for pos, char in enumerate(s):
            if char == '{':
                if inside_braces:
                    raise ValueError(f"Two consecutive opening braces found in '{s}'.")
                inside_braces = True
            if char == '}':
                if not inside_braces:
                    raise ValueError(f"Closing brace found with no matching opening brace in '{s}'.")
                inside_braces = False
            if not inside_braces and char in symbols:
                if before_equals:
                    if symbol_pos[char] is not None:
                        raise ValueError(f"More than one '{char}' found in '{s}'.")
                    symbol_pos[char] = pos
                if char in '~=':
                    before_equals = False
        return symbol_pos

    @staticmethod
    def _parse_field_array_str(dtype_str: str) -> tuple[str, str, str, int, bool | None]:
        # The string has the form 'name: [dtype; items] = value' for a FieldArray.
        # With the name: and value being optional.
        # But there may be chars inside {} sections that should be ignored.
        symbol_pos = SingleDtypeField._find_symbols(dtype_str)

        value = const = None
        name = ''

        # Check to see if it includes a value:
        tilde_pos = symbol_pos['~']
        equals_pos = symbol_pos['=']
        if tilde_pos is not None and equals_pos is not None:
            raise ValueError(f"Both '=' and '~' were found in '{dtype_str}'. "
                             f"Use '=' before values that are constant, otherwise use '~'.")
        if tilde_pos is not None or equals_pos is not None:
            const = equals_pos is not None
            value_pos = tilde_pos if tilde_pos is not None else equals_pos
            value = dtype_str[value_pos + 1:]
            dtype_str = dtype_str[:value_pos]  # Cut off the value part at the end.

        # Check if it has a name:
        colon_pos = symbol_pos[':']
        if colon_pos is not None:
            name = dtype_str[:colon_pos]
            name = name.strip()

        # Check if it is an array:
        if (lbracket_pos := symbol_pos['[']) is not None:
            if (rbracket_pos := symbol_pos[']']) is None:
                raise ValueError(f"An opening '[' was supplied in the field string '{dtype_str}' but without a closing ']'.")
            semicolon_pos = symbol_pos[';']
            if semicolon_pos is None or semicolon_pos > rbracket_pos or semicolon_pos < lbracket_pos:
                raise ValueError(f"An array field must have a ';' between the dtype and the number of items. For example '[u8; 10]'.")
            items = dtype_str[semicolon_pos + 1:rbracket_pos]
            dtype_str = dtype_str[lbracket_pos + 1:semicolon_pos]  # Cut off the items part.
        else:
            raise ValueError(f"An array field must have a '[dtype; items]' in the field string. "
                             f"None was found in '{dtype_str}'.")

        return dtype_str, name, value, items, const

    @staticmethod
    def _parse_field_str(dtype_str: str) -> tuple[str, str, str, bool | None]:
        # The string has the form 'name: dtype = value' for a Field
        # With the name and value being optional.
        # But there may be chars inside {} sections that should be ignored.
        symbol_pos = SingleDtypeField._find_symbols(dtype_str)

        value = const = None
        name = ''

        # Check to see if it includes a value:
        tilde_pos = symbol_pos['~']
        equals_pos = symbol_pos['=']
        if tilde_pos is not None and equals_pos is not None:
            raise ValueError(f"Both '=' and '~' were found in '{dtype_str}'. "
                             f"Use '=' before values that are constant, otherwise use '~'.")
        if tilde_pos is not None or equals_pos is not None:
            const = equals_pos is not None
            value_pos = tilde_pos if tilde_pos is not None else equals_pos
            value = dtype_str[value_pos + 1:].strip()
            dtype_str = dtype_str[:value_pos]  # Cut off the value part at the end.

        # Check if it has a name:
        colon_pos = symbol_pos[':']
        if colon_pos is not None:
            name = dtype_str[:colon_pos]
            name = name.strip()
            dtype_str = dtype_str[colon_pos + 1:]  # Cut off the name part.

        return dtype_str, name, value, const

    def _str_common(self, dtype, name, value, const, item_str='') -> str:
        if item_str == '':
            d = f"{colour.purple}{dtype}{colour.off}"
        else:
            d = f"{colour.purple}[{dtype}; {item_str}]{colour.off}"
        n = '' if name == '' else f"{colour.green}{name}{colour.off}: "
        divider = '=' if const else '~'
        if isinstance(value, Array):
            v = f" {divider} {colour.cyan}{value.tolist()}{colour.off}"
        else:
            v = '' if value is None else f" {divider} {colour.cyan}{value}{colour.off}"
        return f"{n}{d}{v}"

    def _repr_common(self, dtype, name, value, const, item_str='') -> str:
        divider = '=' if const else '~'
        if name != '':
            name = f"{name}: "
        if item_str != '':
            dtype = f"[{dtype}; {item_str}]"
        if isinstance(value, Array):
            v = f" {divider} {value.tolist()}"
        else:
            v = '' if value is None else f" {divider} {value}"
        return f"'{name}{dtype}{v}'"

    def _parse_common(self, b: Bits, vars_: dict[str, Any]) -> int:
        if self.const:
            value = b[:len(self._bits)]
            if value != self._bits:
                raise ValueError(f"Read value '{value}' when '{self._bits}' was expected.")
            return len(self._bits)
        if self.dtype_length_expression is not None:
            self.dtype = Dtype(self.dtype.name, self.dtype_length_expression.safe_eval(vars_))
        self._bits = b[:self.dtype.bitlength]
        if self.name != '':
            vars_[self.name] = self.value
        return self.dtype.bitlength

    def _build_common(self, values: Sequence[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        if self.const and self.value is not None:
            if self.name != '':
                vars_[self.name] = self.value
            return self._bits, 0
        if self.value_expression is not None:
            self._setvalue(self.value_expression.safe_eval(vars_))
        elif self.name in kwargs.keys():
            self._setvalue(kwargs[self.name])
            vars_[self.name] = self.value
            return self._bits, 0
        else:
            self._setvalue(values[index])
        if self.name != '':
            vars_[self.name] = self.value
        return self._bits, 1


class Field(SingleDtypeField):
    def __init__(self, dtype: Dtype | str, name: str = '', value: Any = None, const: bool | None = None) -> None:
        super().__init__(dtype, name, value, const)
        self.value, self.value_expression = _perhaps_convert_to_expression(value)

    @classmethod
    def fromstring(cls, s: str, /):
        dtype, name, value, const = cls._parse_field_str(s)
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

    def _build(self, values: Sequence[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        return self._build_common(values, index, vars_, kwargs)

    def _getvalue(self) -> Any:
        return self.dtype.parse(self._bits) if self._bits is not None else None

    def _setvalue(self, value: Any) -> None:
        if value is None:
            self._bits = None
            return
        try:
            self._bits = self.dtype.build(value)
        except ValueError:
            raise ValueError(f"Can't use the value '{value}' with the dtype {self.dtype}.")

    value = property(_getvalue, _setvalue)

    def _str(self, indent: int) -> str:
        return f"{_indent(indent)}{self._str_common(self.dtype, self.name, self.value, self.const)}"

    # This simple repr used when field is part of a larger object
    def _repr(self, indent: int) -> str:
        return f"{_indent(indent)}{self._repr_common(self.dtype, self.name, self.value, self.const)}"

    # This repr is used when the field is the top level object
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.fromstring('{self.__str__()}')"

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
            self.items, self.items_expression = _perhaps_convert_to_expression(items)
        self.value, self.value_expression = _perhaps_convert_to_expression(value)

    @classmethod
    def fromstring(cls, s: str, /):
        dtype, name, value, items, const = cls._parse_field_array_str(s)
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
        if self.const:
            value = b[:len(self._bits)]
            if value != self._bits:
                raise ValueError(f"Read value '{value}' when '{self._bits}' was expected.")
            return len(self._bits)
        if self.dtype_length_expression is not None:
            self.dtype = Dtype(self.dtype, self.dtype_length_expression.safe_eval(vars_))
        self._bits = b[:self.dtype.bitlength * self.items]
        if self.name != '':
            vars_[self.name] = self.value
        return self.dtype.bitlength


    def _build(self, values: Sequence[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        if self.items_expression is not None:
            self.items = self.items_expression.safe_eval(vars_)
        return self._build_common(values, index, vars_, kwargs)

    def _getvalue(self) -> Any:
        return Array(self.dtype, self._bits).tolist() if self._bits is not None else None

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
        return f"{_indent(indent)}{self._str_common(self.dtype, self.name, self.value, self.const, item_str)}"

    def _repr(self, indent: int) -> str:
        if self.items_expression is not None:
            item_str = self.items_expression
        else:
            item_str = str(self.items)
        return f"{_indent(indent)}{self._repr_common(self.dtype, self.name, self.value, self.const, item_str)}"

    # This repr is used when the field is the top level object
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.fromstring('{self.__str__()}')"

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

    def _build(self, values: Sequence[Any], index: int, _vars: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        return Bits(), 0

    def tobits(self) -> Bits:
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

