from __future__ import annotations

import functools
from typing import Any, Callable, Iterable
import inspect
import bitformat
from bitformat import _utils
from ._common import Expression, Endianness, byteorder


__all__ = ['Dtype', 'DtypeDefinition', 'Register', 'dtype_register']

CACHE_SIZE = 256


class Dtype:
    """A data type class, representing a concrete interpretation of binary data.

    Dtype instances are immutable. They are often created implicitly elsewhere via a token string.

    >>> u12 = Dtype('u12')
    >>> float16 = Dtype('float16')

    """

    _name: str
    _create_fn: Callable
    _get_fn: Callable
    _return_type: Any
    _is_signed: bool
    _item_size: int
    _multiplier: int
    _items: int | None
    _endianness: Endianness

    def __new__(cls, token: str, /) -> Dtype:
        return cls.from_string(token)

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def from_parameters(cls, name: str, length: int = 0, items: int | None = None, endianness: str = '') -> Dtype:
        """Create a new Dtype from its name, length and items.

        It's usually clearer to use the Dtype constructor directly with a dtype str, but
        this builder will be more efficient and is used internally to avoid str parsing.

        """
        endianness = Endianness(endianness)
        x = dtype_register.get_dtype(name, length, items, endianness)
        return x

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def from_string(cls, token: str, /) -> Dtype:
        """Create a new Dtype from a token string.

        The token string examples:

        ``'u12'``: An unsigned 12-bit integer.
        ``'bytes'``: A ``bytes`` object with no explicit length.
        ``'[i6; 5]'``: An array of length 5 containing signed 6-bit integers.

        As a shortcut the ``Dtype`` constructor can be used directly with a token string.

        ``Dtype(s)`` is equivalent to ``Dtype.from_string(s)``.

        """
        token = ''.join(token.split())  # Remove whitespace
        if token.startswith('[') and token.endswith(']'):
            if (p := token.find(';')) == -1:
                raise ValueError(f"Array Dtype strings should be of the form '[dtype; items]'. Got '{token}'.")
            t = token[p + 1: -1]
            items = int(t) if t else 0
            name, length = _utils.parse_name_length_token(token[1:p])
            name, modifier = _utils.parse_name_to_name_and_modifier(name)
            endianness = Endianness(modifier)
            return dtype_register.get_array_dtype(name, length, items, endianness)
        else:
            name, length = _utils.parse_name_length_token(token)
            name, modifier = _utils.parse_name_to_name_and_modifier(name)
            endianness = Endianness(modifier)
            return dtype_register.get_dtype(name, length, None, endianness)

    @property
    def name(self) -> str:
        """A string giving the name of the data type."""
        return self._name

    @property
    def endianness(self) -> Endianness:
        """The endianness of the data type."""
        return self._endianness

    @property
    def length(self) -> int:
        """The length of the data type in units of the multiplier.

        A length of 0 means the length is currently unset.

        """
        return self._item_size // self._multiplier

    @property
    def item_size(self) -> int:
        """The number of bits needed to represent a single element of the data type."""
        return self._item_size

    @property
    def items(self) -> int | None:
        """The number of items in the data type. Will be None unless it's an array.

        An items equal to 0 means it's an array data type but with items currently unset.

        """
        return self._items

    @property
    def multiplier(self) -> int:
        """The number of bits for each unit of length. Usually 1, but equals 8 for bytes type."""
        return self._multiplier

    @property
    def return_type(self) -> Any:
        """The type of the value returned by the parse method, such as int, float or str."""
        return self._return_type

    @property
    def is_signed(self) -> bool:
        """If True then the data type represents a signed quantity."""
        return self._is_signed

    def __hash__(self) -> int:
        return hash((self._name, self._item_size))

    def __len__(self) -> int:
        """The length of the data type in bits.

        Raises ValueError if either the length of the items is not set (equals 0).

        """
        if self._item_size == 0:
            raise ValueError(f"Cannot return the length of the Dtype '{self}' because it has no length set.")
        if self._items is None:
            return self._item_size
        if self._items == 0:
            raise ValueError(f"Cannot return the length of the Dtype '{self}' because it has no number of items set.")
        return self._item_size * self._items

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def _create(cls, definition: DtypeDefinition, length: int | None, items: int | None,
                endianness: Endianness = Endianness.UNSPECIFIED) -> Dtype:
        x = super().__new__(cls)
        x._name = definition.name
        x._items = items
        x._multiplier = definition.multiplier
        x._item_size = length * x._multiplier
        little_endian: bool = endianness == Endianness.LITTLE or (endianness == Endianness.NATIVE and bitformat.byteorder == 'little')
        x._endianness = endianness
        x._get_fn = (lambda b: definition.get_fn(b.byteswap())) if little_endian else definition.get_fn
        if definition.set_fn is None:
            x._create_fn = None
        else:
            if 'length' in inspect.signature(definition.set_fn).parameters:
                set_fn = functools.partial(definition.set_fn, length=x._item_size)
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
                return b.byteswap()
            x._create_fn = create_bits_le if little_endian else create_bits

        x._return_type = definition.return_type if items is None else tuple
        x._is_signed = definition.is_signed
        return x

    def pack(self, value: Any, /) -> bitformat.Bits:
        """Create and return a new Bits from a value.

        The value parameter should be of a type appropriate to the data type.

        """
        if self._items is None:
            # Single item to pack
            b = self._create_fn(value)
            if self.item_size != 0 and len(b) != self.item_size:
                raise ValueError(f"Dtype has a length of {self.item_size} bits, but value '{value}' has {len(b)} bits.")
            return b
        if isinstance(value, bitformat.Bits):
            if len(value) != len(self):
                raise ValueError(f"Expected {len(self)} bits, but got {len(value)} bits.")
            return value
        if len(value) != self._items:
            raise ValueError(f"Expected {self._items} items, but got {len(value)}.")
        return bitformat.Bits.join(self._create_fn(v) for v in value)

    def unpack(self, b: bitformat.Bits | str | Iterable[Any] | bytearray | bytes | memoryview, /) -> Any | tuple[Any]:
        """Unpack a Bits to find its value.

        The b parameter should be a Bits of the appropriate length, or an object that can be converted to a Bits.

        """
        b = bitformat.Bits.from_auto(b)
        if self._items is None:
            if self._item_size == 0:
                return self._get_fn(b)
            else:
                return self._get_fn(b[0:self._item_size])
        return tuple(self._get_fn(b[i * self._item_size:(i + 1) * self._item_size]) for i in range(self.items))

    def __str__(self) -> str:
        hide_length = dtype_register.names[self._name].allowed_lengths.only_one_value() or self.length == 0
        length_str = '' if hide_length else str(self.length)
        if self._items is None:
            return f"{self._name}{self._endianness.value}{length_str}"
        items_str = '' if self._items == 0 else f" {self._items}"
        return f"[{self._name}{self._endianness.value}{length_str};{items_str}]"

    def __repr__(self) -> str:
        hide_length = dtype_register.names[self._name].allowed_lengths.only_one_value() or self.length == 0
        length_str = '' if hide_length else str(self.length)
        if self._items is None:
            return f"{self.__class__.__name__}('{self._name}{self._endianness.value}{length_str}')"
        items_str = '' if self._items == 0 else f" {self._items}"
        return f"{self.__class__.__name__}('[{self._name}{self._endianness.value}{length_str};{items_str}]')"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Dtype):
            return (self._name == other._name and
                    self._item_size == other._item_size and
                    self._items == other._items and
                    self._endianness == other._endianness)
        return False


