from __future__ import annotations

import abc
import functools
from typing import Any, Callable, Iterable, Sequence, overload, Union, Self
import inspect
import bitformat
import re
from ._common import Expression, Endianness, byteorder, DtypeName, override, final
from typing import Pattern

# Things that can be converted to Bits when a Bits type is needed
BitsType = Union["Bits", str, Iterable[Any], bytearray, bytes, memoryview]

__all__ = ["Dtype", "DtypeSingle", "DtypeArray", "DtypeTuple", "DtypeDefinition", "Register"]

CACHE_SIZE = 256

# A token name followed by an integer number
NAME_INT_RE: Pattern[str] = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*?)(\d*)$")

def parse_name_size_token(fmt: str) -> tuple[str, int]:
    if not (match := NAME_INT_RE.match(fmt)):
        raise ValueError(f"Can't parse Dtype token '{fmt}' as 'name[length]'.")
    name, length_str = match.groups()
    return name, int(length_str) if length_str else 0

# A token name followed by a string that starts with '{' and ends with '}'
NAME_EXPRESSION_RE: Pattern[str] = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*?)({.*})$")

def parse_name_expression_token(fmt: str) -> tuple[str, str]:
    if not (match := NAME_EXPRESSION_RE.match(fmt)):
        raise ValueError(f"Can't parse Dtype expression token '{fmt}'.")
    name, expression = match.groups()
    return name, expression

def parse_name_to_name_and_modifier(name: str) -> tuple[str, str]:
    modifiers = name.split("_")
    if len(modifiers) == 1:
        return name, ""
    if len(modifiers) == 2:
        return modifiers[0], modifiers[1]
    raise ValueError(f"Can't parse Dtype name '{name}' as more than one '_' is present.")


class Dtype(abc.ABC):
    """An abstract data type class.

    Although this base class is abstract, the __init__ method can be used to construct its
    sub-classes via a formatted string.

    Dtype instances are immutable. They are often created implicitly via a token string.

    >>> a_12bit_int = Dtype('i12')  # Creates a DtypeSingle
    >>> five_16_bit_floats = Dtype('[f16; 5]')  # Creates a DtypeArray
    >>> a_tuple = Dtype('(bool, u7)')  # Creates a DtypeTuple

    """

    _name: DtypeName
    _endianness: Endianness

    def __new__(cls, token: str | None = None, /) -> Self:
        if token is None:
            x = super().__new__(cls)
            return x
        return cls.from_string(token)

    @classmethod
    @abc.abstractmethod
    def _from_string(cls, s:str) -> Self:
        ...

    @classmethod
    @abc.abstractmethod
    def from_params(cls, *args, **kwargs) -> Self:
        ...

    @classmethod
    def from_string(cls, s: str) -> Self:
        """Create a new Dtype sub-class from a token string.

        Some token string examples:

        * ``'u12'``: A DtypeSingle representing an unsigned 12-bit integer.
        * ``'[i6; 5]'``: A DtypeArray of 5 signed 6-bit integers.

        As a shortcut the ``Dtype`` constructor can be used directly with a token string.

        ``Dtype(s)`` is equivalent to ``Dtype.from_string(s)``.

        """
        s = "".join(s.split())  # Remove whitespace
        # Delegate to the appropriate class
        if s.startswith("("):
            return DtypeTuple._from_string(s)
        if s.startswith("["):
            if "{" in s:
                return DtypeArrayWithExpression._from_string(s)
            else:
                return DtypeArray._from_string(s)
        else:
            if "{" in s:
                return DtypeSingleWithExpression._from_string(s)
            else:
                return DtypeSingle._from_string(s)

    @abc.abstractmethod
    def pack(self, value: Any, /) -> bitformat.Bits:
        """Create and return a new Bits from a value.

        The value parameter should be of a type appropriate to the data type.

        """
        ...

    @abc.abstractmethod
    def unpack(self, b: BitsType, /):
        """Unpack a Bits to find its value.

        The b parameter should be a Bits of the appropriate length, or an object that can be converted to a Bits.

        """
        ...

    @property
    def name(self) -> DtypeName:
        """An Enum giving the name of the data type."""
        return self._name

    @property
    def endianness(self) -> Endianness:
        """The endianness of the data type."""
        return self._endianness

    @property
    @abc.abstractmethod
    def bit_length(self) -> int:
        """The total length of the data type in bits.

        .. code-block:: pycon

            >>> Dtype('u12').bit_length
            12
            >>> Dtype('[u12; 5]').bit_length
            60
            >>> Dtype('hex5').bit_length
            20

        """
    ...

    @property
    def return_type(self) -> Any:
        """The type of the value returned by the parse method, such as ``int``, ``float`` or ``str``."""
        return self._return_type

    @property
    def is_signed(self) -> bool:
        """Returns bool indicating if the data type represents a signed quantity."""
        return self._is_signed

    @property
    def bits_per_character(self) -> int | None:
        """The number of bits represented by a single character of the underlying data type.

        For binary this is 1, for octal 3, hex 4 and for bytes this is 8. For types that don't
        have a direct relationship between bits and characters this will be None.

        """
        return self._bits_per_character

    @abc.abstractmethod
    def __str__(self) -> str:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.__str__()}')"


