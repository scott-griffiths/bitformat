from __future__ import annotations

import abc
import functools
from typing import Any, Callable, Iterable, Sequence, overload, Union, Self
import inspect
import bitformat
from ._common import Expression, Endianness, byteorder, DtypeName, override, final, field_type_parser
from lark import Transformer, UnexpectedInput
import lark

# Things that can be converted to Bits when a Bits type is needed
BitsType = Union["Bits", str, Iterable[Any], bytearray, bytes, memoryview]

__all__ = ["Dtype", "DtypeSingle", "DtypeArray", "DtypeTuple", "DtypeDefinition", "Register"]



class DtypeTransformer(Transformer):

    def NAME(self, item) -> str:
        return str(item)

    def INT(self, item) -> int:
        return int(item)

    def python_string(self, items) -> str:
        return str(items[0])

    def expression(self, items) -> Expression:
        assert len(items) == 1
        x = Expression('{' + items[0] + '}')
        return x

    def dtype_name(self, items) -> DtypeName:
        return DtypeName(items[0])

    def dtype_modifier(self, items) -> Endianness:
        return Endianness(items[0])

    def dtype_size(self, items) -> int | Expression:
        return items[0]

    def dtype_single(self, items) -> DtypeSingle:
        assert len(items) == 3
        name = items[0]
        endianness = Endianness.UNSPECIFIED if items[1] is None else items[1]
        size = items[2]
        return DtypeSingle.from_params(name, size, endianness)

    def dtype_items(self, items) -> int:
        return items[0]

    def dtype_array(self, items) -> DtypeArray:
        assert len(items) == 2
        dtype = items[0]
        items_count = items[1]
        return DtypeArray.from_params(dtype.name, dtype.size, items_count, dtype.endianness)

    def dtype_tuple(self, items) -> DtypeTuple:
        return DtypeTuple.from_params(items)

    def simple_value(self, items) -> str:
        assert len(items) == 1
        return str(items[0])

    def list_of_values(self, items):
        # TODO
        return str(items[0])


dtype_transformer = DtypeTransformer()

CACHE_SIZE = 256


class Dtype(abc.ABC):
    """An abstract data type class.

    Although this base class is abstract, the __init__ method can be used to construct its
    sub-classes via a formatted string.

    Dtype instances are immutable. They are often created implicitly via a token string.

    >>> a_12bit_int = Dtype('i12')  # Creates a DtypeSingle
    >>> five_16_bit_floats = Dtype('[f16; 5]')  # Creates a DtypeArray
    >>> a_tuple = Dtype('(bool, u7)')  # Creates a DtypeTuple

    """

    def __new__(cls, s: str | None = None, /) -> Self:
        if s is None:
            x = super().__new__(cls)
            return x
        return cls.from_string(s)

    @classmethod
    @abc.abstractmethod
    def from_params(cls, *args, **kwargs) -> Self:
        ...

    @classmethod
    def from_string(cls, s: str, /) -> Self:
        """Create a new Dtype sub-class from a token string.

        Some token string examples:

        * ``'u12'``: A DtypeSingle representing an unsigned 12-bit integer.
        * ``'[i6; 5]'``: A DtypeArray of 5 signed 6-bit integers.
        * ``'(bool, hex4, f16)'``: A DtypeTuple of a boolean, a 4-char hex value and a 16-bit float.

        As a shortcut the ``Dtype`` constructor can be used directly with a token string.

        ``Dtype(s)`` is equivalent to ``Dtype.from_string(s)``.

        """
        try:
            tree = field_type_parser.parse(s, start="dtype")
        except UnexpectedInput as e:
            raise ValueError(f"Error parsing dtype: {e}")
        try:
            return dtype_transformer.transform(tree)
        except lark.exceptions.VisitError as e:
            raise ValueError(f"Error parsing dtype: {e}")

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
    @abc.abstractmethod
    def bit_length(self) -> int | None:
        """The total length of the data type in bits.

        Returns ``None`` if the data type doesn't have a fixed length.

        .. code-block:: pycon

            >>> Dtype('u12').bit_length
            12
            >>> Dtype('[u12; 5]').bit_length
            60
            >>> Dtype('(hex5, bool)').bit_length
            21
            >>> Dtype('i').bit_length
            None

        """
    ...

    @abc.abstractmethod
    def __str__(self) -> str:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.__str__()}')"


