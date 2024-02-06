from __future__ import annotations

from bitstring import Bits, Dtype, Array
from typing import Sequence, Any, Iterable, Tuple, List, Dict
from types import CodeType
import copy
import ast
import abc


class Colour:
    def __new__(cls, use_colour: bool) -> Colour:
        x = super().__new__(cls)
        if use_colour:
            cls.blue = '\033[34m'
            cls.purple = '\033[35m'
            cls.green = '\033[32m'
            cls.red = '\033[31m'
            cls.cyan = '\033[36m'
            cls.off = '\033[0m'
        else:
            cls.blue = cls.purple = cls.green = cls.red = cls.cyan = cls.off = ''
        return x

colour = Colour(True)
indent_size = 4


def _compile_safe_eval(s: str) -> CodeType:
    start = s.find('{')
    end = s.find('}')
    if start == -1 or end == -1:
        raise ValueError(f'Invalid expression: {s}. It should start and end with braces.')
    s = s[start + 1:end].strip()
    # Only allowing operations for integer maths or boolean comparisons.
    node_whitelist = {'BinOp', 'Name', 'Add', 'Expr', 'Mult', 'FloorDiv', 'Sub', 'Load', 'Module', 'Constant',
                      'UnaryOp', 'USub', 'Mod', 'Pow', 'BitAnd', 'BitXor', 'BitOr', 'And', 'Or', 'BoolOp', 'LShift',
                      'RShift',
                      'Eq', 'NotEq', 'Compare', 'LtE', 'GtE'}
    nodes_used = set([x.__class__.__name__ for x in ast.walk(ast.parse(s))])
    bad_nodes = nodes_used - node_whitelist
    if bad_nodes:
        raise ValueError(f"Disallowed operations used in expression '{s}'. Disallowed nodes were: {bad_nodes}.")
    if '__' in s:
        raise ValueError(f"Invalid expression: '{s}'. Double underscores are not permitted.")
    code = compile(s, "<string>", "eval")
    return code


class FieldType(abc.ABC):
    @abc.abstractmethod
    def parse(self, b: Bits) -> int:
        ...
    @abc.abstractmethod
    def build(self, values: List[Any] = []) -> Bits:
        ...

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
            if n is not None:
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
        items = int(items)
        self.items = items
        if self.dtype.length == 0:
            raise ValueError(f"A field's dtype cannot have a length of zero (dtype = {self.dtype}).")
        if const is None:
            self.const = value is not None
        else:
            self.const = const
        self.value = value


    def parse(self, b: Bits) -> int:
        if self.const:
            value = b[:len(self._bits)]
            if value != self._bits:
                raise ValueError(f"Read value '{value}' when '{self._bits}' was expected.")
            return len(self._bits)
        if self.items == 1:
            self._value = self.dtype.get_fn(b[:self.dtype.bitlength])
            return self.dtype.bitlength
        else:
            self._setvalue(b[:self.dtype.bitlength * self.items])
            return self.dtype.bitlength * self.items

    def build(self, values: List[Any] = []) -> Bits:
        if self._bits is None:
            if len(values) < self.items:
                raise ValueError(f"Need {self.items} items to build the Field, but was supplied with '{values}'.")
            if self.items == 1:
                self._setvalue(values[0])
                values.pop(0)
            else:
                self._setvalue(values[0:self.items])
                del values[0:self.items]
        return self._bits

    def bits(self) -> Bits:
        return self._bits if self._bits is not None else Bits()

    def clear(self) -> None:
        if not self.const:
            self._setvalue(None)

    def flatten(self) -> List[FieldType]:
        return [self]

    @staticmethod
    def _parse_dtype_str(dtype_str: str) -> Tuple[str, str | None, str | None, int, bool | None]:
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

        name = value = const = None
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
        i = '' if self.items == 1 else f" * {colour.purple}{self.items}{colour.off}"
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