class DtypeSingle(Dtype):

    _size: int
    _bit_length: int

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def _create(cls, definition: DtypeDefinition, size: int,
                endianness: Endianness = Endianness.UNSPECIFIED) -> Self:
        x = DtypeSingle.__new__(DtypeSingle)
        x._name = definition.name
        x._bit_length = x._size = size
        x._bits_per_character = definition.bits_per_character
        if definition.bits_per_character is not None:
            x._bit_length *= definition.bits_per_character
        little_endian: bool = endianness == Endianness.LITTLE or (
            endianness == Endianness.NATIVE and bitformat.byteorder == "little"
        )
        x._endianness = endianness
        x._get_fn = (
            (lambda b: definition.get_fn(b.byte_swap()))
            if little_endian
            else definition.get_fn
        )
        if "length" in inspect.signature(definition.set_fn).parameters:
            set_fn = functools.partial(definition.set_fn, length=x._bit_length)
        else:
            set_fn = definition.set_fn

        def create_bits(v):
            b = bitformat.Bits()
            # The set_fn will do the length check for big endian too.
            set_fn(b, v)
            return b

        def create_bits_le(v):
            b = bitformat.Bits()
            set_fn(b, v)
            return b.byte_swap()

        x._create_fn = create_bits_le if little_endian else create_bits

        x._return_type = definition.return_type
        x._is_signed = definition.is_signed
        return x

    @classmethod
    @override
    @final
    def from_params(cls, name: DtypeName, size: int = 0,
                    endianness: Endianness = Endianness.UNSPECIFIED) -> Self:
        """Create a new Dtype from its name and size.

        It's usually clearer to use the Dtype constructor directly with a dtype str, but
        this builder will be more efficient and is used internally to avoid string parsing.

        """
        return Register().get_single_dtype(name, size, endianness)

    @classmethod
    @override
    @final
    def _from_string(cls, token: str, /) -> Self:
        try:
            name, size = parse_name_size_token(token)
        except ValueError as e:
            if "," in token:
                raise ValueError(
                    f"Can't parse token '{token}' as a single 'name[length]'. Did you mean to use a DtypeTuple instead?"
                )
            else:
                raise e
        name_str, modifier = parse_name_to_name_and_modifier(name)

        endianness = Endianness(modifier)
        try:
            name = DtypeName(name_str)
        except ValueError:
            aliases = {"int": "i", "uint": "u", "float": "f"}
            extra = f"Did you mean '{aliases[name_str]}'? " if name_str in aliases else ""
            raise ValueError(f"Unknown Dtype name '{name_str}'. {extra}Names available: {list(Register().name_to_def.keys())}.")
        return Register().get_single_dtype(name, size, endianness)

    @override
    @final
    def pack(self, value: Any, /) -> bitformat.Bits:
        # Single item to pack
        b = self._create_fn(value)
        if self._bit_length != 0 and len(b) != self._bit_length:
            raise ValueError(
                f"Dtype '{self}' has a bit_length of {self._bit_length} bits, but value '{value}' has {len(b)} bits."
            )
        return b

    @override
    @final
    def unpack(self, b: BitsType, /) -> Any | tuple[Any]:
        b = bitformat.Bits._from_any(b)
        if self._bit_length > len(b):
            raise ValueError(
                f"{self!r} is {self._bit_length} bits long, but only got {len(b)} bits to unpack."
            )
        if self._bit_length == 0:
            # Try to unpack everything
            return self._get_fn(b)
        else:
            return self._get_fn(b[: self._bit_length])

    @override
    @final
    def __str__(self) -> str:
        hide_length = (
            Register().name_to_def[self._name].allowed_sizes.only_one_value()
            or self.size == 0
        )
        size_str = "" if hide_length else str(self.size)
        endianness = (
            ""
            if self._endianness == Endianness.UNSPECIFIED
            else "_" + self._endianness.value
        )
        return f"{self._name}{endianness}{size_str}"

    @override
    @final
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            other = Dtype.from_string(other)
        if isinstance(other, DtypeSingle):
            return (
                self._name == other._name
                and self._size == other._size
                and self._endianness == other._endianness
            )
        return False

    # TODO: move to base class as requirement?
    def __hash__(self) -> int:
        return hash(
            (self._name, self._size)
        )

    @override
    @final
    @property
    def bit_length(self) -> int:
        return self._bit_length

    @property
    def size(self) -> int:
        """The size of the data type.

        This is the number used immediately after the data type name in a dtype string.
        For example, each of ``'u10'``, ``'hex10'`` and ``'[i10; 3]'`` have a size of 10 even
        though they have bitlengths of 10, 40 and 30 respectively.

        See also :attr:`bit_length`.

        """
        return self._size


