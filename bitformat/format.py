from __future__ import annotations

from bitstring import Bits, Dtype
from typing import Sequence, Any, Iterable, Tuple, List, Dict
import copy

from .common import colour, indent_size
from .field import FieldType, Field


class FieldListType(FieldType):

    def __init__(self) -> None:
        self.fieldtypes = []

    def _build(self, values: List[Any], index: int, _vars={}) -> Tuple[Bits, int]:
        values_used = 0
        for fieldtype in self.fieldtypes:
            _, v = fieldtype._build(values, index + values_used, _vars)
            values_used += v
        return self.bits(), values_used

    def _parse(self, b: Bits, vars_: Dict[str, Any]) -> int:
        pos = 0
        for fieldtype in self.fieldtypes:
            pos += fieldtype._parse(b[pos:], vars_)
        return pos

    def clear(self) -> None:
        for fieldtype in self.fieldtypes:
            fieldtype.clear()

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