class AllowedLengths:
    """Used to specify either concrete values or ranges of values that are allowed lengths for data types."""
    def __init__(self, value: tuple[int, ...] = tuple()) -> None:
        if len(value) >= 3 and value[-1] is Ellipsis:
            step = value[1] - value[0]
            for i in range(1, len(value) - 1):
                if value[i] - value[i - 1] != step:
                    raise ValueError(f"Allowed length tuples must be equally spaced when final element is Ellipsis, but got {value}.")
            self.values = (value[0], value[1], Ellipsis)
        else:
            self.values = value

    def __str__(self) -> str:
        if self.values and self.values[-1] is Ellipsis:
            return f"({self.values[0]}, {self.values[1]}, ...)"
        return str(self.values)

    def __contains__(self, other: Any) -> bool:
        if not self.values:
            return True
        if self.values[-1] is Ellipsis:
            return (other - self.values[0]) % (self.values[1] - self.values[0]) == 0
        return other in self.values

    def only_one_value(self) -> bool:
        return self.values and len(self.values) == 1


class DtypeDefinition:
    """Represents a class of dtypes, such as ``bytes`` or ``f``, rather than a concrete dtype such as ``f32``.
    """

    def __init__(self, name: str, set_fn: Callable, get_fn: Callable, return_type: Any = Any, is_signed: bool = False, bitlength2chars_fn=None,
                 allowed_lengths: tuple[int, ...] = tuple(), multiplier: int = 1, endianness_variants: bool = False, description: str = ''):

        # Consistency checks
        if int(multiplier) != multiplier or multiplier <= 0:
            raise ValueError("multiplier must be an integer >= 1.")

        self.name = name
        self.description = description
        self.return_type = return_type
        self.is_signed = is_signed
        self.allowed_lengths = AllowedLengths(allowed_lengths)
        self.multiplier = multiplier
        self.set_fn = set_fn
        self.endianness_variants = endianness_variants

        if self.allowed_lengths.values:
            def allowed_length_checked_get_fn(bs):
                if len(bs) not in self.allowed_lengths:
                    if self.allowed_lengths.only_one_value():
                        raise ValueError(f"'{self.name}' dtypes must have a length of {self.allowed_lengths.values[0]}, but received a length of {len(bs)}.")
                    else:
                        raise ValueError(f"'{self.name}' dtypes must have a length in {self.allowed_lengths}, but received a length of {len(bs)}.")
                return get_fn(bs)
            self.get_fn = allowed_length_checked_get_fn  # Interpret everything and check the length
        else:
            self.get_fn = get_fn  # Interpret everything
        self.bitlength2chars_fn = bitlength2chars_fn

    def get_dtype(self, length: int = 0, items: int | None = None, endianness: Endianness = Endianness.UNSPECIFIED) -> Dtype:
        if self.allowed_lengths:
            if length == 0:
                if self.allowed_lengths.only_one_value():
                    length = self.allowed_lengths.values[0]
            else:
                if length not in self.allowed_lengths:
                    if self.allowed_lengths.only_one_value():
                        raise ValueError(f"A length of {length} was supplied for the '{self.name}' dtype, but its "
                                         f"only allowed length is {self.allowed_lengths.values[0]}.")
                    else:
                        raise ValueError(f"A length of {length} was supplied for the '{self.name}' dtype which "
                                         f"is not one of its possible lengths (must be one of {self.allowed_lengths}).")
        if endianness != Endianness.UNSPECIFIED:
            if not self.endianness_variants:
                raise ValueError(f"The '{self.name}' dtype does not support endianness variants, but '{endianness.value}' was specified.")
            if length % 8 != 0:
                raise ValueError(f"Endianness can only be specified for whole-byte dtypes, but '{self.name}' has a length of {length} bits.")
        d = Dtype._create(self, length, items, endianness)
        return d

    def get_array_dtype(self, length: int, items: int, endianness: Endianness = Endianness.UNSPECIFIED) -> Dtype:
        d = self.get_dtype(length)
        d = Dtype.from_parameters(d.name, d.length, items, endianness)
        return d

    def __repr__(self) -> str:
        s = (f"{self.__class__.__name__}(name='{self.name}', description='{self.description}',"
             f"return_type={self.return_type.__name__}, ")
        s += (f"is_signed={self.is_signed}, "
              f"allowed_lengths={self.allowed_lengths!s}, multiplier={self.multiplier})")
        return s


