from __future__ import annotations

from .bits import Bits
from .dtypes import Dtype
from typing import Sequence, Any, Iterable
import copy

from .common import colour, _indent
from .field import FieldType, Field, FieldArray, _perhaps_convert_to_expression


class Format(FieldType):

    def __init__(self, fieldtypes: Sequence[FieldType | str] | None = None, name: str = '') -> None:
        self.fieldtypes = []
        if fieldtypes is None:
            fieldtypes = []
        self.name = name
        self.vars = {}
        for fieldtype in fieldtypes:
            if isinstance(fieldtype, str):
                # TODO: This is inefficient, parsing the string twice.
                try:
                    fieldtype = FieldArray.from_string(fieldtype)
                except ValueError:
                    fieldtype = Field.from_string(fieldtype)
            if not isinstance(fieldtype, FieldType):
                raise ValueError(f"Invalid Field of type {type(fieldtype)}.")
            self.fieldtypes.append(fieldtype)

    def _build(self, values: Sequence[Any], index: int, _vars: dict[str, Any] | None = None, kwargs: dict[str, Any] | None = None) -> tuple[Bits, int]:
        values_used = 0
        for fieldtype in self.fieldtypes:
            _, v = fieldtype._build(values, index + values_used, _vars, kwargs)
            values_used += v
        return self.tobits(), values_used

    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        pos = 0
        for fieldtype in self.fieldtypes:
            pos += fieldtype._parse(b[pos:], vars_)
        return pos

    def clear(self) -> None:
        for fieldtype in self.fieldtypes:
            fieldtype.clear()

    def _getvalue(self) -> list[Any]:
        return [f.value for f in self.fieldtypes]

    def _setvalue(self, val: Sequence[Any]) -> None:
        if len(val) != len(self.fieldtypes):
            raise ValueError(f"Can't set {len(self.fieldtypes)} fields from {len(val)} values.")
        for fieldtype, v in zip(self.fieldtypes, val):
            fieldtype._setvalue(v)

    def tobits(self) -> Bits:
        return Bits().join(fieldtype.tobits() for fieldtype in self.fieldtypes)

    def flatten(self) -> list[FieldType]:
        # Just return a flat list of fields
        flattened_fields = []
        for fieldtype in self.fieldtypes:
            flattened_fields.extend(fieldtype.flatten())
        return flattened_fields

    def __getitem__(self, key) -> Any:
        if isinstance(key, int):
            fieldtype = self.fieldtypes[key]
            return fieldtype
        elif isinstance(key, slice):
            a = self.__class__()
            a.extend(self.fieldtypes[key])
            return a
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

    def _str(self, indent: int) -> str:
        name_str = '' if self.name == '' else f", {colour.green}{self.name!r}{colour.off}"
        s = f"{_indent(indent)}{self.__class__.__name__}([\n"
        for i, fieldtype in enumerate(self.fieldtypes):
            s += fieldtype._str(indent + 1)
            if i != len(self.fieldtypes) - 1:
                s += ','
            s += '\n'
        s += f"{_indent(indent)}]{name_str})"
        return s

    def _repr(self, indent: int) -> str:
        name_str = '' if self.name == '' else f", {self.name!r}"
        s = f"{_indent(indent)}{self.__class__.__name__}([\n"
        for i, fieldtype in enumerate(self.fieldtypes):
            s += fieldtype._repr(indent + 1)
            if i != len(self.fieldtypes) - 1:
                s += ','
            s += '\n'
        s += f"{_indent(indent)}]{name_str})"
        return s

    def __iadd__(self, other: Format | Dtype | Bits | str | Field) -> Format:
        if isinstance(other, FieldType):
            self.fieldtypes.append(copy.copy(other))
            return self
        field = Field(other)
        self.fieldtypes.append(field)
        return self

    def __copy__(self) -> Format:
        x = Format()
        x.name = self.name
        x.vars = self.vars
        x.fieldtypes = [copy.copy(f) for f in self.fieldtypes]
        return x

    def __add__(self, other: Format | Dtype | Bits | str | Field) -> Format:
        x = copy.deepcopy(self)
        x += other
        return x

    def append(self, value: Any) -> None:
        self.__iadd__(value)

    def extend(self, values: Iterable) -> None:
        for value in values:
            self.__iadd__(value)


class Repeat(FieldType):

    def __init__(self, count: int | str | Iterable, fieldtype: FieldType | str | Dtype | Bits | Sequence[FieldType | str]):
        super().__init__()
        self._bits = None
        self.count, self.count_expression = _perhaps_convert_to_expression(count)
        if isinstance(fieldtype, str):
            self.fieldtype = Field.from_string(fieldtype)
        elif isinstance(fieldtype, Bits):
            self.fieldtype = Field.from_bits(fieldtype)
        elif isinstance(fieldtype, Dtype):
            self.fieldtype = Field(fieldtype)
        elif isinstance(fieldtype, Sequence):
            self.fieldtype = Format(fieldtype)
        else:
            self.fieldtype = fieldtype
        if not isinstance(self.fieldtype, FieldType):
            raise ValueError(f"Invalid Field of type {type(fieldtype)}.")
        self._values = []

    def _str(self, indent: int) -> str:
        if self.count_expression is not None:
            count_str = self.count_expression
        else:
            count_str = str(self.count)
        count_str = f'({count_str})'

        s = f"{_indent(indent)}{self.__class__.__name__}{count_str}\n"
        s += self.fieldtype._str(indent + 1)
        return s

    def _repr(self, indent: int) -> str:
        count = self.count if self.count is not None else self.count_expression
        s = f"{_indent(indent)}{self.__class__.__name__}({count!r},\n"
        s += self.fieldtype._repr(indent + 1)
        s += f"\n{_indent(indent)})"
        return s

    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        index = 0
        if self.count_expression is not None:
            self.count = self.count_expression.safe_eval(vars_)
        if isinstance(self.count, int):
            self.count = range(self.count)
        for _ in self.count:
            index += self.fieldtype.parse(b[index:])
            self._values.append(self.fieldtype.value)
        return index

    def _build(self, values: Sequence[Any], index: int, vars_: dict[str, Any], kwargs: dict[str, Any]) -> tuple[Bits, int]:
        self._bits = Bits()
        if self.count_expression is not None:
            self.count = self.count_expression.safe_eval(vars_)
        if isinstance(self.count, int):
            self.count = range(self.count)
        values_used = 0
        for _ in self.count:
            bits, v = self.fieldtype._build(values, index + values_used, vars_, kwargs)
            self._bits += bits
            values_used += v
        return self._bits, values_used

    def flatten(self) -> list[FieldType]:
        # TODO: This needs values in it. This won't work.
        flattened_fields = []
        for _ in self.count:
            flattened_fields.extend(self.fieldtype.flatten())
        return flattened_fields

    def tobits(self) -> Bits:
        return self._bits if self._bits is not None else Bits()

    def clear(self) -> None:
        self._bits = None

    def _getvalue(self) -> list[Any]:
        return self._values

    value = property(_getvalue, None)
