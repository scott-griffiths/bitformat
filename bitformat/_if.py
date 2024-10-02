from __future__ import annotations

from ._field import FieldType, Field
from ._common import _indent, override, Expression, ExpressionError
from typing import Sequence, Any
from ._bits import Bits
import re


class If(FieldType):

    def __new__(cls, s: str) -> If:
        return cls.from_string(s)

    @classmethod
    def from_parameters(cls, condition: str | Expression, then_: FieldType | str, else_: FieldType | str | None = None) -> If:
        x = super().__new__(cls)
        x.condition = Expression(condition) if isinstance(condition, str) else condition
        x.then_ = then_ if isinstance(then_, FieldType) else Field.from_string(then_)
        if else_ is not None:
            x.else_ = else_ if isinstance(else_, FieldType) else Field.from_string(else_)
        else:
            x.else_ = Field('pad0')
        return x

    @classmethod
    @override
    def from_string(cls, s: str, /) -> If:
        # This compiled re pattern expects
        # if {expression}: then_ \n else: else_
        pattern = re.compile(
            r'\s*if\s*\{\s*(?P<expression>[^}]+)\s*\}\s*:\s*(?P<then>.*?)(?:\s*else\s*:\s*(?P<else>.*))?\s*$'
        )
        if not (match := pattern.match(s)):
            raise ValueError(f"Can't parse If field from '{s}'")
        groups = match.groupdict()
        return cls.from_parameters('{' + groups['expression'] + '}', groups['then'], groups['else'])

    @override
    def __len__(self):
        try:
            len1 = len(self.then_)
        except ValueError as e:
            raise ValueError(f"Cannot calculate length of the If field as 'then' field has no length: {e}")
        try:
            len2 = len(self.else_)
        except ValueError as e:
            raise ValueError(f"Cannot calculate length of the If field as 'else' field has no length: {e}")
        if len(self.then_) != len(self.else_):
            try:
                cond = self.condition.evaluate()
            except ExpressionError:
                raise ValueError(f"Cannot calculate length of the If field as it depends on the result of {self.condition}.\n"
                                 f"If True the length would be {len1}, if False the length would be {len2}.")
            return len1 if cond else len2
        return len(self.then_)

    @override
    def _pack(self, values: Sequence[Any], index: int, _vars: dict[str, Any] | None = None,
              kwargs: dict[str, Any] | None = None) -> tuple[Bits, int]:
        if self.condition.evaluate(_vars, kwargs):
            _, v = self.then_._pack(values[index], index, _vars, kwargs)
        else:
            _, v = self.else_._pack(values[index], index, _vars, kwargs)
        return self.to_bits(), v

    @override
    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        if self.condition.evaluate(**vars_):
            return self.then_._parse(b, vars_)
        return self.else_._parse(b, vars_)

    @override
    def _copy(self) -> If:
        return If.from_parameters(self.condition, self.then_._copy(), self.else_._copy())

    @override
    def clear(self) -> None:
        self.then_.clear()
        self.else_.clear()

    @override
    def _getvalue(self) -> Any:
        if self.condition.evaluate():
            return self.then_._getvalue()
        else:
            return self.else_._getvalue()

    @override
    def _setvalue(self, val: Any) -> None:
        raise NotImplementedError

    @override
    def flatten(self) -> list[FieldType]:
        raise NotImplementedError

    @override
    def _str(self, indent: int) -> str:
        s = f"{_indent(indent)}if {self.condition}:\n{self.then_._str(indent + 1)}\n"
        if len(self.else_) != 0:
            s += f"{_indent(indent)}else:\n{self.else_._str(indent + 1)}"
        return s

    @override
    def _repr(self, indent: int) -> str:
        return self._str(indent)

    @override
    def to_bits(self) -> Bits:
        if self.condition.evaluate():
            return self.then_.to_bits()
        else:
            return self.else_.to_bits()

    value = property(_getvalue, _setvalue)