class Register:
    """A singleton class that holds all the DtypeDefinitions. Not (yet) part of the public interface."""

    _instance: Register | None = None
    names: dict[str, DtypeDefinition] = {}

    def __new__(cls) -> Register:
        # Singleton. Only one Register instance can ever exist.
        if cls._instance is None:
            cls._instance = super(Register, cls).__new__(cls)
        return cls._instance

    @classmethod
    def add_dtype(cls, definition: DtypeDefinition, alias: str | None = None):
        names = [definition.name] if alias is None else [definition.name, alias]
        for name in names:
            cls.names[name] = definition
            if definition.get_fn is not None:
                setattr(bitformat._bits.Bits, name,
                        property(fget=definition.get_fn, doc=f"The Bits as {definition.description}. Read only."))
                if definition.endianness_variants:
                    def fget_be(b):
                        if len(b) % 8 != 0:
                            raise ValueError(f"Cannot use endianness modifer for non whole-byte data. Got length of {len(b)} bits.")
                        return definition.get_fn(b)
                    def fget_le(b):
                        if len(b) % 8 != 0:
                            raise ValueError(f"Cannot use endianness modifer for non whole-byte data. Got length of {len(b)} bits.")
                        return definition.get_fn(b.byteswap())
                    fget_ne = fget_le if byteorder == 'little' else fget_be
                    setattr(bitformat._bits.Bits, name + '_le',
                            property(fget=fget_le,
                                     doc=f"The Bits as {definition.description} in little-endian byte order. Read only."))
                    setattr(bitformat._bits.Bits, name + '_be',
                            property(fget=fget_be,
                                     doc=f"The Bits as {definition.description} in big-endian byte order. Read only."))
                    setattr(bitformat._bits.Bits, name + '_ne',
                            property(fget=fget_ne,
                                     doc=f"The Bits as {definition.description} in native-endian (i.e. {byteorder}-endian) byte order. Read only."))

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def get_dtype(cls, name: str, length: int | None, items: int | None = None,
                  endianness: Endianness = Endianness.UNSPECIFIED) -> Dtype:
        try:
            definition = cls.names[name]
        except KeyError:
            raise ValueError(f"Unknown Dtype name '{name}'. Names available: {list(cls.names.keys())}.")
        else:
            return definition.get_dtype(length, items, endianness)

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def get_array_dtype(cls, name: str, length: int, items: int,
                        endianness: Endianness = Endianness.UNSPECIFIED) -> Dtype:
        try:
            definition = cls.names[name]
        except KeyError:
            raise ValueError(f"Unknown Dtype name '{name}'. Names available: {list(cls.names.keys())}.")
        else:
            d = definition.get_array_dtype(length, items, endianness)
            return d

    @classmethod
    def __getitem__(cls, name: str) -> DtypeDefinition:
        return cls.names[name]

    @classmethod
    def __delitem__(cls, name: str) -> None:
        del cls.names[name]

    def __repr__(self) -> str:
        s = [f"{'key':<12}:{'name':^12}{'signed':^8}{'allowed_lengths':^16}{'multiplier':^12}{'return_type':<13}"]
        s.append('-' * 72)
        for key in self.names:
            m = self.names[key]
            allowed = '' if not m.allowed_lengths else m.allowed_lengths
            ret = 'None' if m.return_type is None else m.return_type.__name__
            s.append(f"{key:<12}:{m.name:>12}{m.is_signed:^8}{allowed!s:^16}{m.multiplier:^12}{ret:<13} # {m.description}")
        return '\n'.join(s)


