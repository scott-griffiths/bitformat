from __future__ import annotations
import abc
from bitformat import Bits
from ._common import final
from typing import Any, Sequence


__all__ = ['FieldType']


class FieldType(abc.ABC):

    fieldtype_classes = []
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.fieldtype_classes.append(cls)

    @final
    def parse(self, b: BitsType = Bits(), /, **kwargs) -> int:
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
        self.clear()
        try:
            return self._parse(b, kwargs)
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

        The type is inferred from the string, so it can be a Field, Format, or other FieldType.

        :param s: The string to parse.
        :type s: str
        :return: The FieldType instance.
        :rtype: FieldType
        """
        try:  # A stupid way to get it to compile without a circular dependency.
            1 / 0
        except ZeroDivisionError:
            from ._format import Format
            from ._pass import Pass
            from ._field import Field
        s = s.strip()
        if s == '':
            return Pass()
        if ',' in s:
            # If it's legal it must be a Format.
            return Format.from_string(s)
        else:
            return Field.from_string(s)

            # TODO: We'll need logic like this once we have new FieldTypes.
            # for fieldtype in [f for f in cls.fieldtype_classes if f is not in (Format, Field)]:
            #     try:
            #         return fieldtype.from_string(s)
            #     except ExpressionError as e:
            #         raise ValueError(f"Error evaluating expression in '{s}': {str(e)}"
            #         # If we got as far as evaluating an Expression then we probably(?) have the correct
            #         # FieldType, so just return the error so it doesn't get hidden by later ones.
            #         break
            #     except ValueError as e:
            #         e.add_note(f"  Can't parse the string '{s}' as a {fieldtype.__name__}.")
            #         raise

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
    def _copy(self) -> FieldType:
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

    def __copy__(self) -> FieldType:
        return self._copy()

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

