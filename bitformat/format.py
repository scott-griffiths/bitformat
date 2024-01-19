from __future__ import annotations

from bitstring import Bits, Dtype
from typing import Sequence, Any, Iterator
import copy

class Field:
    def __init__(self, name: str | None, dtype_or_bits: Dtype | Bits | str, value: Any = None):
        if name == '':
            name = None
        self.name = name
        self.bits = None
        self.dtype = None
        if isinstance(dtype_or_bits, str):
            # Try to convert to Bits first
            try:
                self.bits = Bits(dtype_or_bits)
            except ValueError:
                try:
                    self.dtype = Dtype(dtype_or_bits)
                except ValueError:
                    raise ValueError(f"Can't convert '{dtype_or_bits}' to either a Bits or a Dtype.")
        elif isinstance(dtype_or_bits, Bits):
            self.bits = dtype_or_bits
        elif isinstance(dtype_or_bits, Dtype):
            self.dtype = dtype_or_bits
        else:
            raise ValueError(f"Can't use '{dtype_or_bits}' of type '{type(dtype_or_bits)} to initialise Field.")
        if self.bits is not None and value is not None:
            raise ValueError(f"value supplied for a field that is a bit literal")

        if self.dtype is not None and value is not None:
            self._setvalue(value)
        else:
            self._value = value

    def _getvalue(self) -> Any:
        return self._value

    def _setvalue(self, value: Any) -> None:
        if self.dtype is None:
            raise ValueError(f"Can't set a value for field without a Dtype.")
        self._value = value
        b = Bits()
        try:
            self.dtype.set_fn(b, value)
        except ValueError:
            raise ValueError(f"Can't use the value {value} with the dtype {self.dtype}.")
        self.bits = b

    value = property(_getvalue, _setvalue)

    def __str__(self) -> str:
        n = "'" if self.name is None else f"'<{self.name}> "
        x = self.dtype if self.dtype is not None else self.bits
        v = f" = {self.value}'" if self.value is not None else "'"
        return f"{n}{x}{v}"

    def __repr__(self) -> str:
        return f"Field({self.__str__()})"

    def __eq__(self, other: Any) -> bool:
        if self.name != other.name:
            return False
        if self.dtype != other.dtype:
            return False
        if self.bits != other.bits:
            return False
        if self.value != other.value:
            return False
        return True


class Format:

    def __init__(self, name: str | None = None,
                 fields: Sequence[Field | Format | Sequence] | None = None) -> None:
        self.name = name
        if self.name == '':
            self.name = None
        if fields is None:
            fields = []
        self.empty_fields = 0

        if isinstance(fields, Bits):
            fields = [fields]
        else:
            if fields is not None and not isinstance(fields, Sequence):
                fields = [fields]
            fields = fields
        self.fields = []
        for field in fields:
            if isinstance(field, Format):
                self.empty_fields += field.empty_fields
                self.fields.append(field)
                continue
            if isinstance(field, Field):
                pass
            elif isinstance(field, str):
                field = Field(None, field)
            else:
                field = Field(*field)
            if field.bits is None:
                self.empty_fields += 1
            self.fields.append(field)


    def _str(self, indent: int=0) -> str:
        indent_str = '    ' * indent
        s = f"{indent_str}Format('{self.name}',\n"
        for field in self.fields:
            if isinstance(field, Format):
                s += field._str(indent + 1)
            else:
                s += f"    {indent_str}{field},\n"
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
        field = Field('', other)
        self.fields.append(field)
        if field.bits is None:
            self.empty_fields += 1
        return self

    def __add__(self, other: Format | Dtype | Bits | str | Field) -> Format:
        x = copy.deepcopy(self)
        x += other
        return x

    # def __get__(self, key):

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
                field = Field(field.name, field.dtype, next(value_iter))
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
        out_fields = []
        pos = 0
        for field in self.fields:
            if isinstance(field, Format):
                assert False  # TODO.
            if field.bits is not None:
                value = b[pos: pos + len(field.bits)]
                pos += len(field.bits)
                if value != field.bits:
                    raise ValueError(f"Field {field} at position {pos} does not match parsed bits {value}.")
                out_fields.append(field)
            else:
                assert field.dtype is not None
                value = field.dtype.get_fn(b[pos: pos + field.dtype.bitlength])
                pos += field.dtype.bitlength
                out_fields.append(value)
        return Format(self.name, out_fields)