dtype_register = Register()
"""
Initializes a singleton instance of the Register class.

This is used to maintain a centralized registry of data type definitions.
"""


class DtypeWithExpression:
    """Used internally. A Dtype that can contain an Expression instead of fixed values for length or items."""

    def __init__(self, s: str) -> None:
        self.name = ''
        self.items_expression = None
        self.length_expression = None
        token = ''.join(s.split())  # Remove whitespace
        if token.startswith('[') and token.endswith(']'):
            if (p := token.find(';')) == -1:
                raise ValueError(f"Array Dtype strings should be of the form '[dtype; items]'. Got '{token}'.")
            self.items_expression = Expression(token[p + 1: -1])
            self.name, length_str = _utils.parse_name_expression_token(token[1:p])
        else:
            self.name, length_str = _utils.parse_name_expression_token(token)
        self.length_expression = Expression(length_str)

            # return dtype_register.get_array_dtype(*_utils.parse_name_length_token(token[1:p]), items)
        # return dtype_register.get_dtype(*_utils.parse_name_length_token(token))

    def __str__(self) -> str:
        return "TODO"
        hide_length = dtype_register.names[self._name].allowed_lengths.only_one_value() or self.length == 0
        length_str = '' if hide_length else str(self.length)
        if self._items is None:
            return f"{self._name}{length_str}"
        items_str = '' if self._items == 0 else f" {self._items}"
        return f"[{self._name}{length_str};{items_str}]"