class DtypeArray(Dtype):

    _size: int
    _items: int | None
    _bits_per_item: int

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def _create(cls, definition: DtypeDefinition, size: int, items: int = 1,
                endianness: Endianness = Endianness.UNSPECIFIED,) -> Self:
        x = super().__new__(cls)
        x._name = definition.name
        x._items = items
        x._bits_per_item = x._size = size
        x._bits_per_character = definition.bits_per_character
        if definition.bits_per_character is not None:
            x._bits_per_item *= definition.bits_per_character
        little_endian: bool = endianness == Endianness.LITTLE or (
            endianness == Endianness.NATIVE and bitformat.byteorder == "little"
        )
        x._endianness = endianness
        x._get_fn = (
            (lambda b: definition.get_fn(b.byte_swap()))
            if little_endian
            else definition.get_fn
        )
        if "length" in inspect.signature(definition.set_fn).parameters:
            set_fn = functools.partial(definition.set_fn, length=x._bits_per_item)
        else:
            set_fn = definition.set_fn

        def create_bits(v):
            b = bitformat.Bits()
            # The set_fn will do the length check for big endian too.
            set_fn(b, v)
            return b

        def create_bits_le(v):
            b = bitformat.Bits()
            set_fn(b, v)
            return b.byte_swap()

        x._create_fn = create_bits_le if little_endian else create_bits

        x._return_type = tuple
        x._is_signed = definition.is_signed
        return x

    @classmethod
    @override
    @final
    def from_params(
        cls,
        name: DtypeName,
        size: int = 0,
        items: int | None = None,
        endianness: Endianness = Endianness.UNSPECIFIED,
    ) -> Self:
        """Create a new Dtype from its name, size and items.

        It's usually clearer to use the Dtype constructor directly with a dtype str, but
        this builder will be more efficient and is used internally to avoid string parsing.

        """
        return Register().get_array_dtype(name, size, items, endianness)

    @classmethod
    @override
    @final
    def _from_string(cls, token: str, /) -> Self:
        if not token.startswith("[") or not token.endswith("]") or (p := token.find(";")) == -1:
            raise ValueError(f"Array Dtype strings should be of the form '[dtype; items]'. Got '{token}'.")
        t = token[p + 1 : -1]
        items = int(t) if t else 0
        name_str, size = parse_name_size_token(token[1:p])
        name_str, modifier = parse_name_to_name_and_modifier(name_str)
        endianness = Endianness(modifier)

        try:
            name = DtypeName(name_str)
        except ValueError:
            aliases = {"int": "i", "uint": "u", "float": "f"}
            extra = f"Did you mean '{aliases[name_str]}'? " if name_str in aliases else ""
            raise ValueError(f"Unknown Dtype name '{name_str}'. {extra}Names available: {list(Register().name_to_def.keys())}.")
        return Register().get_array_dtype(name, size, items, endianness)

    @override
    @final
    def pack(self, value: Any, /) -> bitformat.Bits:
        if isinstance(value, bitformat.Bits):
            if len(value) != self.bit_length:
                raise ValueError(f"Expected {self.bit_length} bits, but got {len(value)} bits.")
            return value
        if len(value) != self._items and self._items != 0:
            raise ValueError(f"Expected {self._items} items, but got {len(value)}.")
        return bitformat.Bits.from_joined(self._create_fn(v) for v in value)

    @override
    @final
    def unpack(self, b: BitsType, /) -> Any | tuple[Any]:
        b = bitformat.Bits._from_any(b)
        if self.bit_length > len(b):
            raise ValueError(
                f"{self!r} is {self.bit_length} bits long, but only got {len(b)} bits to unpack."
            )
        items = self.items
        if items == 0:
            # For array dtypes with no items (e.g. '[u8;]') unpack as much as possible.
            items = len(b) // self._bits_per_item
        return tuple(
            self._get_fn(b[i * self._bits_per_item : (i + 1) * self._bits_per_item])
            for i in range(items)
        )

    @override
    @final
    def __str__(self) -> str:
        hide_length = (
            Register().name_to_def[self._name].allowed_sizes.only_one_value()
            or self.size == 0
        )
        size_str = "" if hide_length else str(self.size)
        endianness = (
            ""
            if self._endianness == Endianness.UNSPECIFIED
            else "_" + self._endianness.value
        )
        items_str = "" if self._items == 0 else f" {self._items}"
        return f"[{self._name}{self._endianness.value}{size_str};{items_str}]"

    @override
    @final
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            other = Dtype.from_string(other)
        if isinstance(other, Dtype):
            return (
                self._name == other._name
                and self._size == other._size
                and self._items == other._items
                and self._endianness == other._endianness
            )
        return False

    @override
    @final
    def __hash__(self) -> int:
        return hash(
            (self._name.value, self._size, self._items)
        )

    @override
    @final
    @property
    def bit_length(self) -> int:
        return self._bits_per_item * self._items

    @property
    def size(self) -> int:
        """The size of the data type.

        This is the number used immediately after the data type name in a dtype string.
        For example, each of ``'u10'``, ``'hex10'`` and ``'[i10; 3]'`` have a size of 10 even
        though they have bitlengths of 10, 40 and 30 respectively.

        See also :attr:`bit_length`.

        """
        return self._size

    @property
    def items(self) -> int:
        """The number of items in the data type.

        An items equal to 0 means it's an array data type but with items currently unset.

        """
        return self._items


