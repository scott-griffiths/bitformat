from __future__ import annotations

import functools
from typing import Any, Callable
import inspect
import bitformat
from bitformat import _utils

__all__ = ['Dtype', 'DtypeDefinition', 'Register', 'dtype_register']

CACHE_SIZE = 256


class Dtype:
    """A data type class, representing a concrete interpretation of binary data.

    Dtype instances are immutable. They are often created implicitly elsewhere via a token string.

    >>> u12 = Dtype('uint', 12)
    >>> float16 = Dtype('float16')

    """

    _name: str
    _read_fn: Callable
    _set_fn: Callable
    _get_fn: Callable
    _return_type: Any
    _is_signed: bool
    _set_fn_needs_length: bool
    _item_size: int
    _multiplier: int
    _items: int | None

    def __new__(cls, name: str, /, length: int = 0, items: int | None = None) -> Dtype:
        x = dtype_register.get_dtype(name, length, items)
        return x

    @classmethod
    def from_string(cls, token: str, /) -> Dtype:
        token = ''.join(token.split())  # Remove whitespace
        if token and token[0] == '[':
            x = cls._new_from_array_token(token)
            return x
        else:
            x = cls._new_from_token(token)
            return x

    @property
    def name(self) -> str:
        """A string giving the name of the data type."""
        return self._name

    @property
    def length(self) -> int:
        """The length of the data type in units of bits_per_item."""
        return self._item_size // self._multiplier

    @property
    def item_size(self) -> int:
        """The number of bits needed to represent a single element of the data type."""
        return self._item_size

    @property
    def items(self) -> int | None:
        """The number of items in the data type. Will be None unless it's an array."""
        return self._items

    @property
    def multiplier(self) -> int:
        """The number of bits for each unit of length. Usually 1, but equals 8 for bytes type."""
        return self._multiplier

    @property
    def total_bitlength(self) -> int:
        if self._items is None:
            return self._item_size
        return self._item_size * self._items

    @property
    def return_type(self) -> Any:
        """The type of the value returned by the parse method, such as int, float or str."""
        return self._return_type

    @property
    def is_signed(self) -> bool:
        """If True then the data type represents a signed quantity."""
        return self._is_signed

    @property
    def set_fn(self) -> Callable | None:
        """A function to set the value of the data type."""
        return self._set_fn

    @property
    def get_fn(self) -> Callable:
        """A function to get the value of the data type."""
        return self._get_fn

    @property
    def read_fn(self) -> Callable:
        """A function to read the value of the data type."""
        return self._read_fn

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def _new_from_token(cls, token: str) -> Dtype:
        d = dtype_register.get_dtype(*_utils.parse_name_length_token(token))
        return d

    @classmethod
    def _new_from_array_token(cls, token: str) -> Dtype:
        if token[-1] == ']':
            p = token.find(';')
            if p != -1:
                items = int(token[p + 1:-1])
                d = dtype_register.get_array_dtype(*_utils.parse_name_length_token(token[1:p]), items)
                return d
        raise ValueError(f"Array tokens should be of the form '[dtype; items]'. Got '{token}'.")

    def __hash__(self) -> int:
        return hash((self._name, self._item_size))

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def _create(cls, definition: DtypeDefinition, length: int | None, items: int | None) -> Dtype:
        x = super().__new__(cls)
        x._name = definition.name
        x._items = items
        x._multiplier = definition.multiplier
        x._item_size = length * x._multiplier
        x._set_fn_needs_length = definition.set_fn_needs_length
        if dtype_register.names[x._name].allowed_lengths.only_one_value():
            x._read_fn = definition.read_fn
        else:
            x._read_fn = functools.partial(definition.read_fn, length=x._item_size)
        if definition.set_fn is None:
            x._set_fn = None
        else:
            if x._set_fn_needs_length:
                x._set_fn = functools.partial(definition.set_fn, length=x._item_size)
            else:
                x._set_fn = definition.set_fn
        x._get_fn = definition.get_fn
        x._return_type = definition.return_type
        x._is_signed = definition.is_signed
        return x

    def pack(self, value: Any, /) -> bitformat.Bits:
        """Create and return a new Bits from a value.

        The value parameter should be of a type appropriate to the dtype.
        """
        b = bitformat.Bits()
        if self._items is None:
            # Single item to pack
            self._set_fn(b, value)
            if self.item_size != 0 and len(b) != self.item_size:
                raise ValueError(f"Dtype has a length of {self.item_size} bits, but value '{value}' has {len(b)} bits.")
            return b
        if len(value) != self._items:
            raise ValueError(f"Expected {self._items} items, but got {len(value)}.")
        for v in value:
            item = bitformat.Bits()
            self._set_fn(item, v)
            b += item  # TODO: Horrible performance.
        return b

    def unpack(self, b: BitsType, /) -> Any:
        """Unpack a Bits to find its value.

        The b parameter should be a Bits of the appropriate length, or an object that can be converted to a Bits.

        """
        b = bitformat.Bits._create_from_bitstype(b)
        if self._items is None:
            if self._item_size == 0:
                return self._get_fn(b)
            else:
                return self._get_fn(b[0:self._item_size])
        return [self._get_fn(b[i * self._item_size:(i + 1) * self._item_size]) for i in range(self.items)]

    def __str__(self) -> str:
        hide_length = dtype_register.names[self._name].allowed_lengths.only_one_value() or self.length == 0
        length_str = '' if hide_length else str(self.length)
        if self._items is None:
            return f"{self._name}{length_str}"
        return f"[{self._name}{length_str}; {self._items}]"

    def __repr__(self) -> str:
        hide_length = dtype_register.names[self._name].allowed_lengths.only_one_value() or self.length == 0
        length_str = '' if hide_length else ', ' + str(self.length)
        if self._items is None:
            return f"{self.__class__.__name__}('{self._name}'{length_str})"
        return f"{self.__class__.__name__}('{self._name}'{length_str}, {self._items})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Dtype):
            return self._name == other._name and self._item_size == other._item_size and self._items == other._items
        return False