class DtypeSingle(Dtype):

    _name: DtypeName
    _size: Expression
    _bit_length: int | None
    _definition: DtypeDefinition
    _endianness: Endianness

    @property
    def name(self) -> DtypeName:
        return self._definition.name

    @property
    def endianness(self) -> Endianness:
        """The endianness of the data type."""
        return self._endianness

    @classmethod
    # @functools.lru_cache(CACHE_SIZE)
    def _create(cls, definition: DtypeDefinition, size: Expression,
                endianness: Endianness = Endianness.UNSPECIFIED) -> Self:
        x = DtypeSingle.__new__(DtypeSingle)
        x._definition = definition
        if size.evaluate() is None and definition.allowed_sizes.only_one_value():
            size_int = definition.allowed_sizes.values[0]
            size = Expression(f"{{{size_int}}}")
        x._size = size
        if x._size.evaluate() is None:
            x._bit_length = None
        else:
            if definition.bits_per_character is None:
                x._bit_length = x._size.evaluate()
            else:
                x._bit_length = x._size.evaluate() * definition.bits_per_character
        little_endian = (endianness == Endianness.LITTLE or
                         (endianness == Endianness.NATIVE and bitformat.byteorder == "little"))
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
        return x

    @classmethod
    @override
    @final
    def from_params(cls, name: DtypeName, size: int | Expression | None = None,
                    endianness: Endianness = Endianness.UNSPECIFIED) -> Self:
        """Create a new Dtype from its name and size.

        It's usually clearer to use the Dtype constructor directly with a dtype str, but
        this builder will be more efficient and is used internally to avoid string parsing.

        """
        if size is None:
            size = Expression("{None}")
        elif isinstance(size, int):
            size = Expression(f"{{{size}}}")
        x = Register().get_single_dtype(name, size, endianness)
        return x

    @override
    @final
    def pack(self, value: Any, /) -> bitformat.Bits:
        # Single item to pack
        b = self._create_fn(value)
        if self._bit_length is not None and len(b) != self._bit_length:
            raise ValueError(f"Dtype '{self}' has a bit_length of {self._bit_length} bits, but value '{value}' has {len(b)} bits.")
        return b

    @override
    @final
    def unpack(self, b: BitsType, /) -> Any | tuple[Any]:
        b = bitformat.Bits._from_any(b)
        if self._bit_length is None:
            # Try to unpack everything
            return self._get_fn(b)
        elif self._bit_length > len(b):
            raise ValueError(f"{self!r} is {self._bit_length} bits long, but only got {len(b)} bits to unpack.")
        else:
            return self._get_fn(b[: self._bit_length])

    @override
    @final
    def __str__(self) -> str:
        hide_length = self.size is None or self._definition.allowed_sizes.only_one_value()
        size_str = "" if hide_length else str(self.size)
        endianness = "" if self._endianness == Endianness.UNSPECIFIED else "_" + self._endianness.value
        return f"{self._definition.name}{endianness}{size_str}"

    @override
    @final
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            other = Dtype.from_string(other)
        if isinstance(other, DtypeSingle):
            return (self._definition.name == other._definition.name
                    and self._size == other._size
                    and self._endianness == other._endianness)
        return False

    # TODO: move to base class as requirement?
    def __hash__(self) -> int:
        return hash(
            (self._definition.name, self._size)
        )

    @override
    @final
    @property
    def bit_length(self) -> int | None:
        return self._bit_length

    @property
    def size(self) -> int | Expression | None:
        """The size of the data type.

        This is the number used immediately after the data type name in a dtype string.
        For example, each of ``'u10'``, ``'hex10'`` and ``'[i10; 3]'`` have a size of 10 even
        though they have bitlengths of 10, 40 and 30 respectively.

        See also :attr:`bit_length`.

        """
        return self._size.evaluate()


