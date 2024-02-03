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
            cls.blue = cls.purple = cls.green = cls.off = ''
        return x

colour = Colour(True)

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
    def build(self, *value) -> None:
        ...

    @abc.abstractmethod
    def value(self) -> Any:
        ...

    @abc.abstractmethod
    def bits(self) -> Bits | None:
        ...

    def bytes(self) -> bytes | None:
        b = self.bits()
        return b.tobytes() if b is not None else None

    @abc.abstractmethod
    def clear(self) -> None:
        ...

    def _get_name(self) -> str:
        return self._name

    def _set_name(self, val: str) -> None:
        if val != '' and not val.isidentifier():
            raise ValueError(f"The FieldType name '{val}' is not a valid Python identifier.")
        self._name = val

    name = property(_get_name, _set_name)



class Field(FieldType):
    def __init__(self, dtype: Dtype | Bits | str, name: str = '', value: Any = None, items: str | int = 1):
        self._bits = None
        self._value = None

        if isinstance(dtype, str):
            d, n, v, i = Field._parse_dtype_str(dtype)
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
        if value is not None:
            self._setvalue(value)


    def parse(self, b: Bits) -> int:
        if self._bits is not None:
            value = b[:len(self._bits)]
            if value != self._bits:
                raise ValueError
            return len(self._bits)
        if self.items == 1:
            self._value = self.dtype.get_fn(b[:self.dtype.bitlength])
            return self.dtype.bitlength
        else:
            self._setvalue(b[:self.dtype.bitlength * self.items])
            return self.dtype.bitlength * self.items

    def build(self, values: List | None = None) -> Bits:
        if self._bits is None:
            if values is None or len(values) < self.items:
                raise ValueError(f"Need {self.items} items to build the Field, but was supplied with '{values}'.")
            if self.items == 1:
                self._setvalue(values[0])
                values.pop(0)
            else:
                self._setvalue(values[0:self.items])
                del values[0:self.items]
        return self._bits

    def value(self):
        return self._getvalue()

    def bits(self) -> Bits | None:
        return self._bits

    def clear(self) -> None:
        if self.dtype.name != 'bits':
            self._setvalue(None)

    @staticmethod
    def _parse_dtype_str(dtype_str: str) -> Tuple[str, str | None, str | None, int]:
        # The string has the form 'dtype [* items] [<name>] [= value]'
        # But there may be chars inside {} sections that should be ignored.
        # So we scan to find first real *, <, > and =
        asterix_pos = -1
        lessthan_pos = -1
        greaterthan_pos = -1
        equals_pos = -1
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
                equals_pos = pos

        name = value = None
        items = 1
        # Check to see if it includes a value:
        if equals_pos != -1:
            value = dtype_str[equals_pos + 1:]
            dtype_str = dtype_str[:equals_pos]
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
        return dtype_str, name, value, items

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

    def __str__(self) -> str:
        d = f"{colour.purple}{self.dtype}{colour.off}"
        i = '' if self.items == 1 else f" * {colour.purple}{self.items}{colour.off}"
        n = '' if self.name is None else f" <{colour.green}{self.name}{colour.off}>"
        if isinstance(self.value(), Array):
            v = f" = {colour.cyan}{self.value().tolist()}{colour.off}"
        else:
            v = '' if self.value() is None else f" = {colour.cyan}{self.value()}{colour.off}"
        return f"'{d}{i}{n}{v}'"

    def __repr__(self) -> str:
        return f"Field({self.__str__()})"

    def __eq__(self, other: Any) -> bool:
        if self.dtype != other.dtype:
            return False
        if isinstance(self.value(), Array):
            if not isinstance(other.value(), Array):
                return False
            if not self.value().equals(other.value()):
                return False
        elif self.value() != other.value():
            return False
        return True


