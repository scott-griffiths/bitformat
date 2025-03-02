from __future__ import annotations
import abc
import sys

from bitformat import Bits
from ._dtypes import DtypeTransformer
from ._bits import BitsType
from ._common import final, Indenter, field_parser
from typing import Any, Sequence, TextIO
import keyword
from ._options import Options
from lark import UnexpectedInput
import lark

__all__ = ["FieldType"]

fieldtype_classes: dict[str, FieldType] = {}


class FieldTypeTransformer(DtypeTransformer):

    def field_name(self, items) -> str:
        return items[0]

    def const_field(self, items) -> Field:
        assert len(items) == 3
        name = items[0] if items[0] is not None else ''
        dtype = items[1]
        value = items[2]
        return fieldtype_classes['Field'].from_params(dtype, name, value, const=True)

    def mutable_field(self, items) -> Field:
        assert len(items) == 3
        name = items[0] if items[0] is not None else ''
        dtype = items[1]
        value = items[2]
        return fieldtype_classes['Field'].from_params(dtype, name, value)

    def repeat(self, items) -> Repeat:
        expr = items[0]
        count = expr.evaluate()
        return fieldtype_classes['Repeat'].from_params(count, items[1])

    def pass_(self, items) -> Pass:
        assert len(items) == 0
        return fieldtype_classes['Pass'].from_params()

    def if_(self, items) -> If:
        assert len(items) == 3
        expr = items[0]
        then_ = items[1]
        else_ = items[2]
        return fieldtype_classes['If'].from_params(expr, then_, else_)

    def format(self, items) -> Format:
        assert len(items) >= 1
        name = items[0] if items[0] is not None else ''
        fields = items[1:]
        return fieldtype_classes['Format'].from_params(fields, name)

field_type_transformer = FieldTypeTransformer()


class FieldType(abc.ABC):
    def __new__(cls, *args, **kwargs) -> FieldType:
        x = super().__new__(cls)
        x._name = ""
        return x

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        fieldtype_classes[cls.__name__] = cls

    @final
    def parse(self, b: BitsType | None = None, /, **kwargs) -> int:
        """
        Parse the field type from the supplied bits.

        The parsing is done lazily, so any values might not be calculated at this point, instead waiting until
        they are explicitly asked for.

        :param b: The bits to parse.
        :type b: BitsType
        :return: The number of bits used.
        :rtype: int
        """
        b = Bits() if b is None else Bits._from_any(b)
        self.clear()
        try:
            return self._parse(b, 0, kwargs)
        except ValueError as e:
            raise ValueError(f"Error parsing field {self}: {str(e)}")

    @final
    def pack(self, values: Sequence[Any] | Any, /, **kwargs) -> None:
        """
        Pack with values for each non-const field.

        :param values: The values to pack.
        :type values: Any, optional
        :param kwargs: Additional keyword arguments.
        :rtype: None
        """
        if kwargs is None:
            kwargs = {}
        self._pack(values, {}, kwargs)

    @final
    def unpack(self, b: BitsType | None = None) -> Any | list[Any]:
        """
        Unpack the field type from bits.

        :param b: The bits to unpack.
        :type b: Bits, bytes, bytearray, optional
        :return: The unpacked value.
        :rtype: Any or list[Any]
        """
        if b is not None:
            self.parse(b)
        v = self.value
        if v is None:
            raise ValueError("Cannot unpack field as it has no value.")
        return v

    @final
    def __str__(self) -> str:
        """
        Return a string representation of the field type.

        :return: The string representation.
        :rtype: str
        """
        return self._str(Indenter(Options().indent_size), not Options().no_color)

    def __repr__(self) -> str:
        """
        Return a detailed string representation of the field type.

        :return: The detailed string representation.
        :rtype: str
        """
        return self._repr()

    def is_stretchy(self) -> bool:
        """
        Return True if the field is stretchy, False otherwise.

        :return: True if stretchy, False otherwise.
        :rtype: bool
        """
        try:
            return self.bit_length is None
        # TODO: This logic doesn't work any more?!
        except ValueError:  # It might be an Expression, and Expressions can't be stretchy.
            return False

    def pp(self, stream: TextIO = sys.stdout,indent: int | None = None, depth: int | None = None) -> None:
        """
        Pretty-print the fieldtype to a stream (or stdout by default).

        :param stream: The stream to write to.
        :type stream: TextIO
        :param indent: The number of spaces for each level of indentation. Defaults to Options().indent_size which defaults to 4.
        :type indent: int
        :param depth: The maximum depth to print, or None for no limit.
        :type depth: int or None
        """
        stream.write(self._str(Indenter(indent_size=indent, max_depth=depth)))
        stream.write("\n")

    @classmethod
    @final
    def from_string(cls, s: str) -> FieldType:
        """
        Create a FieldType instance from a string.

        The type is inferred from the string, so it can be a Field, Format, or other FieldType.

        :param s: The string to parse.
        :type s: str
        :return: The FieldType instance.
        :rtype: FieldType
        """
        try:
            tree = field_parser.parse(s)
        except UnexpectedInput:
            raise ValueError
        try:
            return field_type_transformer.transform(tree)
        except lark.exceptions.VisitError as e:
            raise ValueError(f"Error parsing FieldType: {e}")

    @abc.abstractmethod
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
        """
        Parse the field from the bits, using the vars_ dictionary to resolve any expressions.

        Return the number of bits used.

        """
        ...

    @abc.abstractmethod
    def _pack(self, value: Any | Sequence[Any], vars_: dict[str, Any], kwargs: dict[str, Any]) -> None:
        """
        Build the field from the values list, starting at index.

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

    @classmethod
    @abc.abstractmethod
    def from_params(cls, *args, **kwargs) -> FieldType:
        ...

    @abc.abstractmethod
    def _str(self, indent: Indenter, use_colour: bool) -> str: ...

    @abc.abstractmethod
    def _repr(self) -> str: ...

    @abc.abstractmethod
    def _copy(self) -> FieldType: ...

    @abc.abstractmethod
    def _get_value(self) -> Any: ...

    @abc.abstractmethod
    def _set_value_with_kwargs(self, value: Any, kwargs: dict[str, Any]) -> None: ...

    def _set_value(self, value: Any):
        self._set_value_with_kwargs(value, {})

    @abc.abstractmethod
    def _get_bit_length(self) -> int:
        """
        Return the length of the FieldType in bits.

        :return: The length in bits.
        :rtype: int

        Raises ValueError if length cannot be calculated or known.
        """
        ...

    @property
    def bit_length(self) -> int:
        return self._get_bit_length()

    @abc.abstractmethod
    def __eq__(self, other) -> bool: ...

    def __copy__(self) -> FieldType:
        return self._copy()

    def _get_name(self) -> str:
        return self._name

    def _set_name(self, val: str) -> None:
        if val != "":
            if not val.isidentifier():
                raise ValueError(f"The FieldType name '{val}' is not permitted as it is not a valid Python identifier.")
            if keyword.iskeyword(val):
                raise ValueError(f"The FieldType name '{val}' is not permitted as it is a Python keyword.")
            if "__" in val:
                raise ValueError(f"The FieldType name '{val}' contains a double underscore which is not permitted.")
        self._name = val

    @property
    def value(self) -> Any:
        return self._get_value()

    @value.setter
    def value(self, val: Any) -> None:
        self._set_value_with_kwargs(val, {})

    @property
    def name(self) -> str:
        return self._get_name()

    @name.setter
    def name(self, val: str) -> None:
        self._set_name(val)

