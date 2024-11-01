from __future__ import annotations
import abc
import sys

from bitformat import Bits
from ._bits import BitsType
from ._common import final, Indenter
from typing import Any, Sequence, TextIO
import keyword
from ._options import Options


__all__ = ['FieldType']

fieldtype_classes = {}

class FieldType(abc.ABC):

    def __new__(cls, *args, **kwargs) -> FieldType:
        x = super().__new__(cls)
        x._name = ''
        x._comment = ''
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
        b = Bits() if b is None else Bits.from_auto(b)
        self.clear()
        try:
            return self._parse(b, 0, kwargs)
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
        return self._str(Indenter(Options().indent_size))

    def __repr__(self) -> str:
        """
        Return a detailed string representation of the field type.

        :return: The detailed string representation.
        :rtype: str
        """
        return self._repr()

    def pp(self, stream: TextIO = sys.stdout, indent: int | None = None, depth: int | None = None) -> None:
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
        stream.write('\n')

    @classmethod
    def from_string(cls, s: str) -> FieldType:
        """
        Create a FieldType instance from a string.

        The type is inferred from the string, so it can be a Field, Format, or other FieldType.

        :param s: The string to parse.
        :type s: str
        :return: The FieldType instance.
        :rtype: FieldType
        """
        s = s.strip()
        if s == '':
            return fieldtype_classes['Pass']()
        elif s.startswith('if'): # TODO: this isn't a good enough test
            return fieldtype_classes['If'].from_string(s)
        elif s.startswith('Repeat('):
            return fieldtype_classes['Repeat'].from_string(s)
        elif s.endswith(')'):
            # If it's legal it must be a Format.
            return fieldtype_classes['Format'].from_string(s)
        else:
            return fieldtype_classes['Field'].from_string(s)

    @abc.abstractmethod
    def _parse(self, b: Bits, startbit: int, vars_: dict[str, Any]) -> int:
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
    def _str(self, indent: Indenter) -> str:
        ...

    @abc.abstractmethod
    def _repr(self) -> str:
        ...

    @abc.abstractmethod
    def _copy(self) -> FieldType:
        ...

    @abc.abstractmethod
    def _getvalue(self) -> Any:
        ...

    @abc.abstractmethod
    def _setvalue(self, value: Any) -> None:
        ...

    @abc.abstractmethod
    def _getbitlength(self) -> int:
        """
        Return the length of the FieldType in bits.

        :return: The length in bits.
        :rtype: int

        Raises ValueError if length cannot be calculated or known.
        """
        ...

    @property
    def bitlength(self) -> int:
        return self._getbitlength()

    @abc.abstractmethod
    def __eq__(self, other) -> bool:
        ...

    def __copy__(self) -> FieldType:
        return self._copy()

    def _get_name(self) -> str:
        return self._name

    def _set_name(self, val: str) -> None:
        if val != '':
            if not val.isidentifier():
                raise ValueError(f"The FieldType name '{val}' is not a valid Python identifier.")
            if keyword.iskeyword(val):
                raise ValueError(f"The FieldType name '{val}' is a Python keyword.")
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
