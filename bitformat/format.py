from __future__ import annotations

from bitstring import Bits, Dtype, Array
from typing import Sequence, Any, Iterator, Tuple, List, Dict
from types import CodeType
import copy
import ast

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


class Field:
    def __init__(self, dtype: Dtype | Bits | str, name: str | None = None, value: Any = None, items: str | int = 1):
        if name == '':
            name = None
        self._bits = None
        self._value = None

        if isinstance(dtype, str):
            d, n, v, i = Field._parse_dtype_str(dtype)
            if n is not None:
                if name is not None:
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
        if name is not None and not name.isidentifier():
            raise ValueError(f"The Field name '{name}' is not a valid Python identifier.")
        self.name = name
        try:
            items = int(items)
        except ValueError:
            items = _compile_safe_eval(items)
        self.items = items
        if self.dtype.length == 0:
            raise ValueError(f"A field's dtype cannot have a length of zero (dtype = {self.dtype}).")
        if value is not None:
            self._setvalue(value)

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
            return None if self._value is None else self._value.tolist()

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

    def _getbits(self) -> Bits | None:
        return self._bits

    value = property(_getvalue, _setvalue)
    bits = property(_getbits)


    def __str__(self) -> str:
        d = f"{colour.purple}{self.dtype}{colour.off}"
        i = '' if self.items == 1 else f" * {colour.purple}{self.items}{colour.off}"
        n = '' if self.name is None else f" <{colour.green}{self.name}{colour.off}>"
        if isinstance(self.value, Array):
            v = f" = {colour.cyan}{self.value.tolist()}{colour.off}"
        else:
            v = '' if self.value is None else f" = {colour.cyan}{self.value}{colour.off}"
        return f"'{d}{i}{n}{v}'"

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


class Format:

    def __init__(self, name: str | None = None,
                 fields: Sequence[Field | Format | str | Dtype | Bits] | None = None) -> None:
        self.name = name
        if self.name == '':
            self.name = None
        if fields is None:
            fields = []

        self.fields = []
        self.vars = {}
        for field in fields:
            if isinstance(field, Format):
                self.fields.append(field)
                continue
            if isinstance(field, Field):
                pass
            elif isinstance(field, (str, Dtype, Bits)):
                field = Field(field)
            else:
                raise ValueError(f"Invalid Field of type {type(field)}.")
            self.fields.append(field)



    def _str(self, indent: int=0) -> str:
        indent_size = 7  # To line things up under the 'Format('
        indent_str = ' ' * indent_size * indent
        s = f"{indent_str}Format('{colour.blue}{self.name}{colour.off}',\n"
        for field in self.fields:
            if isinstance(field, Format):
                s += field._str(indent + 1)
            else:
                s += ' ' * indent_size + f"{indent_str}{field},\n"
        s += f"{indent_str})\n"
        return s

    def __eq__(self, other):
        return self.flatten() == other.flatten()

    def __str__(self) -> str:
        return self._str()

    def __repr__(self) -> str:
        return self.__str__()

    def __iadd__(self, other: Format | Dtype | Bits | str | Field) -> Format:
        if isinstance(other, Format):
            self.fields.append(copy.deepcopy(other))
            return self
        if isinstance(other, Field):
            self.fields.append(copy.deepcopy(other))
            return self
        field = Field(other)
        self.fields.append(field)
        return self

    def __add__(self, other: Format | Dtype | Bits | str | Field) -> Format:
        x = copy.deepcopy(self)
        x += other
        return x

    def __getitem__(self, key) -> Any:
        if self.fields is None:
            raise ValueError('Format is empty')
        if isinstance(key, int):
            field = self.fields[key]
            if isinstance(field, Field):
                return field.value
            if isinstance(field, Format):
                return field
        for field in self.fields:
            if field.name == key:
                if isinstance(field, Field):
                    return field.value
                if isinstance(field, Format):
                    return field
        raise KeyError(key)

    def __setitem__(self, key, value) -> None:
        if self.fields is None:
            raise ValueError('Format is empty')
        if isinstance(key, int):
            self.fields[key].value = value
            return
        for field in self.fields:
            if field.name == key:
                field.value = value
                return
        raise KeyError(key)


    def flatten(self) -> List[Field]:
        # Just return a flat list of fields (no Format objects, no name)
        flattened_fields = []
        for field in self.fields:
            if isinstance(field, Format):
                flattened_fields.extend(field.flatten())
            else:
                flattened_fields.append(field)
        return flattened_fields

    def clear(self) -> None:
        for field in self.fields:
            if isinstance(field, Format):
                field.clear()
            else:
                if field.dtype.name != 'bits' and field.value is not None:
                    field.value = None

    def append(self, value: Any) -> None:
        self.__iadd__(value)

    @staticmethod
    def _safe_eval(code: CodeType, vars_: Dict) -> Any:
        return eval(code, {"__builtins__": {}}, vars_)

    def _build(self, value_iter: Iterator[Field]) -> Tuple[Sequence[Field | Format], Dict]:
        out_fields = []
        vars_ = {}
        for field in self.fields:
            if isinstance(field, Format):
                format_fields, vars_ = field._build(value_iter)
                f = object.__new__(Format)
                f.name = self.name
                f.fields = format_fields
                f.vars = vars_
                out_fields.append(f)
                continue
            if field.bits is None:
                if isinstance(field.items, CodeType):
                    field.items = Format._safe_eval(field.items, vars_)
                field = Field(field.dtype, field.name, next(value_iter), field.items)
            out_fields.append(field)
            if field.name is not None and field.value is not None:
                vars_[field.name] = field.value
        return out_fields, vars_

    def build(self, *values) -> Format:
        value_iter = iter(values)
        out_fields, vars_ = self._build(value_iter)
        f = object.__new__(Format)  # Avoiding expensive initialisation
        f.name = self.name
        f.fields = out_fields
        f.vars = vars_
        return f

    def tobits(self) -> Bits:
        errors = []
        if self.fields is None:
            return Bits()
        out_bits = []
        for field in self.fields:
            if isinstance(field, Format):
                out_bits.append(field.tobits())
                continue
            if field.bits is None:
                errors.append(f"Field {field} needs a value specified.")
            else:
                out_bits.append(field.bits)
        if errors:
            raise ValueError('\n'.join(errors))
        return Bits().join(out_bits)

    def tobytes(self) -> bytes:
        return self.tobits().tobytes()

    @staticmethod
    def _parse(fmt: Format, b: Bits, start: int, format_name_stack: List[str]) -> Tuple[Format, int]:
        pos = 0
        format_name_stack.append(fmt.name)
        for field in fmt.fields:
            if isinstance(field, Format):
                nested_format, pos = Format._parse(field, b, pos, format_name_stack)
                continue
            if field.bits is not None:
                value = b[start + pos: start + pos + len(field.bits)]
                pos += len(field.bits)
                if value != field.bits:
                    raise ValueError(f"Field {':'.join(colour.blue + fn + colour.off for fn in format_name_stack)}:{field} at bit position {start + pos} does not match parsed bits {value}.")
            else:
                if field.items == 1:
                    field.value = field.dtype.get_fn(b[start + pos: start + pos + field.dtype.bitlength])
                else:
                    field.value = b[start + pos: start + pos + field.dtype.bitlength * field.items]
                pos += field.dtype.bitlength * field.items
        format_name_stack.pop()
        return fmt, start + pos

    def parse(self, b: Bits) -> Format:
        out_format = copy.deepcopy(self)
        f, pos = Format._parse(out_format, b, 0, [])
        return f