# TODO: Note this class isn't properly used yet, so don't expect it to really work.
class DtypeSingleWithExpression(DtypeSingle):
    size_expression: Expression | None
    base_dtype: Dtype

    def __init__(self, name: str, size: int | Expression, endianness: Endianness = Endianness.UNSPECIFIED):
        if isinstance(size, Expression):
            self.size_expression = size
            size = 0
        else:
            self.size_expression = None
        self.base_dtype = Register().get_single_dtype(name, size, endianness)

    def __new__(cls, *args, **kwargs):
        super().__new__(cls)

    @classmethod
    def from_string(cls, token: str, /) -> Dtype:
        x = super().__new__(cls)
        name, size_str = parse_name_expression_token(token)
        try:
            size = int(size_str)
            x.size_expression = None
        except ValueError:
            x.size_expression = Expression(size_str)
            size = 0
        name, modifier = parse_name_to_name_and_modifier(name)
        endianness = Endianness(modifier)
        x.base_dtype = Register().get_single_dtype(name, size, endianness)
        return x

    def evaluate(self, vars_: dict[str, Any]) -> Dtype:
        if self.size_expression is None and self.items_expression is None:
            return self.base_dtype
        if not vars_:
            return self.base_dtype
        name = self.base_dtype.name
        size = self.size_expression.evaluate(vars_) if (self.size_expression and vars_) else self.base_dtype.size
        endianness = self.base_dtype.endianness
        return Register().get_single_dtype(name, size, endianness)

    def __str__(self) -> str:
        only_one_value = Register().name_to_def[self.base_dtype.name].allowed_sizes.only_one_value()
        no_value_given = self.base_dtype.size == 0 and self.size_expression is None
        hide_size = only_one_value or no_value_given
        size_str = "" if hide_size else (self.size_expression if self.size_expression else str(self.base_dtype.size))
        return f"{self.base_dtype.name}{self.base_dtype.endianness.value}{size_str}"