class DtypeArray(Dtype):

    _dtype_single: DtypeSingle
    _items: int | None

    @property
    def name(self) -> DtypeName:
        return self._dtype_single.name

    @property
    def endianness(self) -> Endianness:
        """The endianness of the data type stored in the array."""
        return self._dtype_single.endianness

    @classmethod
    def _create(cls, definition: DtypeDefinition, size: Expression, items: int | None,
                endianness: Endianness = Endianness.UNSPECIFIED,) -> Self:
        x = super().__new__(cls)
        x._dtype_single = DtypeSingle._create(definition, size, endianness)
        x._items = items
        return x

    @classmethod
    @override
    @final
    def from_params(cls, name: DtypeName, size: Expression, items: int | None = None,
                    endianness: Endianness = Endianness.UNSPECIFIED) -> Self:
        """Create a new Dtype from its name, size and items.

        It's usually clearer to use the Dtype constructor directly with a dtype str, but
        this builder will be more efficient and is used internally to avoid string parsing.

        """
        return Register().get_array_dtype(name, size, items, endianness)

    @override
    @final
    def pack(self, value: Any, /) -> bitformat.Bits:
        if isinstance(value, bitformat.Bits):
            if len(value) != self.bit_length:
                raise ValueError(f"Expected {self.bit_length} bits, but got {len(value)} bits.")
            return value
        if self._items is not None and len(value) != self._items:
            raise ValueError(f"Expected {self._items} items, but got {len(value)}.")
        return bitformat.Bits.from_joined(self._dtype_single._create_fn(v) for v in value)

    @override
    @final
    def unpack(self, b: BitsType, /) -> Any | tuple[Any]:
        b = bitformat.Bits._from_any(b)
        if self.items is not None and self.bit_length > len(b):
            raise ValueError(f"{self!r} is {self.bit_length} bits long, but only got {len(b)} bits to unpack.")
        items = self.items
        if items is None:
            # For array dtypes with no items (e.g. '[u8;]') unpack as much as possible.
            items = len(b) // self._dtype_single.bit_length
        return tuple(
            self._dtype_single._get_fn(b[i * self._dtype_single.bit_length : (i + 1) * self._dtype_single.bit_length])
            for i in range(items)
        )

    @override
    @final
    def __str__(self) -> str:
        hide_length = self.size is None or self._dtype_single._definition.allowed_sizes.only_one_value()
        size_str = "" if hide_length else str(self.size)
        endianness = "" if self.endianness == Endianness.UNSPECIFIED else "_" + self.endianness.value
        items_str = "" if self._items is None else f" {self._items}"
        return f"[{self.name}{endianness}{size_str};{items_str}]"

    @override
    @final
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            other = Dtype.from_string(other)
        if isinstance(other, DtypeArray):
            return self._dtype_single == other._dtype_single and self.items == other.items
        return False

    @override
    @final
    def __hash__(self) -> int:
        return hash((self._dtype_single, self._items))

    @override
    @final
    @property
    def bit_length(self) -> int | None:
        if self._items is None:
            return None
        return self._dtype_single.bit_length * self._items

    @property
    def size(self) -> int:
        """The size of the data type.

        This is the number used immediately after the data type name in a dtype string.
        For example, each of ``'u10'``, ``'hex10'`` and ``'[i10; 3]'`` have a size of 10 even
        though they have bitlengths of 10, 40 and 30 respectively.

        See also :attr:`bit_length`.

        """
        return self._dtype_single.size

    @property
    def items(self) -> int:
        """The number of items in the data type.

        An items equal to 0 means it's an array data type but with items currently unset.

        """
        return self._items


