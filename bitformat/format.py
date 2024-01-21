from __future__ import annotations

from bitstring import Bits, Dtype
from typing import Sequence, Any, Iterator
import copy


class Colour:
    def __new__(cls, use_colour: bool) -> Colour:
        x = super().__new__(cls)
        if use_colour:
            cls.blue = '\033[34m'
            cls.purple = '\033[35m'
            cls.green = '\033[32m'
            cls.off = '\033[0m'
        else:
            cls.blue = cls.purple = cls.green = cls.off = ''
        return x

colour = Colour(True)


class Field:
    def __init__(self, dtype: Dtype | Bits | str, name: str | None = None, value: Any = None):
        if name == '':
            name = None
        self._bits = None
        self._value = None
        self.name = name

        if isinstance(dtype, str):
            # Check to see if it includes a value:
            q = dtype.find('=')
            if q != -1:
                if value is not None:
                    raise ValueError(f"A value was supplied in the formatted dtype '{dtype}' as well as in the value parameter.")
                value = dtype[q + 1:]
                dtype = dtype[:q]
            # Check if it has a name:
            name_start = dtype.find('<')
            if name_start != -1:
                name_end = dtype.find('>')
                if name_end == -1:
                    raise ValueError(f"An opening '<' was supplied in the formatted dtype '{dtype} but without a closing '>'.")
                if name is not None:
                    raise ValueError(f"A name was supplied in the formatted dtype '{dtype}' as well as in the name parameter.")
                self.name = dtype[name_start + 1:name_end]
                chars_after_name = dtype[name_end + 1:]
                if chars_after_name != '' and not chars_after_name.isspace():
                    raise ValueError(f"There should be no trailing characters after the <name>.")
                dtype = dtype[:name_start]
            # Try to convert to Bits type first
            try:
                self._bits = Bits(dtype)
            except ValueError:
                try:
                    self.dtype = Dtype(dtype)
                except ValueError:
                    raise ValueError(f"Can't convert '{dtype}' to either a Bits or a Dtype.")
                else:
                    if value is not None:
                        self.value = value
            else:
                self.dtype = Dtype('bits', len(self._bits))
                self.value = self._bits
        elif isinstance(dtype, Bits):
            self.dtype = Dtype('bits', len(dtype))
            self.value = dtype
            return
        elif isinstance(dtype, Dtype):
            self.dtype = dtype
            if value is not None:
                self._setvalue(value)
            return
        else:
            raise ValueError(f"Can't use '{dtype}' of type '{type(dtype)} to initialise Field.")

    def _getvalue(self) -> Any:
        return self._value

    def _setvalue(self, value: Any) -> None:
        if self.dtype is None:
            raise ValueError(f"Can't set a value for field without a Dtype.")
        b = Bits()
        try:
            self.dtype.set_fn(b, value)
            self._bits = b
        except ValueError:
            raise ValueError(f"Can't use the value '{value}' with the dtype {self.dtype}.")
        self._value = self.dtype.get_fn(self._bits)

    def _getbits(self) -> Bits | None:
        return self._bits

    value = property(_getvalue, _setvalue)
    bits = property(_getbits)


    def __str__(self) -> str:
        d = f"{colour.purple}{self.dtype}{colour.off}"
        n = '' if self.name is None else f" <{colour.green}{self.name}{colour.off}>"
        v = '' if self.value is None else f" = {self.value}"
        return f"'{d}{n}{v}'"

    def __repr__(self) -> str:
        return f"Field({self.__str__()})"

    def __eq__(self, other: Any) -> bool:
        if self.dtype != other.dtype:
            return False
        if self.name != other.name:
            return False
        if self.value != other.value:
            return False
        return True


class Format:

    def __init__(self, name: str | None = None,
                 fields: Sequence[Field | Format | str] | None = None) -> None:
        self.name = name
        if self.name == '':
            self.name = None
        if fields is None:
            fields = []
        self.empty_fields = 0

        self.fields = []
        for field in fields:
            if isinstance(field, Format):
                self.empty_fields += field.empty_fields
                self.fields.append(field)
                continue
            if isinstance(field, Field):
                pass
            elif isinstance(field, (str, Dtype, Bits)):
                field = Field(field)
            else:
                raise ValueError(f"Invalid Field of type {type(field)}.")
            if field.value is None:
                self.empty_fields += 1
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

    def __str__(self) -> str:
        return self._str()

    def __repr__(self) -> str:
        return self.__str__()

    def __iadd__(self, other: Format | Dtype | Bits | str | Field) -> Format:
        if isinstance(other, Format):
            self.fields.append(copy.deepcopy(other))
            self.empty_fields += other.empty_fields
            return self
        if isinstance(other, Field):
            self.fields.append(copy.deepcopy(other))
            if other.bits is None:
                self.empty_fields += 1
            return self
        if isinstance(other, str):
            field = Field(other)
        else:
            field = Field('', other)
        self.fields.append(field)
        if field.bits is None:
            self.empty_fields += 1
        return self

    def __add__(self, other: Format | Dtype | Bits | str | Field) -> Format:
        x = copy.deepcopy(self)
        x += other
        return x

    def __getitem__(self, key) -> Any:
        if self.fields is None:
            raise ValueError('Format is empty')
        for field in self.fields:
            if field.name == key:
                return field.value
        raise KeyError(key)

    def __setitem__(self, key, value) -> None:
        if self.fields is None:
            raise ValueError('Format is empty')
        for field in self.fields:
            if field.name == key:
                field.value = value
                return
        raise KeyError(key)

    def flatten(self):
        # Just return a flat list of fields (no Format objects, no name)
        pass

    def build(self, *values) -> Format:
        if len(values) != self.empty_fields:
            raise ValueError(f"Format needs {self.empty_fields} values, but {len(values)} were given.")
        value_iter = iter(values)
        out_fields = self._build(value_iter)
        f = object.__new__(Format)  # Avoiding expensive initialisation
        f.name = self.name
        f.fields = out_fields
        f.empty_fields = 0
        return f


    def _build(self, value_iter: Iterator[Field]) -> Sequence[Field | Format]:
        out_fields = []
        for field in self.fields:
            if isinstance(field, Format):
                format_fields = field._build(value_iter)
                f = object.__new__(Format)
                f.name = self.name
                f.fields = format_fields
                f.empty_fields = 0
                out_fields.append(f)
                continue
            if field.bits is None:
                field = Field(field.dtype, field.name, next(value_iter))
            out_fields.append(field)
        return out_fields


    def tobits(self) -> Bits:
        if self.fields is None:
            return Bits()
        out_bits = []
        for field in self.fields:
            if isinstance(field, Format):
                out_bits.append(field.tobits())
                continue
            if field.bits is None:
                raise ValueError(f"Field {field} needs a value specified")
            out_bits.append(field.bits)
        return Bits().join(out_bits)

    def tobytes(self) -> bytes:
        return self.tobits().tobytes()

    def parse(self, b: Bits) -> Format:
        out_format = copy.deepcopy(self)
        pos = 0
        for field in out_format.fields:
            if isinstance(field, Format):
                assert False  # TODO.
            if field.bits is not None:
                value = b[pos: pos + len(field.bits)]
                pos += len(field.bits)
                if value != field.bits:
                    raise ValueError(f"Field {field} at position {pos} does not match parsed bits {value}.")
            else:
                field.value = field.dtype.get_fn(b[pos: pos + field.dtype.bitlength])
                pos += field.dtype.bitlength
        return out_format