class Format(FieldType):

    def __init__(self, fieldtypes: Sequence[FieldType | str | Dtype | Bits] | None = None, name: str = '') -> None:
        if fieldtypes is None:
            fieldtypes = []
        self.name = name
        self.fieldtypes = []
        self.vars = {}
        for fieldtype in fieldtypes:
            if isinstance(fieldtype, (str, Dtype, Bits)):
                fieldtype = Field(fieldtype)
            if not isinstance(fieldtype, FieldType):
                raise ValueError(f"Invalid Field of type {type(fieldtype)}.")
            self.fieldtypes.append(fieldtype)

    def build(self, values: List | None = None) -> Bits:
        for fieldtype in self.fieldtypes:
            fieldtype.build(values)
        return self.bits()

    def bits(self) -> Bits:
        return Bits().join(fieldtype.bits() for fieldtype in self.fieldtypes)

    def tobytes(self) -> bytes:
        return self.bits().bytes()

    def parse(self, b: Bits) -> int:
        pos = 0
        for fieldtype in self.fieldtypes:
            pos += fieldtype.parse(b[pos:])
        return pos

    def value(self) -> List[Any]:
        return [f.value() for f in self.fieldtypes]

    def clear(self) -> None:
        for fieldtype in self.fieldtypes:
            fieldtype.clear()

    def _str(self, indent: int=0) -> str:
        indent_size = 7  # To line things up under the 'Format('
        indent_str = ' ' * indent_size * indent
        name_str = '' if self.name is None else "'{colour.blue}{self.name}{colour.off}',"
        s = f"{indent_str}{self.__class__.__name__}({name_str}\n"
        for fieldtype in self.fieldtypes:
            if isinstance(fieldtype, Format):
                s += fieldtype._str(indent + 1)
            else:
                s += ' ' * indent_size + f"{indent_str}{fieldtype},\n"
        s += f"{indent_str})\n"
        return s

    def __eq__(self, other):
        return self.flatten() == other.flatten()

    def __str__(self) -> str:
        return self._str()

    def __repr__(self) -> str:
        return self.__str__()

    def __iadd__(self, other: Format | Dtype | Bits | str | Field) -> Struct:
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

    def __getitem__(self, key) -> Any:
        if self.fieldtypes is None:
            raise ValueError(f'{self.__class__.__name__} is empty')
        if isinstance(key, int):
            fieldtype = self.fieldtypes[key]
            return fieldtype

        for fieldtype in self.fieldtypes:
            if fieldtype.name == key:
                return fieldtype
        raise KeyError(key)

    def __setitem__(self, key, value) -> None:
        if self.fieldtypes is None:
            raise ValueError('Format is empty')
        if isinstance(key, int):
            self.fieldtypes[key]._value = value
            return
        for fieldtype in self.fieldtypes:
            if fieldtype.name == key:
                fieldtype._setvalue(value)
                return
        raise KeyError(key)

    def flatten(self) -> List[FieldType]:
        # Just return a flat list of fields (no Format objects, no name)
        flattened_fields = []
        for fieldtype in self.fieldtypes:
            if hasattr(fieldtype, 'flatten'):
                flattened_fields.extend(fieldtype.flatten())
            else:
                flattened_fields.append(fieldtype)
        return flattened_fields

    def append(self, value: Any) -> None:
        self.__iadd__(value)

    @staticmethod
    def _safe_eval(code: CodeType, vars_: Dict) -> Any:
        return eval(code, {"__builtins__": {}}, vars_)


class Repeat(FieldType):

    def __init__(self, count: int | str | Iterable, fieldtype: FieldType | str | Dtype | Bits):
        self.count = count
        if isinstance(fieldtype, (str, Dtype, Bits)):
            fieldtype = Field(fieldtype)
        if not isinstance(fieldtype, FieldType):
            raise ValueError(f"Invalid Field of type {type(fieldtype)}.")
        self.fieldtype_array = []
        for _ in range(count):
            self.fieldtype_array.append(copy.copy(fieldtype))

    def value(self):
        return [f.value() for f in self.fieldtype_array]

    def build(self):
        pass

    def bits(self) -> Bits | None:
        pass

    def clear(self) -> None:
        for fieldtype in self.fieldtype_array:
            fieldtype.clear()

    def parse(self, b: Bits):
        pos = 0
        for fieldtype in self.fieldtype_array:
            pos += fieldtype.parse(b[pos:])
        return pos