class FieldListType(FieldType):

    def __init__(self):
        self.fieldtypes = []

    def build(self, values: List[Any] = []) -> Bits:
        for fieldtype in self.fieldtypes:
            fieldtype.build(values)
        return self.bits()

    def parse(self, b: Bits):
        pos = 0
        for fieldtype in self.fieldtypes:
            pos += fieldtype.parse(b[pos:])
        return pos

    def clear(self) -> None:
        for fieldtype in self.fieldtypes:
            fieldtype.clear()

    def __eq__(self, other):
        return self.flatten() == other.flatten()

    def _getvalue(self) -> List[Any]:
        return [f.value for f in self.fieldtypes]

    def _setvalue(self, val: List[Any]) -> None:
        if len(val) != len(self.fieldtypes):
            raise ValueError(f"Can't set {len(self.fieldtypes)} fields from {len(val)} values.")
        for i in range(len(val)):
            self.fieldtypes[i]._setvalue(val[i])

    def bits(self) -> Bits:
        return Bits().join(fieldtype.bits() for fieldtype in self.fieldtypes)

    def flatten(self) -> List[FieldType]:
        # Just return a flat list of fields
        flattened_fields = []
        for fieldtype in self.fieldtypes:
            flattened_fields.extend(fieldtype.flatten())
        return flattened_fields

    def __getitem__(self, key) -> Any:
        if isinstance(key, int):
            fieldtype = self.fieldtypes[key]
            return fieldtype

        for fieldtype in self.fieldtypes:
            if fieldtype.name == key:
                return fieldtype
        raise KeyError(key)

    def __setitem__(self, key, value) -> None:
        if isinstance(key, int):
            self.fieldtypes[key].value = value
            return
        for fieldtype in self.fieldtypes:
            if fieldtype.name == key:
                fieldtype.value = value
                return
        raise KeyError(key)

    value = property(_getvalue, _setvalue)

class Format(FieldListType):

    def __init__(self, fieldtypes: Sequence[FieldType | str | Dtype | Bits] | None = None, name: str = '') -> None:
        super().__init__()
        if fieldtypes is None:
            fieldtypes = []
        self.name = name
        self.vars = {}
        for fieldtype in fieldtypes:
            if isinstance(fieldtype, (str, Dtype, Bits)):
                fieldtype = Field(fieldtype)
            if not isinstance(fieldtype, FieldType):
                raise ValueError(f"Invalid Field of type {type(fieldtype)}.")
            self.fieldtypes.append(fieldtype)

    def _str(self, indent: int) -> str:
        indent_str = ' ' * indent_size * indent
        name_str = '' if self.name == '' else f"'{colour.blue}{self.name}{colour.off}',"
        s = f"{indent_str}{self.__class__.__name__}({name_str}\n"
        for fieldtype in self.fieldtypes:
            s += fieldtype._str(indent + 1) + ',\n'
        s += f"{indent_str})"
        return s

    def __iadd__(self, other: Format | Dtype | Bits | str | Field) -> Format:
        if isinstance(other, FieldType):
            self.fieldtypes.append(copy.deepcopy(other))
            return self
        field = Field(other)
        self.fieldtypes.append(field)
        return self

    def __add__(self, other: Format | Dtype | Bits | str | Field) -> Format:
        x = copy.deepcopy(self)
        x += other
        return x

    def append(self, value: Any) -> None:
        self.__iadd__(value)

    @staticmethod
    def _safe_eval(code: CodeType, vars_: Dict) -> Any:
        return eval(code, {"__builtins__": {}}, vars_)


class Repeat(FieldListType):

    def __init__(self, count: int | str | Iterable, fieldtype: FieldType | str | Dtype | Bits, name: str = ''):
        super().__init__()
        if isinstance(count, int):
            count = range(count)
        self.count = count
        self.name = name
        if isinstance(fieldtype, (str, Dtype, Bits)):
            fieldtype = Field(fieldtype)
        if not isinstance(fieldtype, FieldType):
            raise ValueError(f"Invalid Field of type {type(fieldtype)}.")
        for _ in count:
            self.fieldtypes.append(copy.copy(fieldtype))

    def _str(self, indent: int) -> str:
        indent_str = ' ' * indent_size * indent
        name_str = '' if self.name == '' else f"'{colour.blue}{self.name}{colour.off}',"
        count_str = f'{colour.green}{self.count!r}{colour.off},'
        s = f"{indent_str}{self.__class__.__name__}({name_str}{count_str}\n"
        for fieldtype in self.fieldtypes:
            s += fieldtype._str(indent + 1) + ',\n'
        s += f"{indent_str})"
        return s



class Find(FieldType):

    def __init__(self, bits: Bits | str, bytealigned: bool = True, name: str = ''):
        super().__init__()
        self.bits_to_find = Bits(bits)
        self.bytealigned = bytealigned
        self.name = name

    def build(self, values: List[Any] = []) -> Bits:
        return Bits()

    def bits(self) -> Bits:
        return Bits()

    def clear(self) -> None:
        self._setvalue(None)

    def parse(self, b: Bits):
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
