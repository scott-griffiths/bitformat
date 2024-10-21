from __future__ import annotations

import re
from bitformat import Bits
from ._dtypes import Dtype, DtypeWithExpression
from ast import literal_eval
from ._common import colour, _indent, override
from typing import Any, Sequence, Iterable
from ._fieldtype import FieldType


__all__ = ['Field']


class Field(FieldType):

    def __new__(cls, s: str) -> Field:
        return cls.from_string(s)

    @classmethod
    def from_params(cls, dtype: Dtype | str, name: str = '', value: Any = None, const: bool = False, comment: str = '') -> Field:
        """
        Create a Field instance from parameters.

        :param dtype: The data type of the field.
        :type dtype: Dtype or str
        :param name: The name of the field, optional.
        :type name: str
        :param value: The value of the field, optional.
        :type value: Any
        :param const: Whether the field is constant, optional.
        :type const: bool
        :return: The Field instance.
        :param comment: An optional comment string
        :type comment: str

        :rtype: Field
        """
        x = super().__new__(cls)
        x._bits = None
        x.const = const
        x.comment = comment.strip()
        if isinstance(dtype, str):
            try:
                x._dtype_expression = DtypeWithExpression.from_string(dtype)
            except ValueError as e:
                raise ValueError(f"Can't convert the string '{dtype}' to a Dtype: {str(e)}")
        else:
            x._dtype_expression = DtypeWithExpression.from_string(str(dtype))  # HACK
        x.name = name
        if const is True and value is None:
            raise ValueError(f"Fields with no value cannot be set to be const.")
        if isinstance(value, str):
            # Special cases converting from strings to bytes and bools.
            value_str = value
            if x.dtype.return_type is bytes:
                try:
                    value = literal_eval(value)
                    if not isinstance(value, bytes):
                        raise ValueError()
                except ValueError:
                    raise ValueError(f"Can't initialise dtype '{dtype}' with the value string '{value_str}' "
                                     f"as it can't be converted to a bytes object.")
            if x.dtype.return_type is bool:
                try:
                    value = literal_eval(value)
                    if not isinstance(value, int) or value not in (0, 1):
                        raise ValueError()
                except ValueError:
                    raise ValueError(f"Can't initialise dtype '{dtype}' with the value string '{value_str}' "
                                     f"as it can't be converted to a bool.")
        if value is not None:
            x._setvalue_no_const_check(value)
        if x.dtype.size == 0:
            if x.dtype.name in ['bits', 'bytes'] and x.value is not None:
                x._dtype_expression = DtypeWithExpression(x.dtype.name, len(x.value), x.dtype.is_array, x.dtype.items, x.dtype.endianness)
        return x

    @override
    def _getbitlength(self) -> int:
        return self.dtype.bitlength

    bitlength = property(_getbitlength)

    @classmethod
    @override
    def from_string(cls, s: str, /) -> Field:
        s, comment = s.split('#', 1) if '#' in s else (s, '')
        comment = comment.strip()
        dtype_str, name, value, const = cls._parse_field_str(s)
        if ',' in dtype_str:
            raise ValueError(f"Field strings can only have one Dtype and should not contain commas. "
                             f"Perhaps you meant to use Format('({s})') instead?")
        return cls.from_params(dtype_str, name, value, const, comment)

    @classmethod
    def from_bits(cls, b: Bits | str | Iterable | bytearray | bytes | memoryview, /, name: str = '') -> Field:
        """
        Create a Field instance from bits.

        :param b: The bits to parse.
        :type b: Bits, str, Iterable, bytearray, bytes, or memoryview
        :param name: The name of the field, optional.
        :type name: str
        :return: The Field instance.
        :rtype: Field
        """
        b = Bits.from_auto(b)
        if len(b) == 0:
            raise ValueError(f"Can't create a Field from an empty Bits object.")
        return cls.from_params(Dtype.from_params('bits', len(b)), name, b, const=True)

    @classmethod
    def from_bytes(cls, b: bytes | bytearray, /, name: str = '', const: bool = False) -> Field:
        """
        Create a Field instance from bytes.

        :param b: The bytes to parse.
        :type b: bytes or bytearray
        :param name: The name of the field, optional.
        :type name: str
        :param const: Whether the field is constant, optional.
        :type const: bool
        :return: The Field instance.
        :rtype: Field
        """
        return cls.from_params(Dtype.from_params('bytes', len(b)), name, b, const)

    @override
    def to_bits(self) -> Bits:
        if self._bits is None:
            raise ValueError(f"Field '{self}' has no value, so can't be converted to bits.")
        return self._bits

    @override
    def clear(self) -> None:
        if not self.const:
            self._bits = None

    @override
    def flatten(self) -> list[FieldType]:
        return [self]

    def _copy(self) -> Field:
        x = self.__class__.from_params(self.dtype, self.name, self.value, self.const, self.comment)
        return x

    @staticmethod
    def _parse_field_str(field_str: str) -> tuple[str, str, str, bool | None]:
        if '\n' in field_str:
            raise ValueError(f"Field strings should not contain newline characters.")
        pattern = r"^(?:(?P<name>.*):)?\s*(?P<const>const\s)?(?P<dtype>[^=]+)\s*(?:=\s*(?P<value>.*))?$"
        compiled_pattern = re.compile(pattern, re.DOTALL)
        match = compiled_pattern.match(field_str)
        if match:
            name = match.group('name')
            const = match.group('const') is not None
            dtype_str = match.group('dtype').strip()
            value = match.group('value')
        else:
            raise ValueError(f"Invalid field string '{field_str}'.")
        name = '' if name is None else name.strip()
        return dtype_str, name, value, const

    @override
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
        if self.const:
            value = b[startbit:len(self._bits)]
            if value != self._bits:
                raise ValueError(f"Read value '{value}' when const value '{self._bits}' was expected.")
            return len(self._bits)
        if self._dtype_expression is not None:
            dtype = self._dtype_expression.evaluate(vars_)
        else:
            dtype = self._dtype_expression.base_dtype
        if len(b) - startbit < dtype.bitlength:
            raise ValueError(f"Field '{str(self)}' needs {dtype.bitlength} bits to parse, but {len(b) - startbit} were available.")
        # Deal with a stretchy dtype
        self._bits = b[startbit:startbit + dtype.bitlength] if dtype.bitlength != 0 else b[startbit:]
        if self.name != '':
            vars_[self.name] = self.value
        return len(self._bits)

    @override
    def _pack(self, values: Sequence[Any], index: int, vars_: dict[str, Any],
              kwargs: dict[str, Any]) -> tuple[Bits, int]:
        if self.const and self.value is not None:
            if self.name != '':
                vars_[self.name] = self.value
            return self._bits, 0
        if self.name in kwargs.keys():
            self._setvalue(kwargs[self.name])
            vars_[self.name] = self.value
            return self._bits, 0
        else:
            self._setvalue(values[index])
        if self.name != '':
            vars_[self.name] = self.value
        return self._bits, 1

    @override
    def _getvalue(self) -> Any:
        if self._bits is None:
            return None
        return self.dtype.unpack(self._bits)

    def _setvalue_no_const_check(self, value: Any) -> None:
        if value is None:
            raise ValueError("Cannot set the value of a Field to None. Perhaps you could use clear()?")
        try:
            self._bits = self.dtype.pack(value)
        except ValueError as e:
            raise ValueError(f"Can't use the value '{value}' with the field '{self}': {e}")

    @override
    def _setvalue(self, value: Any) -> None:
        if self.const:
            raise ValueError(f"Cannot set the value of a const Field '{self}'. "
                             f"To change the value, first set the const property of the Field to False.")
        self._setvalue_no_const_check(value)

    value = property(_getvalue, _setvalue)

    def _getdtype(self) -> Dtype:
        return self._dtype_expression.evaluate({})

    dtype = property(_getdtype)

    @override
    def _str(self, indent: int) -> str:
        const_str = 'const ' if self.const else ''
        dtype_str = str(self._dtype_expression)
        d = f"{colour.purple}{const_str}{dtype_str}{colour.off}"
        n = '' if self.name == '' else f"{colour.green}{self.name}{colour.off}: "
        v = '' if self.value is None else f" = {colour.cyan}{self.value}{colour.off}"
        comment = '' if self.comment == '' else f"  # {self.comment}"
        return f"{_indent(indent)}{n}{d}{v}{comment}"

    # This simple repr used when field is part of a larger object
    @override
    def _repr(self, indent: int) -> str:
        const_str = 'const ' if self.const else ''
        n = '' if self.name == '' else f"{self.name}: "
        dtype = f"{const_str}{self._dtype_expression}"
        v = '' if self.value is None else f" = {self.value}"
        return f"{_indent(indent)}'{n}{dtype}{v}'"

    # This repr is used when the field is the top level object
    def __repr__(self) -> str:
        if self.dtype.name == 'bytes':
            const_str = ', const=True' if self.const else ''
            return f"{self.__class__.__name__}.from_bytes({self.value}{const_str})"
        return f"{self.__class__.__name__}('{self.__str__()}')"

    def __eq__(self, other: Any) -> bool:
        """
         Check if two fields are equal.

         :param other: The other field to compare.
         :type other: Any
         :return: True if the fields are equal, False otherwise.
         :rtype: bool
         """
        if not isinstance(other, Field):
            return False
        if self.dtype != other.dtype:
            return False
        if self.dtype.name != 'pad' and self._bits != other._bits:
            return False
        if self.const != other.const:
            return False
        return True

