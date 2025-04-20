from __future__ import annotations

import abc
import functools
from typing import Any, Callable, Iterable, Sequence, overload, Union, Self
import inspect
import bitformat
from ._common import Expression, Endianness, byteorder, DtypeKind, override, final, parser_str, ExpressionError
from lark import Transformer, UnexpectedInput
import lark


# Things that can be converted to Bits when a Bits type is needed
BitsType = Union["Bits", str, Iterable[Any], bytearray, bytes, memoryview]

__all__ = ["Dtype", "DtypeSingle", "DtypeArray", "DtypeTuple", "DtypeDefinition", "Register", "DtypeTransformer"]


class DtypeTransformer(Transformer):

    @staticmethod
    def NAME(item) -> str:
        return str(item)

    @staticmethod
    def INT(item) -> int:
        return int(item)

    @staticmethod
    def python_string(items) -> str:
        return str(items[0])

    @staticmethod
    def expression(items) -> Expression:
        assert len(items) == 1
        x = Expression('{' + items[0] + '}')
        return x

    @staticmethod
    def dtype_kind(items) -> DtypeKind:
        return DtypeKind(items[0])

    @staticmethod
    def dtype_modifier(items) -> Endianness:
        return Endianness(items[0])

    @staticmethod
    def dtype_size(items) -> int | Expression:
        return items[0]

    @staticmethod
    def dtype_single(items) -> DtypeSingle:
        assert len(items) == 3
        kind = items[0]
        endianness = Endianness.UNSPECIFIED if items[1] is None else items[1]
        size = items[2]
        return DtypeSingle.from_params(kind, size, endianness)

    @staticmethod
    def dtype_items(items) -> int:
        return items[0]

    @staticmethod
    def dtype_array(items) -> DtypeArray:
        assert len(items) == 2
        dtype = items[0]
        items_count = items[1]
        return DtypeArray.from_params(dtype.kind, dtype.size, items_count, dtype.endianness)

    @staticmethod
    def dtype_tuple(items) -> DtypeTuple:
        return DtypeTuple.from_params(items)

    @staticmethod
    def field_dtype_tuple(items) -> DtypeTuple:
        return DtypeTuple.from_params(items)

    def single_value(self, items) -> str:
        assert len(items) == 1
        return str(items[0])

    def list_of_values(self, items):
        return items


dtype_parser = lark.Lark(parser_str, start='dtype', parser='lalr', transformer=DtypeTransformer())

CACHE_SIZE = 256


