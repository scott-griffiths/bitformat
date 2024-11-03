from __future__ import annotations

from ._fieldtype import FieldType
from ._pass import Pass
from ._common import override, Expression, ExpressionError, Indenter
from typing import Sequence, Any
from ._bits import Bits
import re

__all__ = ['If']


class If(FieldType):

    condition: Expression
    condition_value: bool | None
    then_: FieldType
    else_: FieldType

    def __new__(cls, s: str) -> If:
        return cls.from_string(s)

    @classmethod
    def from_params(cls, condition: str | Expression, then_: FieldType | str, else_: FieldType | str | None = None, /) -> If:
        """
        The ``else_`` parameter is optional, and defaults to a :class:`Pass` field if not provided.

        Note that only a single :class:`FieldType` can be provided for each of the ``then_`` and ``else_`` clauses.
        If you need to provide multiple fields, use a :class:`Format`.

        """
        x = super().__new__(cls)
        x.condition = Expression(condition) if isinstance(condition, str) else condition
        x.condition_value = None
        x.then_ = then_ if isinstance(then_, FieldType) else FieldType.from_string(then_)
        if else_ is not None:
            x.else_ = else_ if isinstance(else_, FieldType) else FieldType.from_string(else_)
        else:
            x.else_ = Pass()
        return x

    @classmethod
    @override
    def from_string(cls, s: str, /) -> If:
        """
        Create an If field from a string.

        The string should be in the format:

        if {expression}:
            then_field
        else:
            else_field

        """
        # This compiled re pattern expects
        # if {expression}: then_ \n else: else_
        pattern = re.compile(
            r'\s*if\s*\{\s*(?P<expression>[^}]+)\s*\}\s*:\s*(?P<then>.*?)(?:\s*else\s*:\s*(?P<else>.*))?\s*$'
        )
        if not (match := pattern.match(s)):
            raise ValueError(f"Can't parse If field from '{s}'")
        groups = match.groupdict()
        return cls.from_params('{' + groups['expression'] + '}', groups['then'], groups['else'])

    @override
    def _getbitlength(self) -> int:
        if self.condition_value in [None, True]:
            try:
                then_len = self.then_.bitlength
            except ValueError as e:
                raise ValueError(f"Cannot calculate length of the If field as 'then' field has no length: {e}")
        if self.condition_value is not True:
            try:
                else_len = self.else_.bitlength
            except ValueError as e:
                raise ValueError(f"Cannot calculate length of the If field as 'else' field has no length: {e}")

        if self.condition_value is True:
            return then_len
        if self.condition_value is False:
            return else_len
        if then_len != else_len:
            try:
                cond = self.condition.evaluate()
            except ExpressionError:
                raise ValueError(f"Cannot calculate length of the If field as it depends on the result of {self.condition}.\n"
                                 f"If True the length would be {then_len}, if False the length would be {else_len}.")
            return then_len if cond else else_len
        else:
            return then_len

    @override
    def _pack(self, values: Sequence[Any], index: int, vars_: dict[str, Any],
              kwargs: dict[str, Any]) -> tuple[Bits, int]:
        self.condition_value = self.condition.evaluate(vars_ | kwargs)
        if self.condition_value:
            _, v = self.then_._pack(values, index, vars_, kwargs)
        else:
            _, v = self.else_._pack(values, index, vars_, kwargs)
        return self.to_bits(), v

    @override
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
        self.condition_value = self.condition.evaluate(vars_)
        if self.condition_value:
            return self.then_._parse(b, startbit, vars_)
        return self.else_._parse(b, startbit, vars_)

    @override
    def _copy(self) -> If:
        return If.from_params(self.condition, self.then_._copy(), self.else_._copy())

    @override
    def clear(self) -> None:
        self.then_.clear()
        self.else_.clear()
        self.condition_value = None

    @override
    def _getvalue(self) -> Any:
        if self.condition_value is None:
            raise ValueError("Cannot get value of If field before parsing or unpacking it.")
        if self.condition_value:
            return self.then_._getvalue()
        else:
            return self.else_._getvalue()

    @override
    def _setvalue(self, val: Any) -> None:
        raise NotImplementedError

    @override
    def _str(self, indent: Indenter) -> str:
        s = indent(f"if {self.condition}:\n")
        with indent:
            s += self.then_._str(indent)
        if self.else_.bitlength != 0:
            s += indent('else:\n')
            with indent:
                s += self.else_._str(indent)
        return s

    @override
    def _repr(self) -> str:
        return self._str(Indenter())

    @override
    def to_bits(self) -> Bits:
        if self.condition_value is None:
            raise ValueError("Cannot get value of If field before parsing.")
        if self.condition_value:
            return self.then_.to_bits()
        else:
            return self.else_.to_bits()

    value = property(_getvalue, _setvalue)

    @override
    def __eq__(self, other) -> bool:
        if not isinstance(other, If):
            return False
        if self.condition != other.condition:
            return False
        if self.then_ != other.then_:
            return False
        if self.else_ != other.else_:
            return False
        return True