# TODO: Note this class isn't really used, so things like __init__ won't even work yet.
class DtypeArrayWithExpression(DtypeArray):
    size_expression: Expression | None
    items_expression: Expression | None
    base_dtype: Dtype

    def __init__(self, name: str, size: int | Expression, endianness: Endianness = Endianness.UNSPECIFIED):
        if isinstance(size, Expression):
            self.size_expression = size
            size = 0
        else:
            self.size_expression = None
        self.base_dtype = Register().get_single_dtype(name, size, endianness)

    def __new__(cls, *args, **kwargs):
        super().__new__(cls)

    @classmethod
    def from_string(cls, token: str, /) -> DtypeArrayWithExpression:
        x = super().__new__(cls)
        p = token.find("{")
        if p == -1:
            raise ValueError  # TODO
        token = "".join(token.split())  # Remove whitespace
        if token.startswith("[") and token.endswith("]"):
            if (p := token.find(";")) == -1:
                raise ValueError(f"Array Dtype strings should be of the form '[dtype; items]'. Got '{token}'.")
            t = token[p + 1 : -1]
            try:
                items = int(t) if t else 0
                x.items_expression = None
            except ValueError:
                x.items_expression = Expression(t)
                items = 1
            name, size_str = parse_name_expression_token(token[1:p])
            try:
                size = int(size_str)
                x.size_expression = None
            except ValueError:
                x.size_expression = Expression(size_str)
                size = 0
            name, modifier = parse_name_to_name_and_modifier(name)
            endianness = Endianness(modifier)
            x.base_dtype = Register().get_array_dtype(name, size, items, endianness)
            return x
        else:
            raise ValueError

    def evaluate(self, vars_: dict[str, Any]) -> Dtype:
        if self.size_expression is None and self.items_expression is None:
            return self.base_dtype
        if not vars_:
            return self.base_dtype
        name = self.base_dtype.name
        size = self.size_expression.evaluate(vars_) if (self.size_expression and vars_) else self.base_dtype.size
        items = self.items_expression.evaluate(vars_) if (self.items_expression and vars_) else self.base_dtype.items
        endianness = self.base_dtype.endianness
        return Register().get_array_dtype(name, size, items, endianness)

    def __str__(self) -> str:
        only_one_value = Register().name_to_def[self.base_dtype.name].allowed_sizes.only_one_value()
        no_value_given = self.base_dtype.size == 0 and self.size_expression is None
        hide_size = only_one_value or no_value_given
        size_str = "" if hide_size else (self.size_expression if self.size_expression else str(self.base_dtype.size))
        hide_items = self.base_dtype.items == 0 and self.items_expression is None
        items_str = "" if hide_items else (" " + self.items_expression if self.items_expression else " " + str(self.base_dtype.items))
        return f"[{self.base_dtype.name}{self.base_dtype.endianness.value}{size_str};{items_str}]"


