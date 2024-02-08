from __future__ import annotations
import abc
from bitstring import Bits, Dtype, Array
from typing import Any, Tuple, List, Dict

from .common import colour, Expression, indent_size

class FieldType(abc.ABC):
    @abc.abstractmethod
    def _parse(self, b: Bits, vars_: Dict[str, Any]) -> int:
        ...

    def parse(self, b: Bits) -> int:
        return self._parse(b, {})

    @abc.abstractmethod
    def _build(self, values: List[Any], index: int, vars_: Dict[str, Any]) -> Tuple[Bits, int]:
        ...

    def build(self, values: List[Any]) -> Bits:
        return self._build(values, 0, {})[0]

    @abc.abstractmethod
    def bits(self) -> Bits:
        ...

    def bytes(self) -> bytes:
        b = self.bits()
        return b.tobytes()

    @abc.abstractmethod
    def clear(self) -> None:
        ...

    @abc.abstractmethod
    def _str(self, indent: int) -> str:
        ...

    @abc.abstractmethod
    def flatten(self) -> List[FieldType]:
        ...

    @abc.abstractmethod
    def _getvalue(self) -> Any:
        ...

    @abc.abstractmethod
    def _setvalue(self, value: Any) -> None:
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


class Field(FieldType):
    def __init__(self, dtype: Dtype | Bits | str, name: str = '', value: Any = None, items: str | int = 1, const: bool | None = None) -> None:
        self._bits = None
        if isinstance(dtype, str):
            d, n, v, i, c = Field._parse_dtype_str(dtype)
            if n != '':
                if name != '':
                    raise ValueError(
                        f"A name was supplied in the formatted dtype '{dtype}' as well as in the name parameter.")
                else:
                    name = n
            if v is not None:
                if value is not None:
                    raise ValueError(
                        f"A value was supplied in the formatted dtype '{dtype}' as well as in the value parameter.")
                else:
                    value = v
            if i != 1:
                if items != 1:
                    raise ValueError(f"An multiplier was supplied in the formatted dtype '{dtype}' as well as in the items parameter.")
                else:
                    items = i
            if c is not None:
                if const is not None and c is not const:
                    raise ValueError(f"A const value was supplied that conflicts with the formatted dtype '{dtype}'.")
                else:
                    const = c
            dtype = d
            # Try to convert to Bits type first
            try:
                self._bits = Bits(dtype)
            except ValueError:
                try:
                    self.dtype = Dtype(dtype)
                except ValueError:
                    raise ValueError(f"Can't convert '{dtype}' to either a Bits or a Dtype.")
            else:
                self.dtype = Dtype('bits', len(self._bits))
                value = self._bits
        elif isinstance(dtype, Bits):
            self.dtype = Dtype('bits', len(dtype))
            value = dtype
        elif isinstance(dtype, Dtype):
            self.dtype = dtype
        else:
            raise ValueError(f"Can't use '{dtype}' of type '{type(dtype)} to initialise Field.")
        self.name = name
        try:
            self.items = int(items)
            self.items_expression = None
        except ValueError:
            self.items_expression = Expression(items)
            self.items = None
        if self.dtype.length == 0:
            raise ValueError(f"A field's dtype cannot have a length of zero (dtype = {self.dtype}).")
        if const is None:
            self.const = value is not None
        else:
            self.const = const
        self.value = value

    @classmethod
    def fromstring(cls, s: str):
        dtype, name, value, items, const = Field._parse_dtype_str(s)
        try:
            dtype = Dtype(dtype)
        except ValueError:
            bits = Bits(dtype)
            return cls(Dtype('bits'), name, bits, items, const)
        return cls(dtype, name, value, items, const)

    @classmethod
    def frombits(cls, b: Bits, name: str = ''):
        b = Bits(b)
        return cls(Dtype('bits'), name, b)

    def _parse(self, b: Bits, vars_: Dict[str, Any]) -> int:
        if self.const:
            value = b[:len(self._bits)]
            if value != self._bits:
                raise ValueError(f"Read value '{value}' when '{self._bits}' was expected.")
            return len(self._bits)
        if self.items_expression is not None:
            self.items = self.items_expression.safe_eval(vars_)
        if self.items == 1:
            self._setvalue(self.dtype.get_fn(b[:self.dtype.bitlength]))
            if self.name != '':
                vars_[self.name] = self.value
            return self.dtype.bitlength
        else:
            self._setvalue(b[:self.dtype.bitlength * self.items])
            return self.dtype.bitlength * self.items

    def _build(self, values: List[Any], index: int, vars_: Dict[str, Any]) -> Tuple[Bits, int]:
        if self.const or self._bits:
            return self._bits, 0
        if self.items_expression is not None:
            self.items = self.items_expression.safe_eval(vars_)
        self._setvalue(values[index])
        if self.name != '':
            vars_[self.name] = self.value
        return self._bits, 1

    def bits(self) -> Bits:
        return self._bits if self._bits is not None else Bits()

    def clear(self) -> None:
        if not self.const:
            self._setvalue(None)
        if self.items_expression is not None:
            self.items_expression.clear()
            self.items = None

    def flatten(self) -> List[FieldType]:
        return [self]

    @staticmethod
    def _parse_dtype_str(dtype_str: str) -> Tuple[str, str | None, str, int, bool | None]:
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

    def _getvalue(self) -> Any:
        if self.items == 1:
            return self._value
        else:
            return None if self._value is None else self._value

    def _setvalue(self, value: Any) -> None:
        if self.dtype is None:
            raise ValueError(f"Can't set a value for field without a Dtype.")
        if value is None:
            self._value = None
            self._bits = None
            return
        if self.items == 1:
            b = Bits()
            try:
                self.dtype.set_fn(b, value)
                self._bits = b
            except ValueError:
                raise ValueError(f"Can't use the value '{value}' with the dtype {self.dtype}.")
            self._value = self.dtype.get_fn(self._bits)
        else:
            a = Array(self.dtype, value)
            if len(a) != self.items:
                raise ValueError(f"For Field {self}, {len(a)} values were provided, but expected {self.items}.")
            self._value = a
            self._bits = a.data

    value = property(_getvalue, _setvalue)

    def _str(self, indent: int) -> str:
        d = f"{colour.purple}{self.dtype}{colour.off}"
        if self.items_expression is not None:
            item_str = self.items_expression
        else:
            item_str = '' if self.items == 1 else str(self.items)
        i = '' if item_str == '' else f" * {colour.purple}{item_str}{colour.off}"
        n = '' if self.name == '' else f" <{colour.green}{self.name}{colour.off}>"
        divider = '=' if self.const else ':'
        if isinstance(self.value, Array):
            v = f" {divider} {colour.cyan}{self.value.tolist()}{colour.off}"
        else:
            v = '' if self.value is None else f" {divider} {colour.cyan}{self.value}{colour.off}"
        indent_str = ' ' * indent_size * indent
        return f"{indent_str}'{d}{i}{n}{v}'"

    def __repr__(self) -> str:
        return f"Field({self.__str__()})"

    def __eq__(self, other: Any) -> bool:
        if self.dtype != other.dtype:
            return False
        if isinstance(self.value, Array):
            if not isinstance(other.value, Array):
                return False
            if not self.value.equals(other.value):
                return False
        elif self.value != other.value:
            return False
        return True


