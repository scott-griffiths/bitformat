from __future__ import annotations
import abc
import re
from bitformat import Bits
from ._dtypes import Dtype, DtypeWithExpression
from ast import literal_eval
from ._common import colour, Expression, ExpressionError, _indent, override, final
from typing import Any, Sequence, Iterable

__all__ = ['Field', 'FieldType']


def _perhaps_convert_to_expression(s: Any) -> tuple[Any | None, None | Expression]:
    if not isinstance(s, str):
        return s, None
    try:
        e = Expression(s)
    except ValueError:
        return s, None
    return None, e


class FieldType(abc.ABC):

    fieldtype_classes = []
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.fieldtype_classes.append(cls)

    @final
    def parse(self, b: BitsType) -> int:
        """
        Parse the field type from the supplied bits.

        The parsing is done lazily, so any values might not be calculated at this point, instead waiting until
        they are explicitly asked for.

        :param b: The bits to parse.
        :type b: BitsType
        :return: The number of bits used.
        :rtype: int
        """
        b = Bits.from_auto(b)
        try:
            return self._parse(b, {})
        except ValueError as e:
            raise ValueError(f"Error parsing field {self}: {str(e)}")

    @final
    def pack(self, values: Any | None = None, /, **kwargs) -> Bits:
        """
        Pack the field type into bits.

        :param values: The values to pack.
        :type values: Any, optional
        :param kwargs: Additional keyword arguments.
        :return: The packed bits.
        :rtype: Bits
        """
        if kwargs is None:
            kwargs = {}
        if values is None:
            return self._pack([], 0, {}, kwargs)[0]
        try:
            bits, values_used = self._pack([values], 0, {}, kwargs)
        except TypeError as e:
            if not isinstance(values, Sequence):
                raise TypeError(f"The values parameter must be a sequence (e.g. a list or tuple), not a {type(values)}.")
            raise e
        return bits

    @final
    def unpack(self, b: Bits | bytes | bytearray | None = None) -> Any | list[Any]:
        """
        Unpack the field type from bits.

        :param b: The bits to unpack.
        :type b: Bits, bytes, bytearray, optional
        :return: The unpacked value.
        :rtype: Any or list[Any]
        """
        if b is not None:
            self.parse(b)
        try:  # TODO: This is hacky. Why is bits needed here?
            bits = self.to_bits()
        except ValueError as e:
            raise ValueError(f"Cannot unpack '{self!r}' as not all fields have binary data to unpack: {e}") from None
        else:
            return self.value

    @final
    def __str__(self) -> str:
        """
        Return a string representation of the field type.

        :return: The string representation.
        :rtype: str
        """
        return self._str(0)

    def __repr__(self) -> str:
        """
        Return a detailed string representation of the field type.

        :return: The detailed string representation.
        :rtype: str
        """
        return self._repr(0)

    @classmethod
    def from_string(cls, s: str) -> FieldType:
        """
        Create a FieldType instance from a string.

        :param s: The string to parse.
        :type s: str
        :return: The FieldType instance.
        :rtype: FieldType
        """
        s = s.strip()
        if s == '':
            raise ValueError(f"Can't create a FieldType from an empty string.")
        errors = []
        try:  # A stupid way to get it to compile without a circular dependency.
            1 / 0
        except ZeroDivisionError:
            from ._format import Format
            # Try Field first as it's the simplest and common
            try:
                return Field.from_string(s)
            except ValueError as e:
                errors.append((Field, e))
            # Then try Format
            name, field_strs, err_msg = Format._parse_format_str(s)
            if err_msg:
                errors.append((Format, err_msg))
            else:
                errors.pop()  # Remove error about not converting to Field
                try:
                    return Format._from_field_strs(name, field_strs)
                except ValueError as e:
                    errors.append((Format, e))

            # for fieldtype in [f for f in cls.fieldtype_classes if f is not in (Format, Field)]:
            #     try:
            #         return fieldtype.from_string(s)
            #     except ExpressionError as e:
            #         errors.append((fieldtype, e))
            #         # If we got as far as evaluating an Expression then we probably(?) have the correct
            #         # FieldType, so just return the error so it doesn't get hidden by later ones.
            #         break
            #     except ValueError as e:
            #         errors.append((fieldtype, e))
        if errors:
            err_str = '\n'.join([f"When attempting conversion to {ft.__name__}:\n    {e.__class__.__name__}: {str(e)}" for ft, e in errors])
            # Use the error type of the final error instead of always using ValueError, with the same
            raise ValueError(f"Can't convert the string '{s}' to a FieldType.\n{err_str}")

    @abc.abstractmethod
    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        """
        Parse the field from the bits, using the vars_ dictionary to resolve any expressions.

        Return the number of bits used.

        """
        ...

    @abc.abstractmethod
    def _pack(self, values: Sequence[Any], index: int, vars_: dict[str, Any],
              kwargs: dict[str, Any]) -> tuple[Bits, int]:
        """
        Build the field from the values list, starting at index.

        Return the bits and the number of values used.

        """
        ...

    @abc.abstractmethod
    def to_bits(self) -> Bits:
        """
        Return the bits that represent the field.

        :return: The bits that represent the field.
        :rtype: Bits
        """
        ...

    @final
    def to_bytes(self) -> bytes:
        """
        Return the bytes that represent the field. Pads with up to 7 zero bits if necessary.

        :return: The bytes that represent the field.
        :rtype: bytes
        """
        b = self.to_bits()
        return b.to_bytes()

    @abc.abstractmethod
    def clear(self) -> None:
        """
        Clear the value of the field, unless it is a constant.
        """
        ...

    @abc.abstractmethod
    def _str(self, indent: int) -> str:
        ...

    @abc.abstractmethod
    def _repr(self, indent: int) -> str:
        ...

    @abc.abstractmethod
    def flatten(self) -> list[FieldType]:
        """
        Return a flat list of all the fields in the object.

        :return: A flat list of all the fields.
        :rtype: list[FieldType]
        """
        ...

    @abc.abstractmethod
    def _getvalue(self) -> Any:
        ...

    @abc.abstractmethod
    def _setvalue(self, value: Any) -> None:
        ...

    @abc.abstractmethod
    def __len__(self) -> int:
        """
        Return the length of the FieldType in bits.

        :return: The length in bits.
        :rtype: int
        """
        ...

    def __eq__(self, other) -> bool:
        return self.flatten() == other.flatten()

    def _get_name(self) -> str:
        return self._name

    def _set_name(self, val: str) -> None:
        if val != '':
            if not val.isidentifier():
                raise ValueError(f"The FieldType name '{val}' is not a valid Python identifier.")
            if '__' in val:
                raise ValueError(f"The FieldType name '{val}' contains a double underscore which is not permitted.")
        self._name = val

    name = property(_get_name, _set_name)
    value = property(_getvalue, _setvalue)

    def _get_comment(self) -> str:
        return self._comment

    def _set_comment(self, comment: str) -> None:
        self._comment = comment.strip()

    comment = property(_get_comment, _set_comment)


