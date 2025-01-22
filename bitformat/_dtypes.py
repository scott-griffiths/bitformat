from __future__ import annotations

import functools
from typing import Any, Callable, Iterable, Sequence, overload, Union
import inspect
import bitformat
from bitformat import _utils
from ._common import Expression, Endianness, byteorder

# Things that can be converted to Bits when a Bits type is needed
BitsType = Union["Bits", str, Iterable[Any], bytearray, bytes, memoryview]

__all__ = ["Dtype", "DtypeTuple", "DtypeDefinition", "Register", "DtypeWithExpression"]

CACHE_SIZE = 256


class Dtype:
    """A data type class, representing a concrete interpretation of binary data.

    Dtype instances are immutable. They are often created implicitly elsewhere via a token string.

    >>> u12 = Dtype('u12')
    >>> float16 = Dtype('f16')

    """

    _name: str
    _create_fn: Callable
    _get_fn: Callable
    _return_type: Any
    _is_signed: bool
    _bits_per_item: int
    _items: int
    _is_array: bool
    _size: int
    _endianness: Endianness
    _bits_per_character: int | None

    def __new__(cls, token: str, /) -> Dtype:
        return cls.from_string(token)

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def from_params(
        cls,
        name: str,
        size: int = 0,
        is_array: bool = False,
        items: int = 1,
        endianness: Endianness = Endianness.UNSPECIFIED,
    ) -> Dtype:
        """Create a new Dtype from its name, size and items.

        It's usually clearer to use the Dtype constructor directly with a dtype str, but
        this builder will be more efficient and is used internally to avoid string parsing.

        """
        if is_array:
            return Register().get_array_dtype(name, size, items, endianness)
        else:
            return Register().get_single_dtype(name, size, endianness)

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def from_string(cls, token: str, /) -> Dtype:
        """Create a new Dtype from a token string.

        Some token string examples:

        * ``'u12'``: An unsigned 12-bit integer.
        * ``'bytes'``: A ``bytes`` object with no explicit size.
        * ``'[i6; 5]'``: An array of 5 signed 6-bit integers.

        As a shortcut the ``Dtype`` constructor can be used directly with a token string.

        ``Dtype(s)`` is equivalent to ``Dtype.from_string(s)``.

        """
        token = "".join(token.split())  # Remove whitespace
        if token.startswith("[") and token.endswith("]"):
            if (p := token.find(";")) == -1:
                raise ValueError(
                    f"Array Dtype strings should be of the form '[dtype; items]' but can't find the ';'. Got '{token}'."
                )
            t = token[p + 1 : -1]
            items = int(t) if t else 0
            name, size = _utils.parse_name_size_token(token[1:p])
            name, modifier = _utils.parse_name_to_name_and_modifier(name)
            endianness = Endianness(modifier)
            return Register().get_array_dtype(name, size, items, endianness)
        else:
            try:
                name, size = _utils.parse_name_size_token(token)
            except ValueError as e:
                if "," in token:
                    raise ValueError(
                        f"Can't parse token '{token}' as a single 'name[length]'. Did you mean to use a DtypeTuple instead?"
                    )
                else:
                    raise e
            name, modifier = _utils.parse_name_to_name_and_modifier(name)
            endianness = Endianness(modifier)
            return Register().get_single_dtype(name, size, endianness)

    @property
    def name(self) -> str:
        """A string giving the name of the data type."""
        return self._name

    @property
    def endianness(self) -> Endianness:
        """The endianness of the data type."""
        return self._endianness

    @property
    def bits_per_item(self) -> int:
        """The number of bits needed to represent a single item of the underlying data type.

        .. code-block:: pycon

            >>> Dtype('f64').bits_per_item
            64
            >>> Dtype('hex10').bits_per_item
            40
            >>> Dtype('[u5; 1001]').bits_per_item
            5

        See also :attr:`bit_length` and :attr:`size`.

        """
        return self._bits_per_item

    @property
    def items(self) -> int:
        """The number of items in the data type. Will be 1 unless it's an array.

        An items equal to 0 means it's an array data type but with items currently unset.

        """
        return self._items

    @property
    def is_array(self) -> bool:
        """Returns bool indicating if the data type represents an array of items.

        .. code-block:: pycon

            >>> Dtype('u32').is_array
            False
            >>> Dtype('[u32; 3]').is_array
            True
        """
        return self._is_array

    @property
    def size(self) -> int:
        """The size of the data type.

        This is the number used immediately after the data type name in a dtype string.
        For example, each of ``'u10'``, ``'hex10'`` and ``'[i10; 3]'`` have a size of 10 even
        though they have bitlengths of 10, 40 and 30 respectively.

        See also :attr:`bits_per_item` and :attr:`bit_length`.

        """
        return self._size

    @property
    def bit_length(self) -> int:
        """The total length of the data type in bits.

        The ``bit_length`` for any dtype equals its :attr:`bits_per_item` multiplied by its :attr:`items`.

        .. code-block:: pycon

            >>> Dtype('u12').bit_length
            12
            >>> Dtype('[u12; 5]').bit_length
            60
            >>> Dtype('hex5').bit_length
            20

        See also :attr:`bits_per_item` and :attr:`size`.

        """
        return self._bits_per_item * self._items

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

    def __hash__(self) -> int:
        return hash(
            (self._name, self._bits_per_item, self._items, self.is_array)
        )

    def __len__(self):
        raise TypeError(
            "'Dtype' has no len() method. Use 'size', 'items' or 'bit_length' properties instead."
        )

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def _create(
        cls,
        definition: DtypeDefinition,
        size: int,
        is_array: bool = False,
        items: int = 1,
        endianness: Endianness = Endianness.UNSPECIFIED,
    ) -> Dtype:
        x = super().__new__(cls)
        x._name = definition.name
        x._is_array = is_array
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
            (lambda b: definition.get_fn(b.byteswap()))
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
            return b.byteswap()

        x._create_fn = create_bits_le if little_endian else create_bits

        x._return_type = tuple if is_array else definition.return_type
        x._is_signed = definition.is_signed
        return x

    def pack(self, value: Any, /) -> bitformat.Bits:
        """Create and return a new Bits from a value.

        The value parameter should be of a type appropriate to the data type.

        """
        if not self._is_array:
            # Single item to pack
            b = self._create_fn(value)
            if self.bits_per_item != 0 and len(b) != self.bits_per_item:
                raise ValueError(
                    f"Dtype '{self}' has a bit_length of {self.bits_per_item} bits, but value '{value}' has {len(b)} bits."
                )
            return b
        if isinstance(value, bitformat.Bits):
            if len(value) != self.bit_length:
                raise ValueError(
                    f"Expected {self.bit_length} bits, but got {len(value)} bits."
                )
            return value
        if len(value) != self._items:
            raise ValueError(f"Expected {self._items} items, but got {len(value)}.")
        return bitformat.Bits.from_joined(self._create_fn(v) for v in value)

    def unpack(self, b: BitsType, /) -> Any | tuple[Any]:
        """Unpack a Bits to find its value.

        The b parameter should be a Bits of the appropriate length, or an object that can be converted to a Bits.

        """
        b = bitformat.Bits._from_any(b)
        if self.bit_length > len(b):
            raise ValueError(
                f"{self!r} is {self.bit_length} bits long, but only got {len(b)} bits to unpack."
            )
        if not self._is_array:
            if self.bit_length == 0:
                # Try to unpack everything
                return self._get_fn(b)
            else:
                return self._get_fn(b[: self.bit_length])
        else:
            return tuple(
                self._get_fn(b[i * self._bits_per_item : (i + 1) * self._bits_per_item])
                for i in range(self.items)
            )

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
        if not self._is_array:
            return f"{self._name}{endianness}{size_str}"
        items_str = "" if self._items == 0 else f" {self._items}"
        return f"[{self._name}{self._endianness.value}{size_str};{items_str}]"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.__str__()}')"

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
        name: str,
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
                        raise ValueError(
                            f"'{self.name}' dtypes must have a size of {self.allowed_sizes.values[0]}, but received a size of {len(bs)}."
                        )
                    else:
                        raise ValueError(
                            f"'{self.name}' dtypes must have a size in {self.allowed_sizes}, but received a size of {len(bs)}."
                        )
                return get_fn(bs)

            self.get_fn = (
                allowed_size_checked_get_fn  # Interpret everything and check the size
            )
        else:
            self.get_fn = get_fn  # Interpret everything
        if bits_per_character is not None:
            if bitlength2chars_fn is not None:
                raise ValueError(
                    "You shouldn't specify both a bits_per_character and a bitlength2chars_fn."
                )

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
                            f"is not one of its possible sizes (must be one of {self.allowed_sizes})."
                        )
        if endianness != Endianness.UNSPECIFIED:
            if not self.endianness_variants:
                raise ValueError(
                    f"The '{self.name}' dtype does not support endianness variants, but '{endianness.value}' was specified."
                )
            if size % 8 != 0:
                raise ValueError(
                    f"Endianness can only be specified for whole-byte dtypes, but '{self.name}' has a size of {size} bits."
                )
        return size, endianness

    def get_single_dtype(
        self, size: int = 0, endianness: Endianness = Endianness.UNSPECIFIED
    ) -> Dtype:
        size, endianness = self.sanitize(size, endianness)
        d = Dtype._create(self, size, False, 1, endianness)
        return d

    def get_array_dtype(
        self, size: int, items: int, endianness: Endianness = Endianness.UNSPECIFIED
    ) -> Dtype:
        size, endianness = self.sanitize(size, endianness)
        d = Dtype._create(self, size, True, items, endianness)
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
    name_to_def: dict[str, DtypeDefinition] = {}

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
            name,
            property(
                fget=definition.get_fn,
                doc=f"The Bits as {definition.description}. Read only.",
            ),
        )
        if definition.endianness_variants:

            def fget_be(b):
                if len(b) % 8 != 0:
                    raise ValueError(
                        f"Cannot use endianness modifer for non whole-byte data. Got length of {len(b)} bits."
                    )
                return definition.get_fn(b)

            def fget_le(b):
                if len(b) % 8 != 0:
                    raise ValueError(
                        f"Cannot use endianness modifer for non whole-byte data. Got length of {len(b)} bits."
                    )
                return definition.get_fn(b.byteswap())

            fget_ne = fget_le if byteorder == "little" else fget_be
            setattr(
                bitformat.Bits,
                name + "_le",
                property(
                    fget=fget_le,
                    doc=f"The Bits as {definition.description} in little-endian byte order. Read only.",
                ),
            )
            setattr(
                bitformat.Bits,
                name + "_be",
                property(
                    fget=fget_be,
                    doc=f"The Bits as {definition.description} in big-endian byte order. Read only.",
                ),
            )
            setattr(
                bitformat.Bits,
                name + "_ne",
                property(
                    fget=fget_ne,
                    doc=f"The Bits as {definition.description} in native-endian (i.e. {byteorder}-endian) byte order. Read only.",
                ),
            )

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def get_single_dtype(
        cls,
        name: str,
        size: int | None,
        endianness: Endianness = Endianness.UNSPECIFIED,
    ) -> Dtype:
        try:
            definition = cls.name_to_def[name]
        except KeyError:
            aliases = {"int": "i", "uint": "u", "float": "f"}
            extra = f"Did you mean '{aliases[name]}'? " if name in aliases else ""
            raise ValueError(
                f"Unknown Dtype name '{name}'. {extra}Names available: {list(cls.name_to_def.keys())}."
            )
        else:
            return definition.get_single_dtype(size, endianness)

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def get_array_dtype(
        cls,
        name: str,
        size: int,
        items: int,
        endianness: Endianness = Endianness.UNSPECIFIED,
    ) -> Dtype:
        try:
            definition = cls.name_to_def[name]
        except KeyError:
            raise ValueError(
                f"Unknown Dtype name '{name}'. Names available: {list(cls.name_to_def.keys())}."
            )
        else:
            d = definition.get_array_dtype(size, items, endianness)
            return d

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