class Dtype(abc.ABC):
    """An abstract base class for the :class:`DtypeSingle`, :class:`DtypeArray` and :class:`DtypeTuple` classes.

    The ``__init__`` method can be used to construct its sub-classes via a formatted string.

    Dtype sub-class instances are immutable. They are often created implicitly via a token string.

    .. code-block:: pycon

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

        :param s: The formatted string to convert to a Dtype.
        :type s: str
        :rtype: DtypeSingle | DtypeArray | DtypeTuple

        Some token string examples:

        * ``'u12'``: A DtypeSingle representing an unsigned 12-bit integer.
        * ``'[i6; 5]'``: A DtypeArray of 5 signed 6-bit integers.
        * ``'(bool, hex4, f16)'``: A DtypeTuple of a boolean, a 4-char hex value and a 16-bit float.

        As a shortcut the ``Dtype`` constructor can be used directly with a token string.

        ``Dtype(s)`` is equivalent to ``Dtype.from_string(s)``.

        """
        try:
            return dtype_parser.parse(s)
        except UnexpectedInput as e:
            raise ValueError(f"Error parsing dtype '{s}': {e}")

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

    @abc.abstractmethod
    def _get_bit_length(self) -> int | None:
        ...

    @property
    def bit_length(self) -> int | None:
        """The total length of the data type in bits.

        Returns ``None`` if the data type doesn't have a fixed or known length.

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
        return self._get_bit_length()

    @abc.abstractmethod
    def evaluate(self, **kwargs) -> Self:
        """Create a concrete Dtype using the values provided.

        If a Dtype has been defined in terms of expressions for its size or number of items
        then this method can return a concrete Dtype instance. If the Dtype does not contain
        any expressions then this method will just return it unchanged.

        .. code-block:: python

            concrete = Dtype('u32')
            e1 = Dtype('u{my_size}')
            e2 = Dtype('[u8; {my_items}]')

            assert e1.evaluate(my_size=32) == concrete
            assert e2.evaluate(my_items=10).bit_length == 80

        """
        ...

    @abc.abstractmethod
    def has_fixed_size(self) -> bool:
        """Return whether the size of the dtype is fully known.

        This will be True if the dtype has a known length that doesn't
        depend on any parameters or available data, otherwise it will be False.

        .. code-block:: pycon

            >>> Dtype('u32').has_fixed_size()
            True
            >>> Dtype('[f16; 4]').has_fixed_size()
            True
            >>> Dtype('[u32;]').has_fixed_size()
            False
            >>> Dtype('u{x}').has_fixed_size()
            False

        """
        ...

    @abc.abstractmethod
    def has_dynamic_size(self) -> bool:
        """Return whether the dtype can stretch to fit the available data.

        .. code-block:: pycon

            >>> d = Dtype('u')
            >>> d.has_dynamic_size()
            True
            >>> d.unpack('0b1')
            1
            >>> d.unpack('0x00001')
            1

        """
        ...

    @abc.abstractmethod
    def info(self) -> str:
        """
        Return a descriptive string with information about the Dtype.

        Note that the output is designed to be helpful to users and is not considered part of the API.
        You should not use the output programmatically as it may change even between point versions.
        """
        ...

    @abc.abstractmethod
    def __str__(self) -> str:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.__str__()}')"

    @abc.abstractmethod
    def __hash__(self) -> int:
        ...



class DtypeSingle(Dtype):
    """A data type of a single kind representing a single value.

    This is used to represent the simplest data types, such as an integer, float or a hex string.


    """

    _kind: DtypeKind
    _size: Expression
    _bit_length: int | None
    _definition: DtypeDefinition
    _endianness: Endianness
    _create_fn: Callable[[Any], bitformat.Bits]
    _get_fn: Callable[[bitformat.Bits], Any]

    @override
    def info(self) -> str:
        if self.bit_length is not None:
            bpc = self._definition.bits_per_character
            if bpc is not None and bpc != 1:
                len_str = f"{self.bit_length} bit ({self.size} characters)"
            else:
                len_str = f"{self.bit_length} bit"
        elif self._size.is_none():
            len_str = "variable length"
        else:
            len_str = f"{self._size} sized"
        return f"{len_str} {self._definition.short_description}"

    @property
    def kind(self) -> DtypeKind:
        return self._definition.kind

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
        if size.has_const_value and size.const_value is None and definition.allowed_sizes.only_one_value():
            size_int = definition.allowed_sizes.values[0]
            size = Expression.from_int(size_int)
        x._size = size
        x._bit_length = None
        if x._size.has_const_value and x._size.const_value is not None:
            if definition.bits_per_character is None:
                x._bit_length = x._size.const_value
            else:
                x._bit_length = x._size.const_value * definition.bits_per_character
        little_endian = (endianness is Endianness.LITTLE or
                     (endianness is Endianness.NATIVE and bitformat.byteorder == "little"))
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
    def from_params(cls, kind: DtypeKind, size: int | Expression | None = None,
                    endianness: Endianness = Endianness.UNSPECIFIED) -> Self:
        """Create a new Dtype from its kind and size.

        It's usually clearer to use the Dtype constructor directly with a dtype str, but
        this builder will be more efficient and is used internally to avoid string parsing.

        """
        if size is None:
            size = Expression.from_none()
        elif isinstance(size, int):
            size = Expression.from_int(size)
        x = Register().get_single_dtype(kind, size, endianness)
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
        if self._size.is_none():
            # Try to unpack everything
            return self._get_fn(b)
        if self._bit_length is None:
            raise ExpressionError(f"Cannot unpack a dtype with an unknown size. Got '{self}'")
        if self._bit_length > len(b):
            raise ValueError(f"{self!r} is {self._bit_length} bits long, but only got {len(b)} bits to unpack.")
        else:
            return self._get_fn(b[: self._bit_length])

    @override
    @final
    def has_fixed_size(self) -> bool:
        return self._size.has_const_value and self._size.const_value is not None

    @override
    @final
    def has_dynamic_size(self) -> bool:
        return self._size.is_none()

    @override
    @final
    def __str__(self) -> str:
        hide_length = self._size.has_const_value and self._size.const_value is None or self._definition.allowed_sizes.only_one_value()
        size_str = "" if hide_length else str(self.size)
        endianness = "" if self._endianness is Endianness.UNSPECIFIED else "_" + self._endianness.value
        return f"{self._definition.kind}{endianness}{size_str}"

    @override
    @final
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            other = Dtype.from_string(other)
        if isinstance(other, DtypeSingle):
            return (self._definition.kind == other._definition.kind
                    and self._size == other._size
                    and self._endianness is other._endianness)
        return False

    @override
    @final
    def __hash__(self) -> int:
        return hash((self._definition.kind, self._size))

    @override
    @final
    def _get_bit_length(self) -> int | None:
        return self._bit_length

    @override
    @final
    def evaluate(self, **kwargs) -> Self:
        if self._size.has_const_value:
            return self
        size = self._size.evaluate(**kwargs)
        return DtypeSingle.from_params(self.kind, size, self.endianness)

    @property
    def size(self) -> Expression:
        """The size of the data type as an Expression.

        This is the number used immediately after the data type kind in the dtype string.
        For example ``'u10'`` has a size of 10.

        See also :attr:`bit_length`.

        """
        return self._size


class DtypeArray(Dtype):

    _dtype_single: DtypeSingle
    _items: Expression

    @override
    def info(self) -> str:
        if self._items.is_none():
            item_str = "variable number of items"
        else:
            item_str = f"{self._items} items"
        return f"array of {self._dtype_single.info()} with {item_str}"

    @property
    def kind(self) -> DtypeKind:
        return self._dtype_single.kind

    @property
    def endianness(self) -> Endianness:
        """The endianness of the data type stored in the array."""
        return self._dtype_single.endianness

    @classmethod
    def _create(cls, definition: DtypeDefinition, size: Expression, items: Expression,
                endianness: Endianness = Endianness.UNSPECIFIED) -> Self:
        x = super().__new__(cls)
        x._dtype_single = DtypeSingle._create(definition, size, endianness)
        x._items = items
        return x

    @classmethod
    @override
    @final
    def from_params(cls, kind: DtypeKind, size: Expression, items: Expression = Expression.from_none(),
                    endianness: Endianness = Endianness.UNSPECIFIED) -> Self:
        """Create a new Dtype from its kind, size and items.

        It's usually clearer to use the Dtype constructor directly with a dtype str, but
        this builder will be more efficient and is used internally to avoid string parsing.

        """
        return Register().get_array_dtype(kind, size, items, endianness)

    @override
    @final
    def pack(self, value: Any, /) -> bitformat.Bits:
        if isinstance(value, bitformat.Bits):
            if len(value) != self.bit_length:
                raise ValueError(f"Expected {self.bit_length} bits, but got {len(value)} bits.")
            return value
        if not self._items.is_none() and len(value) != self._items:
            raise ValueError(f"Expected {self._items} items, but got {len(value)}.")
        return bitformat.Bits.from_joined(self._dtype_single._create_fn(v) for v in value)

    @override
    @final
    def unpack(self, b: BitsType, /) -> Any | tuple[Any]:
        b = bitformat.Bits._from_any(b)
        if self.items is not None and self.bit_length is not None and self.bit_length > len(b):
            raise ValueError(f"{self!r} is {self.bit_length} bits long, but only got {len(b)} bits to unpack.")
        items = self._items.evaluate()
        if self._dtype_single.bit_length is None:
            raise ValueError(f"Cannot unpack when the DtypeSingle has an unknown size. Got '{self}'")
        if self._items.is_none():
            # For array dtypes with no items (e.g. '[u8;]') unpack as much as possible.
            if self._dtype_single.bit_length is None:
                raise ValueError(f"Cannot unpack when DtypeArray items is unspecified and the DtypeSingle has an unknown size. Got '{self}'")
            items = len(b) // self._dtype_single.bit_length
        return tuple(
            self._dtype_single.unpack(b[i * self._dtype_single.bit_length : (i + 1) * self._dtype_single.bit_length])
            for i in range(items)
        )

    @override
    @final
    def __str__(self) -> str:
        items_str = "" if self._items.is_none() else f" {self._items}"
        return f"[{self._dtype_single};{items_str}]"

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
    def _get_bit_length(self) -> int | None:
        if self._dtype_single.bit_length is not None and self._items.has_const_value and self._items.const_value is not None:
            return self._dtype_single.bit_length * self._items.const_value
        return None

    @override
    @final
    def has_fixed_size(self) -> bool:
        return self._dtype_single.has_fixed_size() and self._items.has_const_value and self._items.const_value is not None

    @override
    @final
    def has_dynamic_size(self) -> bool:
        return self._dtype_single._size.is_none() or self._items.is_none()

    @override
    @final
    def evaluate(self, **kwargs) -> Self:
        if self._dtype_single._size.has_const_value and self._items.has_const_value:
            return self
        size = self._dtype_single.evaluate(**kwargs).size
        items = self._items.evaluate(**kwargs)
        return DtypeArray.from_params(self._dtype_single.kind, size, items, self._dtype_single.endianness)

    @property
    def size(self) -> Expression:
        """The size of the data type as an Expression.

        This is the number used immediately after the data type kind in the dtype string.
        For example ``'[u10; 5]'`` has a size of 10.

        See also :attr:`bit_length`.

        """
        return self._dtype_single.size

    @property
    def items(self) -> Expression | None | Any:
        """The number of items in the data type as an Expression.

        For example ``'[u10; 5]'`` has 5 items.

        An items equal to 0 means it's an array data type but with items currently unset, while
        if items is None it is open ended and will consume as many items as possible.

        If the number of items is an `Expression` rather than a constant value then the Expression will be returned.

        """
        if self._items.is_none():
            return None
        if self._items.has_const_value:
            return self._items.const_value
        return self._items


class DtypeTuple(Dtype):
    """A data type class, representing a tuple of others.

    DtypeTuple instances are immutable. They are often created implicitly elsewhere via a token string.

    >>> a = Dtype('[u12, u8, bool]')
    >>> b = DtypeTuple.from_params(['u12', 'u8', 'bool'])

    """

    _dtypes: list[Dtype]
    _bit_length: int | None # The total length in bits possible excluding any dynamic size dtype, if known
    _dynamic_index: int | None  # The index of a dynamic size dtype in the tuple, or None

    @override
    def info(self) -> str:
        return f"tuple of {', '.join(dtype.info() for dtype in self._dtypes)}"

    def __new__(cls, s: str) -> Self:
        return cls.from_string(s)

    @classmethod
    def from_params(cls, dtypes: Sequence[Dtype | str]) -> Self:
        x = super().__new__(cls)
        x._dynamic_index = None
        bit_length: int | None = 0
        x._dtypes = []
        for i, d in enumerate(dtypes):
            dtype = d if isinstance(d, Dtype) else Dtype.from_string(d)
            if dtype.has_dynamic_size():
                if x._dynamic_index is not None:
                    raise ValueError(f"Cannot have more than one dtype with a dynamic size in a tuple. Found '{dtype}' at index {i} and '{x._dtypes[x._dynamic_index]}' at index {x._dynamic_index}.")
                x._dynamic_index = i
            else:
                if bit_length is not None:
                    if dtype.bit_length is None:
                        bit_length = None
                    else:
                        bit_length += dtype.bit_length
            x._dtypes.append(dtype)
        x._bit_length = bit_length
        return x

    @override
    @final
    def pack(self, values: Sequence[Any]) -> bitformat.Bits:
        if len(values) != self.items:
            raise ValueError(f"Expected {self.items} values, but got {len(values)}.")
        return bitformat.Bits.from_joined(dtype.pack(value) for dtype, value in zip(self._dtypes, values))

    @override
    @final
    def unpack(self, b: bitformat.Bits | str | Iterable[Any] | bytearray | bytes | memoryview, /) -> tuple[tuple[Any] | Any]:
        """Unpack a Bits to find its value.

        The b parameter should be a Bits of the appropriate length, or an object that can be converted to a Bits.

        """
        if self._bit_length is None:
            raise ValueError(f"{self!r} doesn't have a well defined size, so cannot be unpacked. Perhaps try parse() instead?")
        b = bitformat.Bits._from_any(b)

        if self._bit_length > len(b):
            if self._dynamic_index is not None:
                raise ValueError(f"{self!r} is at least {self.bit_length} bits long, but only got {len(b)} bits to unpack.")
            else:
                raise ValueError(f"{self!r} is {self.bit_length} bits long, but only got {len(b)} bits to unpack.")
        vals = []
        pos = 0
        for i, dtype in enumerate(self._dtypes):
            if i == self._dynamic_index:
                dynamic_length = len(b) - self._bit_length
                vals.append(dtype.unpack(b[pos : pos + dynamic_length]))
                pos += dynamic_length
            else:
                x = dtype.unpack(b[pos : pos + dtype.bit_length])
                if x is not None:  # Padding could unpack as None
                    vals.append(x)
                pos += dtype.bit_length
        return tuple(vals)

    @override
    @final
    def _get_bit_length(self) -> int | None:
        if self._dynamic_index is None:
            return self._bit_length
        return None

    @override
    @final
    def has_fixed_size(self) -> bool:
        return all(dtype.has_fixed_size() for dtype in self._dtypes)

    @override
    @final
    def has_dynamic_size(self) -> bool:
        return self._dynamic_index is not None

    @override
    @final
    def evaluate(self, **kwargs) -> Self:
        if all(dtype.has_fixed_size() for dtype in self._dtypes):
            return self
        dtypes = [dtype.evaluate(**kwargs) for dtype in self._dtypes]
        return DtypeTuple.from_params(dtypes)

    @property
    def items(self) -> int:
        """The number of dtypes in the dtype tuple.
        """
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

    def __init__(self, kind: DtypeKind, description: str, short_description: str, set_fn: Callable, get_fn: Callable,
                 return_type: Any = Any, is_signed: bool = False, bitlength2chars_fn=None,
                 allowed_sizes: tuple[int, ...] = tuple(), bits_per_character: int | None = None,
                 endianness_variants: bool = False):
        self.kind = kind
        self.description = description
        self.short_description = short_description
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
                        raise ValueError(f"'{self.kind}' dtypes must have a size of {self.allowed_sizes.values[0]}, but received a size of {len(bs)}.")
                    else:
                        raise ValueError(f"'{self.kind}' dtypes must have a size in {self.allowed_sizes}, but received a size of {len(bs)}.")
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
        if size.has_const_value and size.const_value is not None and self.allowed_sizes:
            if size.const_value == 0:
                if self.allowed_sizes.only_one_value():
                    size = Expression.from_int(self.allowed_sizes.values[0])
            else:
                if size.const_value not in self.allowed_sizes:
                    if self.allowed_sizes.only_one_value():
                        raise ValueError(f"A size of {size} was supplied for the '{self.kind}' dtype, but its "
                                         f"only allowed size is {self.allowed_sizes.values[0]}.")
                    else:
                        raise ValueError(f"A size of {size} was supplied for the '{self.kind}' dtype which "
                                         f"is not one of its possible sizes. Must be one of {self.allowed_sizes}.")
        if endianness is not Endianness.UNSPECIFIED:
            if not self.endianness_variants:
                raise ValueError(f"The '{self.kind}' dtype does not support endianness variants, but '{endianness.value}' was specified.")
            if size.evaluate() is not None and size.evaluate() % 8 != 0:
                raise ValueError(f"Endianness can only be specified for whole-byte dtypes, but '{self.kind}' has a size of {size} bits.")
        return size, endianness

    def get_single_dtype(self, size: Expression, endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeSingle:
        size, endianness = self.sanitize(size, endianness)
        d = DtypeSingle._create(self, size, endianness)
        return d

    def get_array_dtype(self, size: Expression, items: Expression, endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeArray:
        size, endianness = self.sanitize(size, endianness)
        d = DtypeArray._create(self, size, items, endianness)
        if size.has_const_value and size.const_value is None:
            raise ValueError(f"Array dtypes must have a size specified. Got '{d}'. "
                             f"Note that the number of items in the array dtype can be unknown or zero, but the dtype of each item must have a known size.")
        return d

    def __repr__(self) -> str:
        s = [f"{self.__class__.__name__}(kind='{self.kind}'",
             f"description='{self.description}'",
             f"short_description='{self.short_description}'",
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
    kind_to_def: dict[DtypeKind, DtypeDefinition] = {}

    def __new__(cls) -> Register:
        # Singleton. Only one Register instance can ever exist.
        if cls._instance is None:
            cls._instance = super(Register, cls).__new__(cls)
        return cls._instance

    @classmethod
    def add_dtype(cls, definition: DtypeDefinition):
        kind = definition.kind
        cls.kind_to_def[kind] = definition
        setattr(bitformat.Bits, kind.value, property(fget=definition.get_fn,
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

            for modifier, fget, desc in [("_le", fget_le, "little-endian"),
                                         ("_be", fget_be, "big-endian"),
                                         ("_ne", fget_ne, f"native-endian (i.e. {byteorder}-endian)")]:
                doc = f"The Bits as {definition.description} in {desc} byte order. Read only."
                setattr(bitformat.Bits, kind.value + modifier, property(fget=fget, doc=doc))

    @classmethod
    # @functools.lru_cache(CACHE_SIZE)
    def get_single_dtype(cls, kind: DtypeKind, size: Expression | int | None,
                         endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeSingle:
        definition = cls.kind_to_def[kind]
        if size is None:
            size = Expression.from_none()
        elif isinstance(size, int):
            size = Expression.from_int(size)
        return definition.get_single_dtype(size, endianness)

    @classmethod
    # @functools.lru_cache(CACHE_SIZE)
    def get_array_dtype(cls, kind: DtypeKind, size: Expression | int | None, items: Expression | int | None,
                        endianness: Endianness = Endianness.UNSPECIFIED) -> DtypeArray:
        definition = cls.kind_to_def[kind]
        if size is None:
            size = Expression.from_none()
        elif isinstance(size, int):
            size = Expression.from_int(size)
        if items is None:
            items = Expression.from_none()
        elif isinstance(items, int):
            items = Expression.from_int(items)
        return definition.get_array_dtype(size, items, endianness)

    def __repr__(self) -> str:
        s = [
            f"{'key':<12}:{'kind':^12}{'signed':^8}{'allowed_lengths':^16}{'bits_per_character':^12}{'return_type':<13}"
        ]
        s.append("-" * 72)
        for key in self.kind_to_def:
            m = self.kind_to_def[key]
            allowed = "" if not m.allowed_sizes else m.allowed_sizes
            ret = "None" if m.return_type is None else m.return_type.__name__
            s.append(
                f"{key:<12}:{m.kind:>12}{m.is_signed:^8}{allowed!s:^16}{m.bits_per_character:^12}{ret:<13} # {m.description}"
            )
        return "\n".join(s)