class DtypeTuple(Dtype):
    """A data type class, representing a tuple of concrete interpretations of binary data.

    DtypeTuple instances are immutable. They are often created implicitly elsewhere via a token string.

    >>> a = Dtype('[u12, u8, bool]')
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
        for d in dtypes:
            dtype = d if isinstance(d, Dtype) else Dtype.from_string(d)
            if dtype.bit_length is None:
                raise ValueError(f"Can't create a DtypeTuple from dtype '{d}' as it has an unknown length.")
            x._dtypes.append(dtype)
        x._bit_length = sum(dtype.bit_length for dtype in x._dtypes)
        return x

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
        return hash(tuple(self._dtypes))

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

    def __init__(self, name: DtypeName, description: str, set_fn: Callable, get_fn: Callable,
                 return_type: Any = Any, is_signed: bool = False, bitlength2chars_fn=None,
                 allowed_sizes: tuple[int, ...] = tuple(), bits_per_character: int | None = None,
                 endianness_variants: bool = False):
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

            self.get_fn = allowed_size_checked_get_fn  # Interpret everything and check the size
        else:
            self.get_fn = get_fn  # Interpret everything
        if bits_per_character is not None:
            if bitlength2chars_fn is not None:
                raise ValueError("You shouldn't specify both a bits_per_character and a bitlength2chars_fn.")

            def bitlength2chars_fn(x):
                if x is None:
                    return 0
                return x // bits_per_character

        self.bitlength2chars_fn = bitlength2chars_fn

    def sanitize(self, size: Expression, endianness: Endianness) -> tuple[Expression, Endianness]:
        if size.evaluate() is not None and self.allowed_sizes:
            if size.evaluate() == 0:
                if self.allowed_sizes.only_one_value():
                    size = Expression("{{{self.allowed_sizes.values[0]}}}")
            else:
                if size.evaluate() not in self.allowed_sizes:
                    if self.allowed_sizes.only_one_value():
                        raise ValueError(f"A size of {size} was supplied for the '{self.name}' dtype, but its "
                                         f"only allowed size is {self.allowed_sizes.values[0]}.")
                    else:
                        raise ValueError(f"A size of {size} was supplied for the '{self.name}' dtype which "
                                         f"is not one of its possible sizes. Must be one of {self.allowed_sizes}.")
        if endianness != Endianness.UNSPECIFIED:
            if not self.endianness_variants:
                raise ValueError(f"The '{self.name}' dtype does not support endianness variants, but '{endianness.value}' was specified.")
            if size.evaluate() is not None and size.evaluate() % 8 != 0:
                raise ValueError(f"Endianness can only be specified for whole-byte dtypes, but '{self.name}' has a size of {size} bits.")
        return size, endianness

    def get_single_dtype(self, size: Expression, endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeSingle:
        size_int, endianness = self.sanitize(size, endianness)
        d = DtypeSingle._create(self, size, endianness)
        return d

    def get_array_dtype(self, size: Expression, items: int | None, endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeArray:
        size, endianness = self.sanitize(size, endianness)
        d = DtypeArray._create(self, size, items, endianness)
        if size.evaluate() is None:
            raise ValueError(f"Array dtypes must have a size specified. Got '{d}'. "
                             f"Note that the number of items in the array dtype can be unknown or zero, but the dtype of each item must have a known size.")
        return d

    def __repr__(self) -> str:
        s = [f"{self.__class__.__name__}(name='{self.name}'",
             f"description='{self.description}'",
             f"return_type={self.return_type.__name__}",
             f"is_signed={self.is_signed}",
             f"allowed_lengths={self.allowed_sizes!s}",
             f"bits_per_character={self.bits_per_character})"]
        return ", ".join(s)


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
        setattr(bitformat.Bits, name.value, property(fget=definition.get_fn,
                                                     doc=f"The Bits as {definition.description}. Read only."))
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

            for modifier, fget, desc in [("_le", fget_le, f"little-endian"),
                                         ("_be", fget_be, f"big-endian"),
                                         ("_ne", fget_ne, f"native-endian (i.e. {byteorder}-endian)")]:
                doc = f"The Bits as {definition.description} in {desc} byte order. Read only."
                setattr(bitformat.Bits, name.value + modifier, property(fget=fget, doc=doc))

    @classmethod
    # @functools.lru_cache(CACHE_SIZE)
    def get_single_dtype(cls, name: DtypeName, size: Expression | int | None,
                         endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeSingle:
        definition = cls.name_to_def[name]
        if size is None:
            size = Expression("{None}")
        elif isinstance(size, int):
            size = Expression(f"{{{size}}}")
        return definition.get_single_dtype(size, endianness)

    @classmethod
    # @functools.lru_cache(CACHE_SIZE)
    def get_array_dtype(cls, name: DtypeName, size: Expression | int | None, items: int,
                        endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeArray:
        definition = cls.name_to_def[name]
        if size is None:
            size = Expression("{None}")
        elif isinstance(size, int):
            size = Expression(f"{{{size}}}")
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