class Find(FieldType):

    def __init__(self, bits: Bits | str, bytealigned: bool = True, name: str = ''):
        super().__init__()
        self.bits_to_find = Bits(bits)
        self.bytealigned = bytealigned
        self.name = name

    def _build(self, values: List[Any], index: int, _vars: Dict[str, Any]) -> Tuple[Bits, int]:
        return Bits(), 0

    def bits(self) -> Bits:
        return Bits()

    def clear(self) -> None:
        self._setvalue(None)

    def _parse(self, b: Bits, vars_: Dict[str, Any]) -> int:
        p = b.find(self.bits_to_find, bytealigned=self.bytealigned)
        if p:
            self._setvalue(p[0])
            return p[0]
        self._setvalue(None)
        return 0

    def flatten(self) -> List[FieldType]:
        return []

    def _str(self, indent: int) -> str:
        indent_str = ' ' * indent_size * indent
        name_str = '' if self.name == '' else f"'{colour.blue}{self.name}{colour.off}',"
        find_str = f"'{colour.green}{str(self.bits_to_find)}{colour.off}'"
        s = f"{indent_str}{self.__class__.__name__}({name_str}{find_str})"
        return s

    def _setvalue(self, val: int | None) -> None:
        self._value = val

    def _getvalue(self) -> int | None:
        return self._value

    value = property(_getvalue, None)  # Don't allow the value to be set elsewhere