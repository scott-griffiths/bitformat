from __future__ import annotations

from bitstring import Bits, Dtype
from typing import Sequence, Any, Iterable
import copy

from .common import colour, _indent
from .field import FieldType, Field, FieldArray


class FieldListType(FieldType):

    def __init__(self) -> None:
        self.fieldtypes = []

    def _build(self, values: list[Any], index: int, _vars: dict[str, Any] | None = None, kwargs: dict[str, Any] | None = None) -> tuple[Bits, int]:
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

    def _setvalue(self, val: list[Any]) -> None:
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

    def __init__(self, fieldtypes: Sequence[FieldType | str] | None = None, name: str = '') -> None:
        super().__init__()
        if fieldtypes is None:
            fieldtypes = []
        self.name = name
        self.vars = {}
        for fieldtype in fieldtypes:
            if isinstance(fieldtype, str):
                try:
                    fieldtype = Field.fromstring(fieldtype)
                except ValueError:
                    fieldtype = FieldArray.fromstring(fieldtype)
            if not isinstance(fieldtype, FieldType):
                raise ValueError(f"Invalid Field of type {type(fieldtype)}.")
            self.fieldtypes.append(fieldtype)

    def _str(self, indent: int) -> str:
        name_str = '' if self.name == '' else f" <{colour.green}{self.name}{colour.off}>"
        s = f"{_indent(indent)}{self.__class__.__name__}{name_str}\n"
        for fieldtype in self.fieldtypes:
            s += fieldtype._str(indent + 1) + '\n'
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

