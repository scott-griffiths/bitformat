from __future__ import annotations

import numbers
import random
import sys
import struct
import io
import functools
from ast import literal_eval
from collections import abc
from typing import Union, Iterable, Any, TextIO, overload, Iterator, Type
from bitformat._dtypes import Dtype, DtypeSingle, Register, DtypeTuple, DtypeArray
from bitformat._common import Colour, DtypeKind
from bitformat._options import Options
from bitformat.bit_rust import BitRust
from collections.abc import Sequence


__all__ = ["Bits", "BitsType"]

# Things that can be converted to Bits when a Bits type is needed
BitsType = Union["Bits", str, bytearray, bytes, memoryview]

# The size of various caches used to improve performance
CACHE_SIZE = 256


@functools.lru_cache(CACHE_SIZE)
def token_to_bitstore(token: str) -> BitRust:
    if token[0] != "0":
        dtype_str, value_str = token.split("=", 1)
        try:
            dtype = Dtype.from_string(dtype_str)
        except ValueError:
            raise ValueError(f"Can't parse token '{token}'. It should be in the form 'kind[length]=value' (e.g. "
                             "'u8 = 44') or a literal starting with '0b', '0o' or '0x'.")
        if isinstance(dtype, DtypeSingle) and dtype._definition.return_type not in (bool, bytes):
            return dtype.pack(value_str)._bitstore
        try:
            value = literal_eval(value_str)
        except ValueError:
            raise ValueError(f"Can't parse token '{token}'. The value '{value_str}' can't be converted to the appropriate type.")
        return dtype.pack(value)._bitstore

    if token.startswith("0x"):
        return BitRust.from_hex_checked(token)
    if token.startswith("0b"):
        return BitRust.from_bin_checked(token)
    if token.startswith("0o"):
        return BitRust.from_oct_checked(token)
    raise ValueError(f"Can't parse token '{token}'. Did you mean to prefix with '0x', '0b' or '0o'?")


@functools.lru_cache(CACHE_SIZE)
def str_to_bitstore(s: str) -> BitRust:
    s = "".join(s.split())  # Remove whitespace
    # Find all the commas, ignoring those in other structures.
    # This isn't a rigorous check - if brackets are mismatched it will be picked up later.
    tokens = []
    token_start = 0
    bracket_depth = 0
    for i, c in enumerate(s):
        if c == "," and bracket_depth == 0:
            tokens.append(s[token_start:i])
            token_start = i + 1
        elif c in "([{":
            bracket_depth += 1
        elif c in ")]}":
            bracket_depth -= 1
    tokens.append(s[token_start:])
    tokens = [token for token in tokens if token]
    if len(tokens) == 1:
        return token_to_bitstore(tokens[0])
    if not tokens:
        return BitRust.from_zeros(0)
    return BitRust.join([token_to_bitstore(token) for token in tokens])