class DtypeWithExpression:
    """Used internally. A Dtype that can contain an Expression instead of fixed values for size or items."""

    items_expression: Expression | None
    size_expression: Expression | None
    base_dtype: Dtype

    def __init__(
        self,
        name: str,
        size: int | Expression,
        is_array: bool,
        items: int | Expression,
        endianness: Endianness = Endianness.UNSPECIFIED,
    ):
        if isinstance(size, Expression):
            self.size_expression = size
            size = 0
        else:
            self.size_expression = None
        if isinstance(items, Expression):
            self.items_expression = items
            items = 1
        else:
            self.items_expression = None
        self.base_dtype = Dtype.from_params(name, size, is_array, items, endianness)

    @classmethod
    def from_string(cls, token: str, /) -> DtypeWithExpression:
        x = cls.__new__(cls)
        p = token.find("{")
        if p == -1:
            x.base_dtype = Dtype.from_string(token)
            x.size_expression = x.items_expression = None
            return x
        token = "".join(token.split())  # Remove whitespace
        if token.startswith("[") and token.endswith("]"):
            if (p := token.find(";")) == -1:
                raise ValueError(
                    f"Array Dtype strings should be of the form '[dtype; items]'. Got '{token}'."
                )
            t = token[p + 1 : -1]
            try:
                items = int(t) if t else 0
                x.items_expression = None
            except ValueError:
                x.items_expression = Expression(t)
                items = 1
            name, size_str = _utils.parse_name_expression_token(token[1:p])
            try:
                size = int(size_str)
                x.size_expression = None
            except ValueError:
                x.size_expression = Expression(size_str)
                size = 0
            name, modifier = _utils.parse_name_to_name_and_modifier(name)
            endianness = Endianness(modifier)
            x.base_dtype = Register().get_array_dtype(name, size, items, endianness)
            return x
        else:
            name, size_str = _utils.parse_name_expression_token(token)
            try:
                size = int(size_str)
                x.size_expression = None
            except ValueError:
                x.size_expression = Expression(size_str)
                size = 0
            name, modifier = _utils.parse_name_to_name_and_modifier(name)
            endianness = Endianness(modifier)
            x.base_dtype = Register().get_single_dtype(name, size, endianness)
            return x

    def evaluate(self, vars_: dict[str, Any]) -> Dtype:
        if self.size_expression is None and self.items_expression is None:
            return self.base_dtype
        if not vars_:
            return self.base_dtype
        if self.base_dtype.is_array:
            name = self.base_dtype.name
            size = (
                self.size_expression.evaluate(vars_)
                if (self.size_expression and vars_)
                else self.base_dtype.size
            )
            items = (
                self.items_expression.evaluate(vars_)
                if (self.items_expression and vars_)
                else self.base_dtype.items
            )
            endianness = self.base_dtype.endianness
            return Register().get_array_dtype(name, size, items, endianness)
        else:
            name = self.base_dtype.name
            size = (
                self.size_expression.evaluate(vars_)
                if (self.size_expression and vars_)
                else self.base_dtype.size
            )
            endianness = self.base_dtype.endianness
            return Register().get_single_dtype(name, size, endianness)

    def __str__(self) -> str:
        hide_size = Register().name_to_def[
            self.base_dtype.name
        ].allowed_sizes.only_one_value() or (
            self.base_dtype.size == 0 and self.size_expression is None
        )
        size_str = (
            ""
            if hide_size
            else (
                self.size_expression
                if self.size_expression
                else str(self.base_dtype.size)
            )
        )
        if not self.base_dtype.is_array:
            return f"{self.base_dtype.name}{self.base_dtype.endianness.value}{size_str}"
        hide_items = self.base_dtype.items == 0 and self.items_expression is None
        items_str = (
            ""
            if hide_items
            else (
                self.items_expression
                if self.items_expression
                else str(self.base_dtype.items)
            )
        )
        return f"[{self.base_dtype.name}{self.base_dtype.endianness.value}{size_str}; {items_str}]"