class AllowedLengths:
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

    def __init__(self, name: str, set_fn, get_fn, return_type: Any = Any, is_signed: bool = False, bitlength2chars_fn=None,
                 allowed_lengths: tuple[int, ...] = tuple(), multiplier: int = 1, description: str = ''):

        # Consistency checks
        if int(multiplier) != multiplier or multiplier <= 0:
            raise ValueError("multiplier must be an positive integer")

        self.name = name
        self.description = description
        self.return_type = return_type
        self.is_signed = is_signed
        self.allowed_lengths = AllowedLengths(allowed_lengths)

        self.multiplier = multiplier

        # Can work out if set_fn needs length based on its signature.
        self.set_fn_needs_length = set_fn is not None and 'length' in inspect.signature(set_fn).parameters
        self.set_fn = set_fn

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

        # Create a reading function from the get_fn.
        if self.allowed_lengths.only_one_value():
            def read_fn(bs, start: int):
                return self.get_fn(bs[start:start + self.allowed_lengths.values[0]])
        else:
            def read_fn(bs, start: int, length: int):
                if len(bs) < start + length:
                    raise ValueError(f"Needed a length of at least {length} bits, but only {len(bs) - start} bits were available.")
                return self.get_fn(bs[start:start + length])
        self.read_fn = read_fn

        self.bitlength2chars_fn = bitlength2chars_fn

    def get_dtype(self, length: int = 0, items: int | None = None) -> Dtype:
        if self.allowed_lengths:
            if length == 0:
                if self.allowed_lengths.only_one_value():
                    length = self.allowed_lengths.values[0]
            else:
                if length not in self.allowed_lengths:
                    if self.allowed_lengths.only_one_value():
                        raise ValueError(f"A length of {length} was supplied for the '{self.name}' dtype, but its only allowed length is {self.allowed_lengths.values[0]}.")
                    else:
                        raise ValueError(f"A length of {length} was supplied for the '{self.name}' dtype which is not one of its possible lengths (must be one of {self.allowed_lengths}).")
        d = Dtype._create(self, length, items)
        return d

    def get_array_dtype(self, length: int = 0, items: int = 0) -> Dtype:
        d = self.get_dtype(length)
        d = Dtype(d.name, d.length, items)
        return d

    def __repr__(self) -> str:
        s = f"{self.__class__.__name__}(name='{self.name}', description='{self.description}', return_type={self.return_type.__name__}, "
        s += f"is_signed={self.is_signed}, set_fn_needs_length={self.set_fn_needs_length}, allowed_lengths={self.allowed_lengths!s}, multiplier={self.multiplier})"
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
    def add_dtype(cls, definition: DtypeDefinition):
        cls.names[definition.name] = definition
        if definition.get_fn is not None:
            setattr(bitformat._bits.Bits, definition.name,
                    property(fget=definition.get_fn, doc=f"The Bits as {definition.description}. Read only."))

    @classmethod
    def add_dtype_alias(cls, name: str, alias: str):
        cls.names[alias] = cls.names[name]
        definition = cls.names[alias]
        if definition.get_fn is not None:
            setattr(bitformat._bits.Bits, alias,
                    property(fget=definition.get_fn, doc=f"An alias for '{name}'. Read only."))

    @classmethod
    def get_dtype(cls, name: str, length: int | None, items: int | None = None) -> Dtype:
        try:
            definition = cls.names[name]
        except KeyError:
            raise ValueError(f"Unknown Dtype name '{name}'. Names available: {list(cls.names.keys())}.")
        else:
            return definition.get_dtype(length, items)

    @classmethod
    def get_array_dtype(cls, name: str, length: int | None, items: int) -> Dtype:
        try:
            definition = cls.names[name]
        except KeyError:
            raise ValueError(f"Unknown Dtype name '{name}'. Names available: {list(cls.names.keys())}.")
        else:
            d = definition.get_array_dtype(length, items)
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