class Bits:
    """
    An immutable container of binary data.

    To construct, use a builder 'from' method:

    * ``Bits.from_bytes(b)`` - Create directly from a ``bytes`` object.
    * ``Bits.from_string(s)`` - Use a formatted string.
    * ``Bits.from_bools(i)`` - Convert each element in ``i`` to a bool.
    * ``Bits.from_zeros(n)`` - Initialise with ``n`` zero bits.
    * ``Bits.from_ones(n)`` - Initialise with ``n`` one bits.
    * ``Bits.from_random(n, [seed])`` - Initialise with ``n`` pseudo-randomly set bits.
    * ``Bits.from_dtype(dtype, value)`` - Combine a data type with a value.
    * ``Bits.from_joined(iterable)`` - Concatenate an iterable of ``Bits`` objects.

    Using the constructor ``Bits(s)`` is an alias for ``Bits.from_string(s)``.

    """

    __slots__ = ("_bitstore",)

    def __new__(cls, s: str | None = None, /) -> Bits:
        x = super().__new__(cls)
        if s is None:
            x._bitstore = BitRust.from_zeros(0)
        else:
            x._bitstore = str_to_bitstore(s)
        return x

    # ----- Class Methods -----

    @classmethod
    def _from_any(cls: Type[Bits], any_: BitsType, /) -> Bits:
        """Create a new :class:`Bits` from one of the many things that can be used to build it.

        This method will be implicitly called whenever an object needs to be promoted to a :class:`Bits`.
        The builder can delegate to :meth:`Bits.from_bytes` or :meth:`Bits.from_string` as appropriate.

        :param any_: The object to convert to a :class:`Bits`.
        :type any_: BitsType

        :raises TypeError: If no builder can be found.

        .. code-block:: python

            # Bits._from_any will be called internally to convert to Bits
            a = Bits() + '0x3f' + b'hello'

        """
        if isinstance(any_, cls):
            return any_
        if isinstance(any_, str):
            return cls.from_string(any_)
        elif isinstance(any_, (bytes, bytearray, memoryview)):
            return cls.from_bytes(any_)
        raise TypeError(f"Cannot convert '{any_}' of type {type(any_)} to a Bits object.")

    @classmethod
    def from_bytes(cls, b: bytes, /) -> Bits:
        """Create a new :class:`Bits` from a bytes object.

        This method initializes a new instance of the :class:`Bits` class using a bytes object.

        :param b: The bytes object to convert to a :class:`Bits`.
        :type b: bytes
        :rtype: Bits

        .. code-block:: python

            a = Bits.from_bytes(b"some_bytes_maybe_from_a_file")

        """
        x = super().__new__(cls)
        x._bitstore = BitRust.from_bytes(b)
        return x

    @classmethod
    def from_bools(cls, i: Iterable[Any], /) -> Bits:
        """
        Create a new :class:`Bits` from an iterable by converting each element to a bool.

        This method initializes a new instance of the :class:`Bits` class using an iterable, where each element is converted to a boolean value.

        :param i: The iterable to convert to a :class:`Bits`.
        :type i: Iterable[Any]
        :rtype: Bits

        .. code-block:: python

            a = Bits.from_bools([False, 0, 1, "Steven"])  # binary 0011

        """
        x = super().__new__(cls)
        x._bitstore = BitRust.from_bin("".join("1" if x else "0" for x in i))
        return x

    @classmethod
    def from_string(cls, s: str, /) -> Bits:
        """
        Create a new :class:`Bits` from a formatted string.

        This method initializes a new instance of the :class:`Bits` class using a formatted string.

        :param s: The formatted string to convert to a :class:`Bits`.
        :type s: str
        :rtype: Bits

        .. code-block:: python

            a = Bits.from_string("0xff01")
            b = Bits.from_string("0b1")
            c = Bits.from_string("u12 = 31, f16=-0.25")

        The `__init__` method for `Bits` redirects to the `from_string` method and is sometimes more convenient:

        .. code-block:: python

            a = Bits("0xff01")  # Bits(s) is equivalent to Bits.from_string(s)

        """
        x = super().__new__(cls)
        x._bitstore = str_to_bitstore(s)
        return x

    @classmethod
    def from_joined(cls, sequence: Iterable[BitsType], /) -> Bits:
        """
        Return concatenation of Bits.

        This method concatenates a sequence of Bits objects into a single Bits object.

        :param sequence: A sequence to concatenate. Items can either be a Bits object, or a string or bytes-like object that could create one via the :meth:`from_string` or :meth:`from_bytes` methods.
        :type sequence: Iterable[BitsType]
        :rtype: Bits

        .. code-block:: python

            a = Bits.from_joined([f'u6={x}' for x in range(64)])
            b = Bits.from_joined(['0x01', 'i4 = -1', b'some_bytes'])

        """
        x = super().__new__(cls)
        x._bitstore = BitRust.join([Bits._from_any(item)._bitstore for item in sequence])
        return x

    @classmethod
    def from_ones(cls, n: int, /) -> Bits:
        """
        Create a new :class:`Bits` with all bits set to one.

        This method initializes a new instance of the :class:`Bits` class with all bits set to one.

        :param n: The number of bits.
        :type n: int
        :rtype: Bits

        .. code-block:: python

            a = Bits.from_ones(5)  # binary 11111

        """
        if n == 0:
            return Bits()
        if n < 0:
            raise ValueError(f"Negative bit length given: {n}.")
        x = super().__new__(cls)
        x._bitstore = BitRust.from_ones(n)
        return x

    @classmethod
    def from_dtype(cls, dtype: Dtype | str, value: Any, /) -> Bits:
        """
        Pack a value according to a data type or data type tuple.

        :param dtype: The data type to pack.
        :type dtype: Dtype | str
        :param value: A value appropriate for the data type.
        :type value: Any
        :returns: A newly constructed ``Bits``.
        :rtype: Bits

        .. code-block:: python

            a = Bits.from_dtype("u8", 17)
            b = Bits.from_dtype("f16, i4, bool", [2.25, -3, False])

        """
        if isinstance(dtype, str):
            dtype = Dtype.from_string(dtype)
        try:
            x = dtype.pack(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Can't pack a value of {value} with a Dtype '{dtype}': {str(e)}")
        return x

    @classmethod
    def from_zeros(cls, n: int, /) -> Bits:
        """
        Create a new Bits with all bits set to zero.

        :param n: The number of bits.
        :type n: int
        :return: A Bits object with all bits set to zero.
        :rtype: Bits

        .. code-block:: python

            a = Bits.from_zeros(500)  # 500 zero bits

        """
        if n == 0:
            return Bits()
        if n < 0:
            raise ValueError(f"Negative bit length given: {n}.")
        x = super().__new__(cls)
        x._bitstore = BitRust.from_zeros(n)
        return x

    @classmethod
    def from_random(cls, n: int, /, seed: int | None = None) -> Bits:
        """
        Create a new Bits with all bits pseudo-randomly set.

        :param n: The number of bits. Must be positive.
        :type n: int
        :param seed: An optional seed.
        :type seed: int | None
        :return: A Bits object with all bits set to zero.
        :rtype: Bits

        Note that this uses Python's pseudo-random number generator and so is
        not suitable for cryptographic or other more serious purposes.

        .. code-block:: python

            a = Bits.from_random(1000000)  # A million random bits

        """
        if n == 0:
            return Bits()
        if seed is not None:
            random.seed(seed)
        value = random.getrandbits(n)
        x = Bits.from_dtype(DtypeSingle.from_params(DtypeKind.UINT, n), value)
        return x

    # ----- Instance Methods -----

    def all(self) -> bool:
        """
        Return True if all bits are equal to 1, otherwise return False.

        :return: True if all bits are 1, otherwise False.
        :rtype: bool
        """
        return self._bitstore.all_set()

    def any(self) -> bool:
        """
        Return True if any bits are equal to 1, otherwise return False.

        :return: True if any bits are 1, otherwise False.
        :rtype: bool
        """
        return self._bitstore.any_set()

    def byte_swap(self, bytelength: int | None = None, /) -> Bits:
        """Change the byte endianness. Return new Bits.

        The whole of the Bits will be byte-swapped. It must be a multiple
        of bytelength long.

        :param bytelength: An int giving the number of bytes to swap.
        :type bytelength: int or None
        :return: A new Bits object with byte-swapped data.
        :rtype: Bits
        """
        if len(self) % 8 != 0:
            raise ValueError(f"Bit length must be an multiple of 8 to use byte_swap (got length of {len(self)} bits). "
                             "This error can be caused by using an endianness modifier on non-whole byte data.")
        if bytelength is None:
            bytelength = len(self) // 8
        if bytelength == 0:
            return Bits()
        if bytelength < 0:
            raise ValueError(f"Negative bytelength given: {bytelength}.")
        if len(self) % (bytelength * 8) != 0:
            raise ValueError(
                f"The Bits to byte_swap is {len(self) // 8} bytes long, but it needs to be a multiple of {bytelength} bytes."
            )
        chunks = []
        for startbit in range(0, len(self), bytelength * 8):
            x = self._slice(startbit, startbit + bytelength * 8).to_bytes()
            chunks.append(Bits.from_bytes(x[::-1]))
        return Bits.from_joined(chunks)

    def count(self, value: Any, /) -> int:
        """
        Return count of total number of either zero or one bits.

        :param value: If `bool(value)` is True, bits set to 1 are counted; otherwise, bits set to 0 are counted.
        :type value: Any
        :return: The count of bits set to 1 or 0.
        :rtype: int

        .. code-block:: pycon

            >>> Bits('0xef').count(1)
            7

        """
        # count the number of 1s (from which it's easy to work out the 0s).
        count = self._bitstore.count()
        return count if value else len(self) - count

    def chunks(self, chunk_size: int, /, count: int | None = None) -> Iterator[Bits]:
        """
        Return Bits generator by cutting into bits sized chunks.

        :param chunk_size: The size in bits of the chunks to generate.
        :type chunk_size: int
        :param count: If specified, at most count items are generated. Default is to cut as many times as possible.
        :type count: int, optional
        :return: A generator yielding Bits chunks.
        :rtype: Iterator[Bits]
        """
        if count is not None and count < 0:
            raise ValueError("Cannot cut - count must be >= 0.")
        if chunk_size <= 0:
            raise ValueError("Cannot cut - bits must be >= 0.")
        c = 0
        start = 0
        end = len(self)
        while count is None or c < count:
            c += 1
            nextchunk = self._slice(start, min(start + chunk_size, end))
            if len(nextchunk) == 0:
                return
            yield nextchunk
            if len(nextchunk) != chunk_size:
                return
            start += chunk_size
        return

    def ends_with(self, suffix: BitsType, /) -> bool:
        """
        Return whether the current Bits ends with suffix.

        :param suffix: The Bits to search for.
        :type suffix: BitsType
        :return: True if the Bits ends with the suffix, otherwise False.
        :rtype: bool
        """
        suffix = self._from_any(suffix)
        if len(suffix) <= len(self):
            return self._slice(len(self) - len(suffix), len(self)) == suffix
        return False

    def find(self, bs: BitsType, /, byte_aligned: bool | None = None) -> int | None:
        """
        Find first occurrence of substring bs.

        Returns the bit position if found, or None if not found.

        :param bs: The Bits to find.
        :type bs: BitsType
        :param byte_aligned: If True, the Bits will only be found on byte boundaries.
        :type byte_aligned: bool, optional
        :return: The bit position if found, or None if not found.
        :rtype: int or None

        .. code-block:: pycon

            >>> Bits.from_string('0xc3e').find('0b1111')
            6

        """
        bs = Bits._from_any(bs)
        if len(bs) == 0:
            raise ValueError("Cannot find an empty Bits.")
        ba = Options().byte_aligned if byte_aligned is None else byte_aligned
        p = self._bitstore.find(bs._bitstore, 0, ba)
        return None if p == -1 else p

    def find_all(self, bs: BitsType, count: int | None = None, byte_aligned: bool | None = None) -> Iterable[int]:
        """Find all occurrences of bs. Return generator of bit positions.

        :param bs: The Bits to find.
        :type bs: BitsType
        :param count: The maximum number of occurrences to find.
        :type count: int, optional
        :param byte_aligned: If True, the Bits will only be found on byte boundaries.
        :type byte_aligned: bool, optional
        :return: A generator yielding bit positions.
        :rtype: Iterable[int]

        Raises ValueError if bs is empty, if start < 0, if end > len(self) or
        if end < start.

        Note that all occurrences of bs are found, even if they overlap.

        """
        if count is not None and count < 0:
            raise ValueError("In find_all, count must be >= 0.")
        bs = Bits._from_any(bs)
        ba = Options().byte_aligned if byte_aligned is None else byte_aligned
        return self._find_all(bs, count, ba)

    def info(self) -> str:
        """Return a descriptive string with information about the Bits.

        Note that the output is designed to be helpful to users and is not considered part of the API.
        You should not use the output programmatically as it may change even between point versions.
        """

        def with_underscores(s: str) -> str:
            """Insert underscores every 4 characters."""
            return "_".join(s[x : x + 4] for x in range(0, len(s), 4))

        length = len(self)
        if length == 0:
            return "0 bits: empty"
        max_interpretation_length = 64
        len_str = f"{length} bit{'' if length == 1 else 's'}: "
        if length <= max_interpretation_length:
            hex_str = f_str = ""
            t = self.unpack("bin")
            bin_str = f"binary = {with_underscores(t)}"
            if length % 4 == 0:
                hex_str = f"hex = {with_underscores(self.unpack('hex'))}"
            u = self.unpack("u")
            i = self.unpack("i")
            u_str = f"unsigned int = {u}"
            i_str = f"signed int = {i}"
            if length in Register().kind_to_def[DtypeKind.FLOAT].allowed_sizes:
                f_str = f'float = {self.unpack("f")}'
            return len_str + ", ".join(x for x in [bin_str, hex_str, f_str, u_str, i_str] if x)
        else:
            if length <= 4 * max_interpretation_length and length % 4 == 0:
                return f"{len_str}hex = {with_underscores(self.unpack('hex'))}"
            else:
                if length % 4 == 0:
                    return f"{len_str}hex ≈ {with_underscores(self[:4 * max_interpretation_length].unpack('hex'))}..."
                else:
                    return f"{len_str}binary ≈ {with_underscores(self[:max_interpretation_length].unpack('bin'))}..."

    def insert(self, pos: int, bs: BitsType, /) -> Bits:
        """Return new Bits with bs inserted at bit position pos.

        :param pos: The bit position to insert at.
        :type pos: int
        :param bs: The Bits to insert.
        :type bs: BitsType
        :return: A new Bits object with the inserted bits.
        :rtype: Bits

        Raises ValueError if pos < 0 or pos > len(self).

        """
        bs = self._from_any(bs)
        if pos < 0:
            pos += len(self)
        if pos < 0 or pos > len(self):
            raise ValueError("Overwrite starts outside boundary of Bits.")
        x = self.__class__()
        x._bitstore = BitRust.join([self._bitstore.getslice(0, pos),
                                    bs._bitstore,
                                    self._bitstore.getslice(pos, None)])
        return x

    def invert(self, pos: Iterable[int] | int | None = None) -> Bits:
        """Return new Bits with one or many bits inverted between 0 and 1.

        :param pos: Either a single bit position or an iterable of bit positions.
        :type pos: int or Iterable[int] or None
        :return: A new Bits object with the inverted bits.
        :rtype: Bits

        Raises IndexError if pos < -len(self) or pos >= len(self).

        """
        x = self.__class__()
        if pos is None:
            x._bitstore = self._bitstore.invert_all()
        elif not isinstance(pos, abc.Iterable):
            x._bitstore = self._bitstore.invert_single_bit(pos)
        else:
            x._bitstore = self._bitstore.invert_bit_list(list(pos))
        return x

    def overwrite(self, pos: int, bs: BitsType, /) -> Bits:
        """Return new Bits with bs overwritten at bit position pos.

        :param pos: The bit position to start overwriting at.
        :type pos: int
        :param bs: The Bits to overwrite.
        :type bs: BitsType
        :return: A new Bits object with the overwritten bits.
        :rtype: Bits

        Raises ValueError if pos < 0 or pos > len(self).

        """
        bs = self._from_any(bs)
        if pos < 0:
            pos += len(self)
        if pos < 0 or pos > len(self):
            raise ValueError("Overwrite starts outside boundary of Bits.")
        x = self.__class__()
        x._bitstore = BitRust.join([self._bitstore.getslice(0, pos),
                                    bs._bitstore,
                                    self._bitstore.getslice(pos + len(bs), None)])
        return x

    def pp(self, dtype1: str | Dtype | None = None, dtype2: str | Dtype | None = None,
           groups: int | None = None, width: int = 80, show_offset: bool = True, stream: TextIO = sys.stdout) -> None:
        """Pretty print the Bits's value.

        :param dtype1: First data type to display.
        :type dtype1: str or Dtype or None
        :param dtype2: Optional second data type.
        :type dtype2: str or Dtype or None
        :param groups: How many groups of bits to display on each line. This overrides any value given for width.
        :type groups: int or None
        :param width: Max width of printed lines. Defaults to 80, but ignored if groups parameter is set.
            A single group will always be printed per line even if it exceeds the max width.
        :type width: int
        :param show_offset: If True (the default) shows the bit offset in the first column of each line.
        :type show_offset: bool
        :param stream: A TextIO object with a write() method. Defaults to sys.stdout.
        :type stream: TextIO
        :return: None

        .. code-block:: pycon

            s.pp('hex4', groups=6)
            s.pp('bin', 'hex', show_offset=False)

        """
        colour = Colour(not Options().no_color)
        if dtype1 is None and dtype2 is not None:
            dtype1, dtype2 = dtype2, dtype1
        if dtype1 is None:
            dtype1 = DtypeSingle.from_params(DtypeKind.BIN)
            if len(self) % 8 == 0 and len(self) >= 8:
                dtype2 = DtypeSingle.from_params(DtypeKind.HEX)
        if isinstance(dtype1, str):
            dtype1 = Dtype.from_string(dtype1)
        if isinstance(dtype2, str):
            dtype2 = Dtype.from_string(dtype2)

        bits_per_group, has_length_in_fmt = Bits._process_pp_tokens(dtype1, dtype2)
        trailing_bit_length = len(self) % bits_per_group if has_length_in_fmt and bits_per_group else 0
        data = self if trailing_bit_length == 0 else self[0:-trailing_bit_length]
        sep = " "  # String to insert between groups
        format_sep = " : "  # String to insert on each line between multiple formats
        dtype1_str = str(dtype1)
        dtype2_str = ""
        if dtype2 is not None:
            dtype2_str = f", dtype2='{dtype2}'"
        output_stream = io.StringIO()
        len_str = colour.green + str(len(self)) + colour.off
        output_stream.write(f"<{self.__class__.__name__}, dtype1='{dtype1_str}'{dtype2_str}, length={len_str} bits> [\n")
        data._pp(dtype1, dtype2, bits_per_group, width, sep, format_sep, show_offset, output_stream, 1, groups)
        output_stream.write("]")
        if trailing_bit_length != 0:
            output_stream.write(" + trailing_bits = 0b" + Dtype("bin").unpack(self[-trailing_bit_length:]))
        output_stream.write("\n")
        stream.write(output_stream.getvalue())
        return

    def replace(self, old: BitsType, new: BitsType, /, start: int | None = None, end: int | None = None,
                count: int | None = None, byte_aligned: bool | None = None) -> Bits:
        """Return new Bits with all occurrences of old replaced with new.

        :param old: The Bits to replace.
        :type old: BitsType
        :param new: The replacement Bits.
        :type new: BitsType
        :param start: Any occurrences that start before this will not be replaced.
        :type start: int, optional
        :param end: Any occurrences that finish after this will not be replaced.
        :type end: int, optional
        :param count: The maximum number of replacements to make. Defaults to all.
        :type count: int, optional
        :param byte_aligned: If True, replacements will only be made on byte boundaries.
        :type byte_aligned: bool, optional
        :return: A new Bits object with the replaced bits.
        :rtype: Bits

        Raises ValueError if old is empty or if start or end are out of range.

        """
        if count == 0:
            return self
        old = self._from_any(old)
        new = self._from_any(new)
        if len(old) == 0:
            raise ValueError("Empty Bits cannot be replaced.")
        start, end = self._validate_slice(start, end)
        if byte_aligned is None:
            byte_aligned = Options().byte_aligned
        # First find all the places where we want to do the replacements
        starting_points: list[int] = []
        if byte_aligned:
            start += (8 - start % 8) % 8
        for x in self[start:end].find_all(old, byte_aligned=byte_aligned):
            x += start
            if not starting_points:
                starting_points.append(x)
            elif x >= starting_points[-1] + len(old):
                # Can only replace here if it hasn't already been replaced!
                starting_points.append(x)
            if count != 0 and len(starting_points) == count:
                break
        if not starting_points:
            return self
        replacement_list = [self._bitstore.getslice(0, starting_points[0])]
        for i in range(len(starting_points) - 1):
            replacement_list.append(new._bitstore)
            replacement_list.append(self._bitstore.getslice(starting_points[i] + len(old), starting_points[i + 1]))
        # Final replacement
        replacement_list.append(new._bitstore)
        replacement_list.append(self._bitstore.getslice(starting_points[-1] + len(old), None))
        x = self.__class__()
        x._bitstore = BitRust.join(replacement_list)
        return x

    def reverse(self) -> Bits:
        """Reverse bits.

        :return: A new Bits object with the reversed bits.
        :rtype: Bits

        """
        x = self.__class__()
        bs = self._bitstore.reverse()
        x._bitstore = bs
        return x

    def rfind(self, bs: BitsType, /, byte_aligned: bool | None = None) -> int | None:
        """Find final occurrence of substring bs.

        Returns a the bit position if found, or None if not found.

        :param bs: The Bits to find.
        :type bs: BitsType
        :param byte_aligned: If True, the Bits will only be found on byte boundaries.
        :type byte_aligned: bool, optional
        :return: The bit position if found, or None if not found.
        :rtype: int or None

        Raises ValueError if bs is empty, if start < 0, if end > len(self) or
        if end < start.

        """
        bs = Bits._from_any(bs)
        ba = Options().byte_aligned if byte_aligned is None else byte_aligned
        if len(bs) == 0:
            raise ValueError("Cannot find an empty Bits.")
        p = self._bitstore.rfind(bs._bitstore, 0, ba)
        return None if p == -1 else p

    def rol(self, n: int, /, start: int | None = None, end: int | None = None) -> Bits:
        """Return new Bits with bit pattern rotated to the left.

        :param n: The number of bits to rotate by.
        :type n: int
        :param start: Start of slice to rotate. Defaults to 0.
        :type start: int, optional
        :param end: End of slice to rotate. Defaults to len(self).
        :type end: int, optional
        :return: A new Bits object with the rotated bits.
        :rtype: Bits

        Raises ValueError if bits < 0.

        """
        if not len(self):
            raise ValueError("Cannot rotate an empty Bits.")
        if n < 0:
            raise ValueError("Cannot rotate by negative amount.")
        start, end = self._validate_slice(start, end)
        n %= end - start
        return Bits.from_joined([self._slice(0, start),
                                 self._slice(start + n, end),
                                 self._slice(start, start + n),
                                 self._slice(end, len(self))])

    def ror(self, n: int, /, start: int | None = None, end: int | None = None) -> Bits:
        """Return new Bits with bit pattern rotated to the right.

        :param n: The number of bits to rotate by.
        :type n: int
        :param start: Start of slice to rotate. Defaults to 0.
        :type start: int, optional
        :param end: End of slice to rotate. Defaults to len(self).
        :type end: int, optional
        :return: A new Bits object with the rotated bits.
        :rtype: Bits

        Raises ValueError if bits < 0.

        """
        if len(self) == 0:
            raise ValueError("Cannot rotate an empty Bits.")
        if n < 0:
            raise ValueError("Cannot rotate by negative amount.")
        start, end = self._validate_slice(start, end)
        n %= end - start
        return Bits.from_joined(
            [
                self._slice(0, start),
                self._slice(end - n, end),
                self._slice(start, end - n),
                self._slice(end, len(self)),
            ]
        )

    def set(self, value: Any, pos: int | Sequence[int]) -> Bits:
        """Return new Bits with one or many bits set to 1 or 0.

        :param value: If bool(value) is True, bits are set to 1, otherwise they are set to 0.
        :type value: Any
        :param pos: Either a single bit position or an iterable of bit positions.
        :type pos: int or Sequence[int]
        :return: A new Bits object with the set bits.
        :rtype: Bits

        Raises IndexError if pos < -len(self) or pos >= len(self).

        """
        v = True if value else False
        if not isinstance(pos, abc.Sequence):
            s = Bits()
            if pos < 0:
                pos += len(self)
            if pos < 0 or pos >= len(self):
                raise IndexError
            s._bitstore = self._bitstore.set_index(v, pos)
        elif isinstance(pos, range):
            s = Bits()
            s._bitstore = self._bitstore.set_from_slice(v, pos.start or 0, pos.stop, pos.step or 1)
        else:
            s = Bits()
            s._bitstore = self._bitstore.set_from_sequence(v, pos)
        return s

    def starts_with(self, prefix: BitsType) -> bool:
        """Return whether the current Bits starts with prefix.

        :param prefix: The Bits to search for.
        :type prefix: BitsType
        :return: True if the Bits starts with the prefix, otherwise False.
        :rtype: bool

        """
        prefix = self._from_any(prefix)
        if len(prefix) <= len(self):
            return self._slice(0, len(prefix)) == prefix
        return False

    def to_bytes(self) -> bytes:
        """Return the Bits as bytes, padding with zero bits if needed.

        Up to seven zero bits will be added at the end to byte align.

        :return: The Bits as bytes.
        :rtype: bytes

        """
        return self._bitstore.to_bytes()

    def unpack(self, fmt: Dtype | str | list[Dtype | str], /) -> Any | list[Any]:
        """
        Interpret the Bits as a given data type or list of data types.

        If a single Dtype is given then a single value will be returned, otherwise a list of values will be returned.
        A single Dtype with no length can be used to interpret the whole Bits - in this common case properties
        are provided as a shortcut. For example instead of ``b.unpack('bin')`` you can use ``b.bin``.

        :param fmt: The data type or list of data types to interpret the Bits as.
        :type fmt: Dtype | str | list[Dtype | str]
        :return: The interpreted value(s).
        :rtype: Any or list[Any]

        .. code-block:: pycon

            >>> s = Bits('0xdeadbeef')
            >>> s.unpack(['bin4', 'u28'])
            ['1101', 246267631]
            >>> s.unpack(['f16', '[u4; 4]'])
            [-427.25, (11, 14, 14, 15)]
            >>> s.unpack('i')
            -559038737
            >>> s.i
            -559038737

        """
        # First do the cases where there's only one data type.
        # For dtypes like hex, bin etc. there's no need to specify a length.
        if isinstance(fmt, list):
            d = DtypeTuple.from_params(fmt)
            return list(d.unpack(self))
        if isinstance(fmt, str):
            fmt = Dtype.from_string(fmt)
        return fmt.unpack(self)

    # ----- Private Methods -----

    def _find_all(self, bs: Bits, count: int | None, byte_aligned: bool) -> Iterable[int]:
        c = 0
        for i in self._bitstore.findall(bs._bitstore, byte_aligned):
            if count is not None and c >= count:
                return
            c += 1
            yield i
        return

    def _set_bits(self, bs: BitsType, _length: None = None) -> None:
        bs = Bits._from_any(bs)
        self._bitstore = bs._bitstore

    def _set_bytes(self, data: bytearray | bytes | list, _length: None = None) -> None:
        """Set the data from a bytes or bytearray object."""
        self._bitstore = BitRust.from_bytes(bytes(data))

    def _get_bytes(self) -> bytes:
        """Return the data as an ordinary bytes object."""
        if len(self) % 8:
            raise ValueError(f"Cannot interpret as bytes - length of {len(self)} is not a multiple of 8 bits.")
        return self._bitstore.to_bytes()

    _unprintable = list(range(0x00, 0x20))  # ASCII control characters
    _unprintable.extend(range(0x7F, 0xFF))  # DEL char + non-ASCII

    def _get_bytes_printable(self) -> str:
        """Return an approximation of the data as a string of printable characters."""
        bytes_ = self._get_bytes()
        # For everything that isn't printable ASCII, use value from 'Latin Extended-A' unicode block.
        string = "".join(chr(0x100 + x) if x in Bits._unprintable else chr(x) for x in bytes_)
        return string

    def _set_u(self, u: int | str, length: int | None = None) -> None:
        """Reset the Bits to have given unsigned int interpretation."""
        u = int(u)
        if length is None or length == 0:
            raise ValueError("A non-zero length must be specified with a 'u' initialiser.")
        try:
            if u >= (1 << length):
                raise ValueError(f"{u} is too large an unsigned integer for a Bits of length {length}. "
                                 f"The allowed range is [0, {(1 << length) - 1}].")
            if u < 0:
                raise ValueError(f"Unsigned integers cannot be initialised with the negative number {u}.")
            b = u.to_bytes((length + 7) // 8, byteorder="big", signed=False)
            offset = 8 - (length % 8)
            if offset == 8:
                self._bitstore = BitRust.from_bytes(b)
            else:
                self._bitstore = BitRust.from_bytes_with_offset(b, offset=offset)
        except OverflowError as e:
            if u >= (1 << length):
                raise ValueError(f"{u} is too large an unsigned integer for a Bits of length {length}. "
                                 f"The allowed range is [0, {(1 << length) - 1}].")
            if u < 0:
                raise ValueError(f"Cannot initialise an unsigned integer with the negative number {u}.")
            raise e

    def _get_u(self) -> int:
        """Return data as an unsigned int."""
        if len(self) == 0:
            raise ValueError("Cannot interpret empty Bits as an integer.")
        return int.from_bytes(self._bitstore.to_int_byte_data(False), byteorder="big", signed=False)

    def _set_i(self, i: int | str, length: int | None = None) -> None:
        """Reset the Bits to have given signed int interpretation."""
        i = int(i)
        if length is None or length == 0:
            raise ValueError("A non-zero length must be specified with an 'i' initialiser.")
        try:
            if i >= (1 << (length - 1)) or i < -(1 << (length - 1)):
                raise ValueError(f"{i} is too large a signed integer for a Bits of length {length}. "
                                 f"The allowed range is [{-(1 << (length - 1))}, {(1 << (length - 1)) - 1}].")
            b = i.to_bytes((length + 7) // 8, byteorder="big", signed=True)
            offset = 8 - (length % 8)
            if offset == 8:
                self._bitstore = BitRust.from_bytes(b)
            else:
                self._bitstore = BitRust.from_bytes_with_offset(b, offset=offset)
        except OverflowError as e:
            if i >= (1 << (length - 1)) or i < -(1 << (length - 1)):
                raise ValueError(f"{i} is too large a signed integer for a Bits of length {length}. "
                                 f"The allowed range is [{-(1 << (length - 1))}, {(1 << (length - 1)) - 1}].")
            raise e

    def _get_i(self) -> int:
        """Return data as a two's complement signed int."""
        if len(self) == 0:
            raise ValueError("Cannot interpret empty Bits as an integer.")
        return int.from_bytes(self._bitstore.to_int_byte_data(True), byteorder="big", signed=True)

    def _set_f(self, f: float | str, length: int | None) -> None:
        if length is None:
            raise ValueError("No length can be inferred for the float initialiser.")
        f = float(f)
        fmt = {16: ">e", 32: ">f", 64: ">d"}[length]
        try:
            b = struct.pack(fmt, f)
        except OverflowError:
            # If float64 doesn't fit it automatically goes to 'inf'. This reproduces that behaviour for other types.
            b = struct.pack(fmt, float("inf") if f > 0 else float("-inf"))
        self._bitstore = BitRust.from_bytes(b)

    def _get_f(self) -> float:
        """Interpret the whole Bits as a big-endian float."""
        fmt = {16: ">e", 32: ">f", 64: ">d"}[len(self)]
        return struct.unpack(fmt, self._bitstore.to_bytes())[0]

    def _set_bool(self, value: bool) -> None:
        self._bitstore = BitRust.from_bin("1") if value else BitRust.from_bin("0")
        return

    def _get_bool(self) -> bool:
        return self[0]

    def _get_pad(self) -> None:
        return None

    def _set_pad(self, value: None, length: int) -> None:
        raise ValueError("It's not possible to set a 'pad' value.")

    def _set_bin_safe(self, binstring: str, _length: None = None) -> None:
        """Reset the Bits to the value given in binstring."""
        self._bitstore = BitRust.from_bin_checked(binstring)

    def _get_bin(self) -> str:
        """Return interpretation as a binary string."""
        return self._bitstore.to_bin()

    def _set_oct(self, octstring: str, _length: None = None) -> None:
        """Reset the Bits to have the value given in octstring."""
        self._bitstore = BitRust.from_oct_checked(octstring)

    def _get_oct(self) -> str:
        """Return interpretation as an octal string."""
        if len(self) % 3 != 0:
            raise ValueError(f"Cannot interpret '{self}' as octal - length of {len(self)} is not a multiple of 3 bits.")
        return self._bitstore.to_oct()

    def _set_hex(self, hexstring: str, _length: None = None) -> None:
        """Reset the Bits to have the value given in hexstring."""
        self._bitstore = BitRust.from_hex_checked(hexstring)

    def _get_hex(self) -> str:
        """Return the hexadecimal representation as a string."""
        if len(self) % 4 != 0:
            raise ValueError(f"Cannot interpret '{self}' as hex - length of {len(self)} is not a multiple of 4 bits.")
        return self._bitstore.to_hex()

    def _slice(self: Bits, start: int, end: int) -> Bits:
        """Used internally to get a  slice, without error checking. No copy of data is made - it's just a view."""
        bs = self.__class__()
        bs._bitstore = self._bitstore.getslice(start, end)
        return bs

    def _get_bits(self: Bits):
        return self

    def _validate_slice(self, start: int | None, end: int | None) -> tuple[int, int]:
        """Validate start and end and return them as positive bit positions."""
        start = 0 if start is None else (start + len(self) if start < 0 else start)
        end = len(self) if end is None else (end + len(self) if end < 0 else end)
        if not 0 <= start <= end <= len(self):
            raise ValueError(
                f"Invalid slice positions for Bits length {len(self)}: start={start}, end={end}."
            )
        return start, end

    def _simple_str(self) -> str:
        length = len(self)
        if length == 0:
            s = ""
        elif length % 4 == 0:
            s = "0x" + self.unpack("hex")
        else:
            s = "0b" + self.unpack("bin")
        return s

    @staticmethod
    def _format_bits(bits: Bits, bits_per_group: int, sep: str, dtype: Dtype, colour_start: str,
                     colour_end: str,  width: int | None = None) -> tuple[str, int]:
        get_fn = dtype.unpack
        chars_per_group = Bits._chars_per_dtype(dtype, bits_per_group)
        if isinstance(dtype, (DtypeSingle, DtypeArray)):
            n = dtype.kind
            if n is DtypeKind.BYTES:  # Special case for bytes to print one character each.
                get_fn = Bits._get_bytes_printable
            elif n is DtypeKind.BOOL:  # Special case for bool to print '1' or '0' instead of `True` or `False`.
                get_fn = Register().get_single_dtype(DtypeKind.UINT, bits_per_group).unpack
            align = ">"
            if n is DtypeKind.BIN or n is DtypeKind.OCT or n is DtypeKind.HEX or n is DtypeKind.BITS or n is DtypeKind.BYTES:
                align = "<"
            if dtype.kind is DtypeKind.BITS:
                x = sep.join(f"{b._simple_str(): {align}{chars_per_group}}" for b in bits.chunks(bits_per_group))
            else:
                x = sep.join(f"{str(get_fn(b)): {align}{chars_per_group}}" for b in bits.chunks(bits_per_group))

            chars_used = len(x)
            padding_spaces = 0 if width is None else max(width - len(x), 0)
            x = colour_start + x + colour_end
            # Pad final line with spaces to align it
            x += " " * padding_spaces
            return x, chars_used
        else:  # DtypeTuple
            align = ">"
            s = []
            for b in bits.chunks(bits_per_group):
                chars_per_dtype = [Bits._chars_per_dtype(d, d.bit_length) for d in dtype]
                values = get_fn(b)
                strings = [f"{str(v): {align}{c}}" for v, c in zip(values, chars_per_dtype)]
                s.append(f"[{', '.join(strings)}]")
            x = sep.join(s)
            chars_used = len(x)
            padding_spaces = 0 if width is None else max(width - len(x), 0)
            x = colour_start + x + colour_end
            # Pad final line with spaces to align it
            x += " " * padding_spaces
            return x, chars_used

    @staticmethod
    def _chars_per_dtype(dtype: Dtype, bits_per_group: int):
        """How many characters are needed to represent a number of bits with a given Dtype."""
        if isinstance(dtype, (DtypeSingle, DtypeArray)):
            # TODO: Not sure this is right for DtypeArray. Maybe needs a refactor?
            return Register().kind_to_def[dtype.kind].bitlength2chars_fn(bits_per_group)
        # Start with '[' then add the number of characters for each element and add ', ' for each element, ending with a ']'.
        chars = sum(Bits._chars_per_dtype(d, bits_per_group) for d in dtype) + 2 + 2 * (dtype.items - 1)
        return chars

    def _pp(self, dtype1: Dtype, dtype2: Dtype | None, bits_per_group: int,
            width: int, sep: str, format_sep: str, show_offset: bool, stream: TextIO, offset_factor: int,
            groups: int | None) -> None:
        """Internal pretty print method."""
        if dtype2 is not None:
            if dtype1.bit_length is not None:
                try:
                    _ = dtype2.unpack(Bits.from_zeros(dtype1.bit_length))
                except ValueError:
                    raise ValueError(f"The Dtype '{dtype2}' can't be used alongside '{dtype1}' as it's not compatible with it's length.")
            if dtype2.bit_length is not None:
                try:
                    _ = dtype1.unpack(Bits.from_zeros(dtype2.bit_length))
                except ValueError:
                    raise ValueError(f"The Dtype '{dtype1}' can't be used alongside '{dtype2}' as it's not compatible with it's length.")
        colour = Colour(not Options().no_color)
        offset_width = 0
        offset_sep = ": "
        if show_offset:
            # This could be 1 too large in some circumstances. Slightly recurrent logic needed to fix it...
            offset_width = len(str(len(self))) + len(offset_sep)
        group_chars1 = Bits._chars_per_dtype(dtype1, bits_per_group)
        group_chars2 = 0 if dtype2 is None else Bits._chars_per_dtype(dtype2, bits_per_group)
        if groups is None:
            # The number of characters that get added when we add an extra group (after the first one)
            total_group_chars = group_chars1 + group_chars2 + len(sep) + len(sep) * bool(group_chars2)
            width_excluding_offset_and_final_group = width - offset_width - group_chars1 - group_chars2 - len(format_sep) * bool(group_chars2)
            width_excluding_offset_and_final_group = max(width_excluding_offset_and_final_group, 0)
            groups_per_line = 1 + width_excluding_offset_and_final_group // total_group_chars
        else:
            groups_per_line = groups
        max_bits_per_line = groups_per_line * bits_per_group  # Number of bits represented on each line
        assert max_bits_per_line > 0

        bitpos = 0
        first_fb_width = second_fb_width = None
        for bits in self.chunks(max_bits_per_line):
            offset_str = ""
            if show_offset:
                offset = bitpos // offset_factor
                bitpos += len(bits)
                offset_str = colour.green + f"{offset: >{offset_width - len(offset_sep)}}" + offset_sep + colour.off
            fb1, chars_used = Bits._format_bits(bits, bits_per_group, sep, dtype1, colour.magenta, colour.off, first_fb_width)
            if first_fb_width is None:
                first_fb_width = chars_used
            fb2 = ""
            if dtype2 is not None:
                fb2, chars_used = Bits._format_bits(bits, bits_per_group, sep, dtype2, colour.blue, colour.off, second_fb_width)
                if second_fb_width is None:
                    second_fb_width = chars_used
                fb2 = format_sep + fb2

            line_fmt = offset_str + fb1 + fb2 + "\n"
            stream.write(line_fmt)
        return

    @staticmethod
    def _process_pp_tokens(dtype1: Dtype, dtype2: Dtype | None) -> tuple[int, bool]:
        has_length_in_fmt = True
        bits_per_group = 0 if dtype1.bit_length is None else dtype1.bit_length

        if dtype2 is not None:
            if None not in {dtype1.bit_length, dtype2.bit_length} and dtype1.bit_length != dtype2.bit_length:
                raise ValueError(f"The Dtypes '{dtype1}' and '{dtype2}' can't be used together as they have differing "
                                 f"bit lengths of {dtype1.bit_length} and {dtype2.bit_length} respectively.")
            if bits_per_group == 0:
                bits_per_group = 0 if dtype2.bit_length is None else dtype2.bit_length

        if bits_per_group == 0:
            has_length_in_fmt = False
            if dtype2 is None:
                bits_per_group = {"bin": 8, "hex": 8, "oct": 12, "bytes": 32}.get(dtype1.kind.value, 0)
                if bits_per_group == 0:
                    raise ValueError(f"No length or default length available for pp() dtype '{dtype1}'.")
            else:
                try:
                    bits_per_group = 2 * dtype1._definition.bits_per_character * dtype2._definition.bits_per_character
                except ValueError:
                    raise ValueError(f"Can't find a default bit_length to use for pp() format with dtypes '{dtype1}' and '{dtype2}'.")
                if bits_per_group >= 24:
                    bits_per_group //= 2
        return bits_per_group, has_length_in_fmt

    # ----- Special Methods -----

    # ----- Logical
    def __and__(self: Bits, bs: BitsType, /) -> Bits:
        """Bit-wise 'and' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        if bs is self:
            return self
        bs = Bits._from_any(bs)
        s = object.__new__(self.__class__)
        s._bitstore = self._bitstore & bs._bitstore
        return s

    def __or__(self: Bits, bs: BitsType, /) -> Bits:
        """Bit-wise 'or' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        if bs is self:
            return self
        bs = Bits._from_any(bs)
        s = object.__new__(self.__class__)
        s._bitstore = self._bitstore | bs._bitstore
        return s

    def __xor__(self: Bits, bs: BitsType, /) -> Bits:
        """Bit-wise 'xor' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        bs = Bits._from_any(bs)
        s = object.__new__(self.__class__)
        s._bitstore = self._bitstore ^ bs._bitstore
        return s

    def __rand__(self: Bits, bs: BitsType, /) -> Bits:
        """Bit-wise 'and' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        return self.__and__(bs)

    def __ror__(self: Bits, bs: BitsType, /) -> Bits:
        """Bit-wise 'or' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        return self.__or__(bs)

    def __rxor__(self: Bits, bs: BitsType, /) -> Bits:
        """Bit-wise 'xor' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        return self.__xor__(bs)

    # ----- Conversions

    def __bool__(self) -> bool:
        """Return False if Bits is empty, otherwise return True."""
        return len(self) != 0

    def __bytes__(self) -> bytes:
        return self.to_bytes()

    def __str__(self) -> str:
        """Return string representations of Bits for printing."""
        length = len(self)
        if length == 0:
            return ""
        return self._simple_str()

    def __repr__(self) -> str:
        """Return representation that could be used to recreate the Bits.."""
        repr_ = f"{self.__class__.__name__}('{self._simple_str()}')"
        return repr_

    # ----- Comparisons

    def __eq__(self, bs: Any, /) -> bool:
        """Return True if two Bits have the same binary representation.

        >>> Bits('0b1110') == '0xe'
        True

        """
        try:
            return self._bitstore == Bits._from_any(bs)._bitstore
        except TypeError:
            return False

    def __ge__(self, other: Any, /) -> bool:
        # Bits can't really be ordered.
        return NotImplemented

    def __gt__(self, other: Any, /) -> bool:
        # Bits can't really be ordered.
        return NotImplemented

    def __le__(self, other: Any, /) -> bool:
        # Bits can't really be ordered.
        return NotImplemented

    def __lt__(self, other: Any, /) -> bool:
        # Bits can't really be ordered.
        return NotImplemented

    def __ne__(self, bs: Any, /) -> bool:
        """Return False if two Bits have the same binary representation.

        >>> Bits('0b111') != '0x7'
        False

        """
        return not self.__eq__(bs)

    # ----- Operators

    def __add__(self: Bits, bs: BitsType, /) -> Bits:
        """Concatenate Bits and return a new Bits."""
        return Bits.from_joined([self, Bits._from_any(bs)])

    @overload
    def __getitem__(self: Bits, key: slice, /) -> Bits: ...

    @overload
    def __getitem__(self, key: int, /) -> bool: ...

    def __getitem__(self: Bits, key: slice | int, /) -> Bits | bool:
        """Return a new Bits representing a slice of the current Bits."""
        if isinstance(key, numbers.Integral):
            return bool(self._bitstore.getindex(key))
        bs = super().__new__(self.__class__)
        start, stop, step = key.indices(len(self))
        if step == 1:
            bs._bitstore = self._bitstore.getslice(start, stop)
        else:
            bs._bitstore = self._bitstore.getslice_with_step(start, stop, step)
        return bs

    def __invert__(self: Bits) -> Bits:
        """Return the Bits with every bit inverted.

        Raises ValueError if the Bits is empty.

        """
        if len(self) == 0:
            raise ValueError("Cannot invert empty Bits.")
        x = self.__class__()
        x._bitstore = self._bitstore.invert()
        return x

    def __lshift__(self: Bits, n: int, /) -> Bits:
        """Return Bits shifted by n to the left.

        n -- the number of bits to shift. Must be >= 0.

        """
        if n < 0:
            raise ValueError("Cannot shift by a negative amount.")
        if len(self) == 0:
            raise ValueError("Cannot shift an empty Bits.")
        n = min(n, len(self))
        return Bits.from_joined([self._slice(n, len(self)), Bits.from_zeros(n)])

    def __mul__(self: Bits, n: int, /) -> Bits:
        """Return new Bits consisting of n concatenations of self.

        Called for expression of the form 'a = b*3'.
        n -- The number of concatenations. Must be >= 0.

        """
        if n < 0:
            raise ValueError("Cannot multiply by a negative integer.")
        x = self.__class__()
        if n == 0:
            return x
        # No need to copy as the BitRust is immutable.
        x._bitstore = self._bitstore
        m = 1
        old_len = len(self)
        # Keep doubling the length for as long as we can
        while m * 2 < n:
            x._bitstore = BitRust.join([x._bitstore, x._bitstore])
            m *= 2
        # Then finish off with the remaining copies
        x._bitstore = BitRust.join([x._bitstore, x[0: (n - m) * old_len]._bitstore])
        return x

    def __radd__(self: Bits, bs: BitsType, /) -> Bits:
        """Concatenate Bits and return a new Bits."""
        bs = self.__class__._from_any(bs)
        return bs.__add__(self)

    def __rmul__(self: Bits, n: int, /) -> Bits:
        """Return Bits consisting of n concatenations of self.

        Called for expressions of the form 'a = 3*b'.
        n -- The number of concatenations. Must be >= 0.

        """
        return self.__mul__(n)

    def __rshift__(self: Bits, n: int, /) -> Bits:
        """Return Bits shifted by n to the right.

        n -- the number of bits to shift. Must be >= 0.

        """
        if n < 0:
            raise ValueError("Cannot shift by a negative amount.")
        if len(self) == 0:
            raise ValueError("Cannot shift an empty Bits.")
        if n == 0:
            return self
        n = min(n, len(self))
        return Bits.from_joined([Bits.from_zeros(n), self._slice(0, len(self) - n)])

    # ----- Other

    def __contains__(self, bs: BitsType, /) -> bool:
        """Return whether bs is contained in the current Bits.

        bs -- The Bits to search for.

        """
        found = Bits.find(self, bs, byte_aligned=False)
        return False if found is None else True

    def __copy__(self: Bits) -> Bits:
        """Return a new copy of the Bits for the copy module.

        This can just return self as it's immutable.

        """
        return self

    def __hash__(self) -> int:
        """Return an integer hash of the object."""
        # Only requirement is that equal Bits should return the same hash.
        # For equal Bits the bytes at the start/end will be the same and they will have the same length
        # (need to check the length as there could be zero padding when getting the bytes).
        length = len(self)
        if length <= 2000:
            # Use the whole Bits.
            return hash((self.to_bytes(), length))
        else:
            # We can't in general hash the whole Bits (it could take hours!)
            # So instead take some bits from the start and end.
            start = self._slice(0, 800)
            end = self._slice(length - 800, length)
            return hash(((start + end).to_bytes(), length))

    def __iter__(self) -> Iterable[bool]:
        """Iterate over the bits."""
        return iter(self._bitstore)

    def __len__(self) -> int:
        """Return the length of the Bits in bits."""
        return len(self._bitstore)


Sequence.register(Bits)