class DtypeTuple(Dtype):
    """A data type class, representing a tuple of concrete interpretations of binary data.

    DtypeTuple instances are immutable. They are often created implicitly elsewhere via a token string.

    >>> a = DtypeTuple('[u12, u8, bool]')
    >>> b = DtypeTuple.from_params(['u12', 'u8', 'bool'])

    """

    _dtypes: list[Dtype]
    _bit_length: int

    def __new__(cls, s: str) -> Self:
        return cls.from_string(s)

    @classmethod
    def from_params(cls, dtypes: Sequence[Dtype | str]) -> Self:
        x = super().__new__(cls)
        x._dtypes = []
        x._name = DtypeName.TUPLE
        for d in dtypes:
            dtype = d if isinstance(d, Dtype) else Dtype.from_string(d)
            if dtype.bit_length == 0:
                raise ValueError(f"Can't create a DtypeTuple from dtype '{d}' as it has an unknown length.")
            x._dtypes.append(dtype)
        x._bit_length = sum(dtype.bit_length for dtype in x._dtypes)
        return x

    @override
    @final
    @classmethod
    def _from_string(cls, s: str, /) -> Self:
        if not s.startswith("(") or not s.endswith(")"):
            raise ValueError(f"DtypeTuple strings should be of the form '(dtype1, dtype2, ...)'. Got '{s}'.")
        tokens = [t.strip() for t in s[1: -1].split(",")]
        dtypes = [Dtype.from_string(token) for token in tokens if token != '']
        return cls.from_params(dtypes)

    @override
    @final
    def pack(self, values: Sequence[Any]) -> bitformat.Bits:
        if len(values) != len(self):
            raise ValueError(f"Expected {len(self)} values, but got {len(values)}.")
        return bitformat.Bits.from_joined(dtype.pack(value) for dtype, value in zip(self._dtypes, values))

    @override
    @final
    def unpack(self, b: bitformat.Bits | str | Iterable[Any] | bytearray | bytes | memoryview, /) -> tuple[tuple[Any] | Any]:
        """Unpack a Bits to find its value.

        The b parameter should be a Bits of the appropriate length, or an object that can be converted to a Bits.

        """
        b = bitformat.Bits._from_any(b)
        if self.bit_length > len(b):
            raise ValueError(f"{self!r} is {self.bit_length} bits long, but only got {len(b)} bits to unpack.")
        vals = []
        pos = 0
        for dtype in self:
            if dtype.name != DtypeName.PAD:
                vals.append(dtype.unpack(b[pos : pos + dtype.bit_length]))
            pos += dtype.bit_length
        return tuple(vals)

    @override
    @final
    @property
    def bit_length(self) -> int:
        return self._bit_length

    # TODO: This is defined as not allowed in the base class
    def __len__(self) -> int:
        return len(self._dtypes)

    @override
    @final
    def __eq__(self, other) -> bool:
        if isinstance(other, DtypeTuple):
            return self._dtypes == other._dtypes
        return False

    @override
    @final
    def __hash__(self) -> int:
        return hash(
            tuple(self._dtypes)
        )

    @overload
    def __getitem__(self, key: int) -> Dtype: ...

    @overload
    def __getitem__(self, key: slice) -> DtypeTuple: ...

    def __getitem__(self, key: int | slice) -> Dtype | DtypeTuple:
        if isinstance(key, int):
            return self._dtypes[key]
        return DtypeTuple.from_params(self._dtypes[key])

    def __iter__(self):
        return iter(self._dtypes)

    @override
    @final
    def __str__(self) -> str:
        return "(" + ", ".join(str(dtype) for dtype in self._dtypes) + ")"