class DtypeTuple:
    """A data type class, representing a tuple of concrete interpretations of binary data.

    DtypeTuple instances are immutable. They are often created implicitly elsewhere via a token string.

    >>> a = DtypeTuple('u12, u8, bool')
    >>> b = DtypeTuple.from_params(['u12', 'u8', 'bool'])

    """

    _dtypes: list[Dtype]
    _bit_length: int
    is_array: bool = False

    def __new__(cls, s: str) -> DtypeTuple:
        return cls.from_string(s)

    @classmethod
    def from_params(cls, dtypes: Sequence[Dtype | str]) -> DtypeTuple:
        x = super().__new__(cls)
        x._dtypes = []
        for d in dtypes:
            dtype = d if isinstance(d, Dtype) else Dtype.from_string(d)
            if dtype.bit_length == 0:
                raise ValueError(f"Can't create a DtypeTuple from dtype '{d}' as it has an unknown length.")
            x._dtypes.append(dtype)
        x._bit_length = sum(dtype.bit_length for dtype in x._dtypes)
        return x

    @classmethod
    def from_string(cls, s: str, /) -> DtypeTuple:
        tokens = [t.strip() for t in s.split(",")]
        dtypes = [Dtype.from_string(token) for token in tokens]
        return cls.from_params(dtypes)

    def pack(self, values: Sequence[Any]) -> bitformat.Bits:
        if len(values) != len(self):
            raise ValueError(f"Expected {len(self)} values, but got {len(values)}.")
        return bitformat.Bits.from_joined(
            dtype.pack(value) for dtype, value in zip(self._dtypes, values)
        )

    def unpack(
        self,
        b: bitformat.Bits | str | Iterable[Any] | bytearray | bytes | memoryview,
        /,
    ) -> tuple[tuple[Any] | Any]:
        """Unpack a Bits to find its value.

        The b parameter should be a Bits of the appropriate length, or an object that can be converted to a Bits.

        """
        b = bitformat.Bits._from_any(b)
        if self.bit_length > len(b):
            raise ValueError(
                f"{self!r} is {self.bit_length} bits long, but only got {len(b)} bits to unpack."
            )
        vals = []
        pos = 0
        for dtype in self:
            if dtype.name != "pad":
                vals.append(dtype.unpack(b[pos : pos + dtype.bit_length]))
            pos += dtype.bit_length
        return tuple(vals)

    def _getbitlength(self) -> int:
        return self._bit_length

    bit_length = property(
        _getbitlength, doc="The total length of all the dtypes in bits."
    )
    bits_per_item = bit_length  # You can't do an array-like DtypeTuple so this is the same as bit_length

    def __len__(self) -> int:
        return len(self._dtypes)

    def __eq__(self, other) -> bool:
        if isinstance(other, DtypeTuple):
            return self._dtypes == other._dtypes
        return False

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

    def __str__(self) -> str:
        return ", ".join(str(dtype) for dtype in self._dtypes)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{str(self)}')"