class Field(FieldType):

    def __new__(cls, token: str | None = None) -> Field:
        if token is None:
            x = super().__new__(cls)
            x.const = False
            return x
        return cls.from_string(token)

    @classmethod
    def from_parameters(cls, dtype: Dtype | str, name: str = '', value: Any = None, const: bool = False, comment: str = '') -> Field:
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
        x._setvalue_no_const_check(value)
        if x.dtype.size == 0:
            if x.dtype.name in ['bits', 'bytes'] and x.value is not None:
                x._dtype_expression = DtypeWithExpression(x.dtype.name, len(x.value), x.dtype.is_array, x.dtype.items, x.dtype.endianness)
        return x

    @override
    def __len__(self) -> int:
        return self.dtype.bitlength

    @classmethod
    @override
    def from_string(cls, s: str, /) -> Field:
        s, comment = s.split('#', 1) if '#' in s else (s, '')
        comment = comment.strip()
        dtype_str, name, value, const = cls._parse_field_str(s)
        return cls.from_parameters(dtype_str, name, value, const, comment)

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
        return cls.from_parameters(Dtype.from_parameters('bits', len(b)), name, b, const=True)

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
        return cls.from_parameters(Dtype.from_parameters('bytes', len(b)), name, b, const)

    @override
    def to_bits(self) -> Bits:
        if self._bits is None:
            raise ValueError(f"Field '{self}' has no value, so can't be converted to bits.")
        return self._bits

    @override
    def clear(self) -> None:
        if not self.const:
            self._setvalue(None)

    @override
    def flatten(self) -> list[FieldType]:
        return [self]

    @staticmethod
    def _parse_field_str(field_str: str) -> tuple[str, str, str, bool | None]:
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
    def _parse(self, b: Bits, vars_: dict[str, Any]) -> int:
        if self.const:
            value = b[:len(self._bits)]
            if value != self._bits:
                raise ValueError(f"Read value '{value}' when const value '{self._bits}' was expected.")
            return len(self._bits)
        if self._dtype_expression is not None:
            dtype = self._dtype_expression.evaluate(vars_)
        else:
            dtype = self._dtype_expression.base_dtype
        if len(b) < dtype.bitlength:
            raise ValueError(f"Field '{str(self)}' needs {dtype.bitlength} bits to parse, but only {len(b)} were available.")
        self._bits = b[:dtype.bitlength]
        if self.name != '':
            vars_[self.name] = self.value
        return dtype.bitlength

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
        return self.dtype.unpack(self._bits) if self._bits is not None else None

    def _setvalue_no_const_check(self, value: Any) -> None:
        if value is None:
            self._bits = None
            return
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