class AllowedSizes:
    values: tuple[int, ...]

    """Used to specify either concrete values or ranges of values that are allowed lengths for data types."""

    def __init__(self, values: tuple[int, ...] = tuple()) -> None:
        self.values = values

    def __bool__(self) -> bool:
        return bool(self.values)

    def __str__(self) -> str:
        return str(self.values)

    def __contains__(self, other: Any) -> bool:
        if not self.values:
            return True
        return other in self.values

    def only_one_value(self) -> bool:
        return bool(self.values and len(self.values) == 1)


class DtypeDefinition:
    """Represents a class of dtypes, such as ``bytes`` or ``f``, rather than a concrete dtype such as ``f32``."""

    def __init__(
        self,
        name: DtypeName,
        description: str,
        set_fn: Callable,
        get_fn: Callable,
        return_type: Any = Any,
        is_signed: bool = False,
        bitlength2chars_fn=None,
        allowed_sizes: tuple[int, ...] = tuple(),
        bits_per_character: int | None = None,
        endianness_variants: bool = False,
    ):
        self.name = name
        self.description = description
        self.return_type = return_type
        self.is_signed = is_signed
        self.allowed_sizes = AllowedSizes(allowed_sizes)
        self.bits_per_character = bits_per_character
        self.set_fn = set_fn
        self.endianness_variants = endianness_variants

        if self.allowed_sizes.values:

            def allowed_size_checked_get_fn(bs):
                if len(bs) not in self.allowed_sizes:
                    if self.allowed_sizes.only_one_value():
                        raise ValueError(f"'{self.name}' dtypes must have a size of {self.allowed_sizes.values[0]}, but received a size of {len(bs)}.")
                    else:
                        raise ValueError(f"'{self.name}' dtypes must have a size in {self.allowed_sizes}, but received a size of {len(bs)}.")
                return get_fn(bs)

            self.get_fn = (
                allowed_size_checked_get_fn  # Interpret everything and check the size
            )
        else:
            self.get_fn = get_fn  # Interpret everything
        if bits_per_character is not None:
            if bitlength2chars_fn is not None:
                raise ValueError("You shouldn't specify both a bits_per_character and a bitlength2chars_fn.")

            def bitlength2chars_fn(x):
                return x // bits_per_character

        self.bitlength2chars_fn = bitlength2chars_fn

    def sanitize(self, size: int, endianness: Endianness) -> tuple[int, Endianness]:
        if self.allowed_sizes:
            if size == 0:
                if self.allowed_sizes.only_one_value():
                    size = self.allowed_sizes.values[0]
            else:
                if size not in self.allowed_sizes:
                    if self.allowed_sizes.only_one_value():
                        raise ValueError(
                            f"A size of {size} was supplied for the '{self.name}' dtype, but its "
                            f"only allowed size is {self.allowed_sizes.values[0]}."
                        )
                    else:
                        raise ValueError(
                            f"A size of {size} was supplied for the '{self.name}' dtype which "
                            f"is not one of its possible sizes. Must be one of {self.allowed_sizes}."
                        )
        if endianness != Endianness.UNSPECIFIED:
            if not self.endianness_variants:
                raise ValueError(f"The '{self.name}' dtype does not support endianness variants, but '{endianness.value}' was specified.")
            if size % 8 != 0:
                raise ValueError(f"Endianness can only be specified for whole-byte dtypes, but '{self.name}' has a size of {size} bits.")
        return size, endianness

    def get_single_dtype(self, size: int = 0, endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeSingle:
        size, endianness = self.sanitize(size, endianness)
        d = DtypeSingle._create(self, size, endianness)
        return d

    def get_array_dtype(self, size: int, items: int, endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeArray:
        size, endianness = self.sanitize(size, endianness)
        d = DtypeArray._create(self, size, items, endianness)
        if size == 0:
            raise ValueError(f"Array dtypes must have a size specified. Got '{d}'. "
                             f"Note that the number of items in the array dtype can be unknown, but the dtype of each item must have a known size.")
        return d

    def __repr__(self) -> str:
        s = (
            f"{self.__class__.__name__}(name='{self.name}', description='{self.description}', "
            f"return_type={self.return_type.__name__}, "
        )
        s += (
            f"is_signed={self.is_signed}, "
            f"allowed_lengths={self.allowed_sizes!s}, bits_per_character={self.bits_per_character})"
        )
        return s


class Register:
    """Returns the singleton register of the dtype definitions.

    This is used to maintain a centralized registry of data type definitions.
    It is not yet part of the public API, so should not be used.

    .. code-block:: pycon

        >>> print(Register())

    """

    _instance: Register | None = None
    name_to_def: dict[DtypeName, DtypeDefinition] = {}

    def __new__(cls) -> Register:
        # Singleton. Only one Register instance can ever exist.
        if cls._instance is None:
            cls._instance = super(Register, cls).__new__(cls)
        return cls._instance

    @classmethod
    def add_dtype(cls, definition: DtypeDefinition):
        name = definition.name
        cls.name_to_def[name] = definition
        setattr(
            bitformat.Bits,
            name.value,
            property(
                fget=definition.get_fn,
                doc=f"The Bits as {definition.description}. Read only.",
            ),
        )
        if definition.endianness_variants:

            def fget_be(b):
                if len(b) % 8 != 0:
                    raise ValueError(f"Cannot use endianness modifer for non whole-byte data. Got length of {len(b)} bits.")
                return definition.get_fn(b)

            def fget_le(b):
                if len(b) % 8 != 0:
                    raise ValueError(f"Cannot use endianness modifer for non whole-byte data. Got length of {len(b)} bits.")
                return definition.get_fn(b.byte_swap())

            fget_ne = fget_le if byteorder == "little" else fget_be
            setattr(
                bitformat.Bits,
                name.value + "_le",
                property(
                    fget=fget_le,
                    doc=f"The Bits as {definition.description} in little-endian byte order. Read only.",
                ),
            )
            setattr(
                bitformat.Bits,
                name.value + "_be",
                property(
                    fget=fget_be,
                    doc=f"The Bits as {definition.description} in big-endian byte order. Read only.",
                ),
            )
            setattr(
                bitformat.Bits,
                name.value + "_ne",
                property(
                    fget=fget_ne,
                    doc=f"The Bits as {definition.description} in native-endian (i.e. {byteorder}-endian) byte order. Read only.",
                ),
            )

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def get_single_dtype(cls, name: DtypeName, size: int | None,
                         endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeSingle:
        definition = cls.name_to_def[name]
        return definition.get_single_dtype(size, endianness)

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def get_array_dtype(cls, name: DtypeName, size: int, items: int,
                        endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeArray:
        definition = cls.name_to_def[name]
        return definition.get_array_dtype(size, items, endianness)

    def __repr__(self) -> str:
        s = [
            f"{'key':<12}:{'name':^12}{'signed':^8}{'allowed_lengths':^16}{'bits_per_character':^12}{'return_type':<13}"
        ]
        s.append("-" * 72)
        for key in self.name_to_def:
            m = self.name_to_def[key]
            allowed = "" if not m.allowed_sizes else m.allowed_sizes
            ret = "None" if m.return_type is None else m.return_type.__name__
            s.append(
                f"{key:<12}:{m.name:>12}{m.is_signed:^8}{allowed!s:^16}{m.bits_per_character:^12}{ret:<13} # {m.description}"
            )
        return "\n".join(s)