#
# class Find(FieldType):
#
#     def __init__(self, bits: Bits | str, bytealigned: bool = True, name: str = '') -> None:
#         super().__init__()
#         self.bits_to_find = Bits.from_string(bits)
#         self.bytealigned = bytealigned
#         self.name = name
#         self._value = None
#
#     def _pack(self, values: Sequence[Any], index: int, _vars: dict[str, Any],
#               kwargs: dict[str, Any]) -> tuple[Bits, int]:
#         return Bits(), 0
#
#     def to_bits(self) -> Bits:
#         return Bits()
#
#     def clear(self) -> None:
#         self._value = None
#
#     def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
#         p = b.find(self.bits_to_find, bytealigned=self.bytealigned)
#         if p:
#             self._value = p[0]
#             return p[0]
#         self._value = None
#         return 0
#
#     def flatten(self) -> list[FieldType]:
#         # TODO
#         return []
#
#     def _str(self, indent: int) -> str:
#         name_str = '' if self.name == '' else f"'{colour.blue}{self.name}{colour.off}',"
#         find_str = f"'{colour.green}{str(self.bits_to_find)}{colour.off}'"
#         s = f"{_indent(indent)}{self.__class__.__name__}({name_str}{find_str})"
#         return s
#
#     def _repr(self, indent: int) -> str:
#         return self._str(indent)
#
#     def _getvalue(self) -> int | None:
#         return self._value
#
#     value = property(_getvalue, None)
