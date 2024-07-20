from __future__ import annotations

import numbers
import sys
import struct
import io
import re
import functools
from collections import abc
from typing import Union, Iterable, Any, TextIO, overload, Iterator, Type
import bitformat
from ._bitstore import BitStore
from bitformat import _utils
from bitformat._dtypes import Dtype, dtype_register
from bitformat._common import colour
from typing import Pattern, Callable

__all__ = ['Bits']

# Things that can be converted to Bits when a Bits type is needed
BitsType = Union['Bits', str, Iterable[Any], bytearray, bytes, memoryview]

# Maximum number of digits to use in __str__ and __repr__.
MAX_CHARS: int = 256

# name[length][=value]
NAME_INT_VALUE_RE: Pattern[str] = re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*?)(\d*)(?:=(.*))?$')

# The size of various caches used to improve performance
CACHE_SIZE = 256

literal_bit_funcs: dict[str, Callable[..., BitStore]] = {
    'x': BitStore.from_hex,
    'X': BitStore.from_hex,
    'b': BitStore.from_bin,
    'B': BitStore.from_bin,
    'o': BitStore.from_oct,
    'O': BitStore.from_oct,
}


@functools.lru_cache(CACHE_SIZE)
def parse_single_token(token: str) -> tuple[str, int, str | None]:
    match = NAME_INT_VALUE_RE.match(token)
    if not match:
        raise ValueError(f"Can't parse token '{token}'. It should be in the form 'name[length][=value]'.")
    name, length_str, value = match.groups()
    length = int(length_str) if length_str else 0
    value = None if value == '' else value
    return name, length, value


@functools.lru_cache(CACHE_SIZE)
def str_to_bitstore(s: str) -> BitStore:
    s = ''.join(s.split())  # Remove whitespace
    bsl = []
    for token in (t for t in s.split(',') if t):
        if token.startswith(('0x', '0X', '0b', '0B', '0o', '0O')):
            bsl.append(literal_bit_funcs[token[1]](token[2:]))
        else:
            name, length, value = parse_single_token(token)
            bsl.append(Dtype(name, length).pack(value)._bitstore)
    return BitStore.join(bsl)


class Bits:
    """
    An immutable container of binary data.

    To construct use a builder method.
    ``Bits(s)`` is equivalent to ``Bits.from_string(s)``.

    * ``Bits.from_string(s)`` - Use a formatted string.
    * ``Bits.from_bytes(b)`` - Directly from a ``bytes`` object.
    * ``Bits.from_iterable(i)`` - Convert each element to a bool.
    * ``Bits.zeros(n)`` - Initialise with ``n`` zero bits.
    * ``Bits.ones(n)`` - Initialise with ``n`` one bits.
    * ``Bits.pack(dtype, value)`` - Combine a data type with a value.
    * ``Bits.join(iterable)`` - Concatenate an iterable of ``Bits`` objects.
    """

    __slots__ = ('_bitstore',)

    def __new__(cls, s: str | None = None, /) -> Bits:
        x = super().__new__(cls)
        if s is None:
            x._bitstore = BitStore()
        else:
            x._bitstore = str_to_bitstore(s)
        return x

    # ----- Class Methods -----

    @classmethod
    def from_string(cls, s: str, /) -> Bits:
        """Create a new Bits from a formatted string."""
        x = super().__new__(cls)
        x._bitstore = str_to_bitstore(s)
        return x

    @classmethod
    def from_bytes(cls, b: bytes, /) -> Bits:
        """Create a new Bits from a bytes object."""
        x = super().__new__(cls)
        x._bitstore = BitStore.from_bytes(b)
        return x

    @classmethod
    def from_iterable(cls, i: Iterable[Any], /) -> Bits:
        """Create a new Bits from an iterable by converting each element to a bool."""
        x = super().__new__(cls)
        x._bitstore = BitStore.from_binstr(''.join('1' if x else '0' for x in i))
        return x

    @classmethod
    def zeros(cls, n: int, /) -> Bits:
        """Create a new Bits with all bits set to zero.

        n -- The number of bits.

        """
        if n == 0:
            return Bits()
        x = super().__new__(cls)
        x._bitstore = BitStore.from_zeros(n)
        return x

    @classmethod
    def ones(cls, n: int, /) -> Bits:
        """Create a new Bits with all bits set to one.

        n -- The number of bits.

        """
        if n == 0:
            return Bits()
        x = super().__new__(cls)
        x._bitstore = BitStore.from_ones(n)
        return x

    @classmethod
    def pack(cls, dtype: Dtype | str, value: Any, /) -> Bits:
        """
        :param dtype: The data type to pack.
        :type dtype: Dtype | str
        :param value: A value appropriate for the data type.
        :type value: Any
        :returns: A newly constructed ``Bits``.
        :rtype: Bits
        """
        if isinstance(dtype, str):
            dtype = Dtype.from_string(dtype)
        return dtype.pack(value)

    @classmethod
    def join(cls, sequence: Iterable[Any], /) -> Bits:
        """Return concatenation of Bits.

        sequence -- A sequence of Bits.

        """
        x = super().__new__(cls)
        x._bitstore = BitStore()
        for item in sequence:
            x._addright(Bits._create_from_bitstype(item))
        return x

    # ----- Private Class Methods -----

    @classmethod
    def _create_from_bitstype(cls: Type[Bits], auto: BitsType, /) -> Bits:
        """Create a new Bits from one of the many things that can be a BitsType."""
        if isinstance(auto, cls):
            return auto
        if isinstance(auto, str):
            return cls.from_string(auto)
        elif isinstance(auto, (bytes, bytearray, memoryview)):
            return cls.from_bytes(auto)
        elif isinstance(auto, abc.Iterable):
            return cls.from_iterable(auto)
        raise TypeError(f"Cannot initialise Bits from type '{type(auto)}'.")

    # ----- Instance Methods -----

    def all(self) -> bool:
        """Return True if all bits are equal to 1, otherwise return False."""
        return self._bitstore.all_set()

    def any(self) -> bool:
        """Return True if any bits are equal to 1, otherwise return False."""
        return self._bitstore.any_set()

    def byteswap(self, bytelength: int | None = None, /) -> Bits:
        """Change the byte endianness. Return new Bits.

        bytelength: An int giving the number of bytes to swap.

        The whole of the Bits will be byte-swapped. It must be a multiple
        of bytelength long.

        """
        if len(self) % 8 != 0:
            raise ValueError(f"Bit length must be an multiple of 8 to use byteswap.")
        if bytelength is None:
            bytelength = len(self) // 8
        if bytelength == 0:
            return Bits()
        if bytelength < 0:
            raise ValueError(f"Negative bytelength given: {bytelength}.")
        if len(self) % (bytelength * 8) != 0:
            raise ValueError(f"The bits should be a whole number of bytelength bytes long.")
        chunks = []
        for startbit in range(0, len(self), bytelength * 8):
            x = self._slice_copy(startbit, startbit + bytelength * 8).to_bytes()
            chunks.append(Bits.from_bytes(x[::-1]))
        return Bits.join(chunks)

    def count(self, value: Any, /) -> int:
        """Return count of total number of either zero or one bits.

        value -- If bool(value) is True then bits set to 1 are counted, otherwise bits set
                 to 0 are counted.

        >>> Bits('0xef').count(1)
        7

        """
        # count the number of 1s (from which it's easy to work out the 0s).
        count = self._bitstore.count(1)
        return count if value else len(self) - count

    def cut(self, bits: int, start: int | None = None, end: int | None = None,
            count: int | None = None) -> Iterator[Bits]:
        """Return Bits generator by cutting into bits sized chunks.

        bits -- The size in bits of the Bits chunks to generate.
        start -- The bit position to start the first cut. Defaults to 0.
        end -- The bit position one past the last bit to use in the cut.
               Defaults to len(self).
        count -- If specified then at most count items are generated.
                 Default is to cut as many times as possible.

        """
        start_, end_ = self._validate_slice(start, end)
        if count is not None and count < 0:
            raise ValueError("Cannot cut - count must be >= 0.")
        if bits <= 0:
            raise ValueError("Cannot cut - bits must be >= 0.")
        c = 0
        while count is None or c < count:
            c += 1
            nextchunk = self._slice_copy(start_, min(start_ + bits, end_))
            if len(nextchunk) == 0:
                return
            yield nextchunk
            if len(nextchunk) != bits:
                return
            start_ += bits
        return

    def ends_with(self, suffix: BitsType, /, start: int | None = None, end: int | None = None) -> bool:
        """Return whether the current Bits ends with suffix.

        suffix -- The Bits to search for.
        start -- The bit position to start from. Defaults to 0.
        end -- The bit position to end at. Defaults to len(self).

        """
        suffix = self._create_from_bitstype(suffix)
        start, end = self._validate_slice(start, end)
        return self._slice_copy(end - len(suffix), end) == suffix if start + len(suffix) <= end else False

    def find(self, bs: BitsType, /, start: int | None = None, end: int | None = None,
             bytealigned: bool | None = None) -> int | None:
        """Find first occurrence of substring bs.

        Returns a the bit position if found, or None if not found.

        bs -- The Bits to find.
        start -- The bit position to start the search. Defaults to 0.
        end -- The bit position one past the last bit to search.
               Defaults to len(self).
        bytealigned -- If True the Bits will only be
                       found on byte boundaries.

        Raises ValueError if bs is empty, if start < 0, if end > len(self) or
        if end < start.

        >>> Bits.from_string('0xc3e').find('0b1111')
        6

        """
        bs = Bits._create_from_bitstype(bs)
        if len(bs) == 0:
            raise ValueError("Cannot find an empty Bits.")
        start, end = self._validate_slice(start, end)
        ba = bitformat.options.bytealigned if bytealigned is None else bytealigned
        p = self._bitstore.find(bs._bitstore, start, end, ba)
        return None if p == -1 else p

    def find_all(self, bs: BitsType, start: int | None = None, end: int | None = None, count: int | None = None,
                 bytealigned: bool | None = None) -> Iterable[int]:
        """Find all occurrences of bs. Return generator of bit positions.

        bs -- The Bits to find.
        start -- The bit position to start the search. Defaults to 0.
        end -- The bit position one past the last bit to search.
               Defaults to len(self).
        count -- The maximum number of occurrences to find.
        bytealigned -- If True the Bits will only be found on
                       byte boundaries.

        Raises ValueError if bs is empty, if start < 0, if end > len(self) or
        if end < start.

        Note that all occurrences of bs are found, even if they overlap.

        """
        if count is not None and count < 0:
            raise ValueError("In findall, count must be >= 0.")
        bs = Bits._create_from_bitstype(bs)
        start, end = self._validate_slice(start, end)
        ba = bitformat.options.bytealigned if bytealigned is None else bytealigned
        return self._findall(bs, start, end, count, ba)

    def insert(self, pos: int, bs: BitsType, /) -> Bits:
        """Return new Bits with bs inserted at bit position pos.

        pos -- The bit position to insert at.
        bs -- The Bits to insert.

        Raises ValueError if pos < 0 or pos > len(self).

        """
        bs = self._create_from_bitstype(bs)
        if pos < 0:
            pos += len(self)
        if pos < 0 or pos > len(self):
            raise ValueError("Overwrite starts outside boundary of Bits.")
        return Bits.join([self._slice_copy(0, pos), bs, self._slice_copy(pos, len(self))])

    def invert(self, pos: Iterable[int] | int | None = None) -> Bits:
        """Return new Bits with one or many bits inverted between 0 and 1.

        pos -- Either a single bit position or an iterable of bit positions.
               Negative numbers are treated in the same way as slice indices.

        Raises IndexError if pos < -len(self) or pos >= len(self).

        """
        s = self._copy()
        if pos is None:
            s._invert_all()
            return s
        if not isinstance(pos, abc.Iterable):
            pos = (pos,)
        length = len(self)

        for p in pos:
            if p < 0:
                p += length
            if not 0 <= p < length:
                raise IndexError(f"Bit position {p} out of range.")
            s._invert(p)
        return s

    def overwrite(self, pos: int, bs: BitsType, /) -> Bits:
        """Return new Bits with bs overwritten at bit position pos.

        pos -- The bit position to start overwriting at.
        bs -- The Bits to overwrite.

        Raises ValueError if pos < 0 or pos > len(self).

        """
        bs = self._create_from_bitstype(bs)
        if pos < 0:
            pos += len(self)
        if pos < 0 or pos > len(self):
            raise ValueError("Overwrite starts outside boundary of Bits.")
        return Bits.join([self._slice_copy(0, pos), bs, self._slice_copy(pos + len(bs), len(self))])

    def pp(self, fmt: str | None = None, width: int = 120, sep: str = ' ',
           show_offset: bool = True, stream: TextIO = sys.stdout) -> None:
        """Pretty print the Bits's value.

        fmt -- Printed data format. One or two of 'bin', 'oct', 'hex' or 'bytes'.
              The number of bits represented in each printed group defaults to 8 for hex and bin,
              12 for oct and 32 for bytes. This can be overridden with an explicit length, e.g. 'hex:64'.
              Use a length of 0 to not split into groups, e.g. `bin:0`.
        width -- Max width of printed lines. Defaults to 120. A single group will always be printed
                 per line even if it exceeds the max width.
        sep -- A separator string to insert between groups. Defaults to a single space.
        show_offset -- If True (the default) shows the bit offset in the first column of each line.
        stream -- A TextIO object with a write() method. Defaults to sys.stdout.

        >>> s.pp('hex16')
        >>> s.pp('bin, hex', sep='_', show_offset=False)

        """
        if fmt is None:
            fmt = 'bin, hex' if len(self) % 8 == 0 and len(self) >= 8 else 'bin'
        token_list = [token.strip() for token in fmt.split(',')]
        dtype1, dtype2, bits_per_group, has_length_in_fmt = Bits._process_pp_tokens(token_list, fmt)
        trailing_bit_length = len(self) % bits_per_group if has_length_in_fmt and bits_per_group else 0
        data = self if trailing_bit_length == 0 else self[0: -trailing_bit_length]
        format_sep = " : "  # String to insert on each line between multiple formats
        tidy_fmt = colour.purple + str(dtype1) + colour.off
        if dtype2 is not None:
            tidy_fmt += ', ' + colour.blue + str(dtype2) + colour.off
        output_stream = io.StringIO()
        len_str = colour.green + str(len(self)) + colour.off
        output_stream.write(f"<{self.__class__.__name__}, fmt='{tidy_fmt}', length={len_str} bits> [\n")
        data._pp(dtype1, dtype2, bits_per_group, width, sep, format_sep, show_offset,
                 output_stream, 1)
        output_stream.write("]")
        if trailing_bit_length != 0:
            output_stream.write(" + trailing_bits = 0b" + self[-trailing_bit_length:].bin)
        output_stream.write("\n")
        stream.write(output_stream.getvalue())
        return

    def replace(self, old: BitsType, new: BitsType, /, start: int | None = None, end: int | None = None,
                count: int | None = None, bytealigned: bool | None = None) -> Bits:
        """Return new Bits with all occurrences of old replaced with new.

        old -- The Bits to replace.
        new -- The replacement Bits.
        start -- Any occurrences that start before this will not be replaced.
                 Defaults to 0.
        end -- Any occurrences that finish after this will not be replaced.
               Defaults to len(self).
        count -- The maximum number of replacements to make. Defaults to
                 replace all occurrences.
        bytealigned -- If True replacements will only be made on byte
                       boundaries.

        Raises ValueError if old is empty or if start or end are
        out of range.

        """
        s = self._copy()
        if count == 0:
            return s
        old = self._create_from_bitstype(old)
        new = self._create_from_bitstype(new)
        if len(old) == 0:
            raise ValueError("Empty Bits cannot be replaced.")
        start, end = self._validate_slice(start, end)

        if new is self:
            # Prevent self assignment woes
            new = self._copy()
        if bytealigned is None:
            bytealigned = bitformat.options.bytealigned
        # First find all the places where we want to do the replacements
        starting_points: list[int] = []
        for x in self.find_all(old, start, end, bytealigned=bytealigned):
            if not starting_points:
                starting_points.append(x)
            elif x >= starting_points[-1] + len(old):
                # Can only replace here if it hasn't already been replaced!
                starting_points.append(x)
            if count != 0 and len(starting_points) == count:
                break
        if not starting_points:
            return s
        replacement_list = [s._bitstore.getslice(0, starting_points[0])]
        for i in range(len(starting_points) - 1):
            replacement_list.append(new._bitstore)
            replacement_list.append(
                s._bitstore.getslice(starting_points[i] + len(old), starting_points[i + 1]))
        # Final replacement
        replacement_list.append(new._bitstore)
        replacement_list.append(s._bitstore.getslice(starting_points[-1] + len(old), None))
        s._bitstore.clear()
        for r in replacement_list:
            s._bitstore += r
        return s

    def reverse(self, start: int | None = None, end: int | None = None) -> Bits:
        """Reverse bits.

        start -- Position of first bit to reverse. Defaults to 0.
        end -- One past the position of the last bit to reverse.
               Defaults to len(self).

        Using on an empty Bits will have no effect.

        Raises ValueError if start < 0, end > len(self) or end < start.

        """
        start, end = self._validate_slice(start, end)
        s = self._slice_copy(start, end)
        s._bitstore.reverse()
        return Bits.join([self._slice_copy(0, start) + s + self._slice_copy(end, len(self))])

    def rfind(self, bs: BitsType, /, start: int | None = None, end: int | None = None,
              bytealigned: bool | None = None) -> int | None:
        """Find final occurrence of substring bs.

        Returns a the bit position if found, or None if not found.

        bs -- The Bits to find.
        start -- The bit position to end the reverse search. Defaults to 0.
        end -- The bit position one past the first bit to reverse search.
               Defaults to len(self).
        bytealigned -- If True the Bits will only be found on byte
                       boundaries.

        Raises ValueError if bs is empty, if start < 0, if end > len(self) or
        if end < start.

        """
        bs = Bits._create_from_bitstype(bs)
        start, end = self._validate_slice(start, end)
        ba = bitformat.options.bytealigned if bytealigned is None else bytealigned
        if len(bs) == 0:
            raise ValueError("Cannot find an empty Bits.")
        p = self._bitstore.rfind(bs._bitstore, start, end, ba)
        return None if p == -1 else p

    def rol(self, n: int, /, start: int | None = None, end: int | None = None) -> Bits:
        """Return new Bits with bit pattern rotated to the left.

        n -- The number of bits to rotate by.
        start -- Start of slice to rotate. Defaults to 0.
        end -- End of slice to rotate. Defaults to len(self).

        Raises ValueError if bits < 0.

        """
        if not len(self):
            raise ValueError("Cannot rotate an empty Bits.")
        if n < 0:
            raise ValueError("Cannot rotate by negative amount.")
        start, end = self._validate_slice(start, end)
        n %= (end - start)
        return Bits.join([self._slice_copy(0, start), self._slice_copy(start + n, end),
                          self._slice_copy(start, start + n), self._slice_copy(end, len(self))])

    def ror(self, n: int, /, start: int | None = None, end: int | None = None) -> Bits:
        """Return new Bits with bit pattern rotated to the right.

        n -- The number of bits to rotate by.
        start -- Start of slice to rotate. Defaults to 0.
        end -- End of slice to rotate. Defaults to len(self).

        Raises ValueError if bits < 0.

        """
        if len(self) == 0:
            raise ValueError("Cannot rotate an empty Bits.")
        if n < 0:
            raise ValueError("Cannot rotate by negative amount.")
        start, end = self._validate_slice(start, end)
        n %= (end - start)
        return Bits.join([self._slice_copy(0, start), self._slice_copy(end - n, end),
                          self._slice_copy(start, end - n), self._slice_copy(end, len(self))])

    def set(self, value: Any, pos: int | Iterable[int] | None = None) -> Bits:
        """Return new Bits with one or many bits set to 1 or 0.

        value -- If bool(value) is True bits are set to 1, otherwise they are set to 0.
        pos -- Either a single bit position or an iterable of bit positions.
               Negative numbers are treated in the same way as slice indices.
               Defaults to the entire Bits.

        Raises IndexError if pos < -len(self) or pos >= len(self).

        """
        s = self._copy()
        if pos is None:
            # Set all bits to either 1 or 0
            v = -1 if value else 0
            s._bitstore = BitStore.from_int(v, len(self), True)
            return s
        if not isinstance(pos, abc.Iterable):
            pos = (pos,)
        v = 1 if value else 0
        if isinstance(pos, range):
            s._bitstore.setitem(slice(pos.start, pos.stop, pos.step), v)
            return s
        for p in pos:
            s._bitstore.setitem(p, v)
        return s

    def starts_with(self, prefix: BitsType, start: int | None = None, end: int | None = None) -> bool:
        """Return whether the current Bits starts with prefix.

        prefix -- The Bits to search for.
        start -- The bit position to start from. Defaults to 0.
        end -- The bit position to end at. Defaults to len(self).

        """
        prefix = self._create_from_bitstype(prefix)
        start, end = self._validate_slice(start, end)
        return self._slice_copy(start, start + len(prefix)) == prefix if end >= start + len(prefix) else False

    def to_bytes(self) -> bytes:
        """Return the Bits as bytes, padding with zero bits if needed.

        Up to seven zero bits will be added at the end to byte align.

        """
        return self._bitstore.to_bytes()

# TODO: Allow the fmt to be a single array-like Dtype. Or I guess any single type.
    def unpack(self, fmt: list[Dtype | str], /) -> list[Any]:
        """Interpret the Bits as a given data type."""
        dtypes = []
        for i in fmt:
            if isinstance(i, str):
                for x in i.split(','):
                    d = Dtype.from_string(x)
                    dtypes.append(d)
            else:
                dtypes.append(i)
        if len(dtypes) == 1:
            if dtypes[0].name == 'pad':
                return []
            else:
                return [dtypes[0].unpack(self)]
        pos = 0
        ret_val = []
        for dtype in dtypes:
            if dtype.name != 'pad':
                ret_val.append(dtype.unpack(self._slice_copy(pos, pos + dtype.length)))
            pos += dtype.length
        return ret_val

    # ----- Private Methods -----

    def _findall(self, bs: Bits, start: int, end: int, count: int | None,
                 bytealigned: bool) -> Iterable[int]:
        c = 0
        for i in self._bitstore.findall(bs._bitstore, start, end, bytealigned):
            if count is not None and c >= count:
                return
            c += 1
            yield i
        return

    def _str_interpretations(self) -> list[str]:
        length = len(self)
        if length == 0:
            return []
        hex_str = bin_str = f_str = u_str = i_str = ''
        if length % 4 == 0:
            t = self.hex
            with_underscores = '_'.join(t[x: x + 4] for x in range(0, len(t), 4))
            hex_str = f'hex == {with_underscores}'
        if length <= 64:
            t = self.bin
            with_underscores = '_'.join(t[x: x + 4] for x in range(0, len(t), 4))
            bin_str = f'bin == {with_underscores}'
            u_str = f'u{length} == {self.u:_}'
            i_str = f'i{length} == {self.i:_}'
        if length in dtype_register['f'].allowed_lengths:
            f_str = f'f{length} == {self.f}'
        return [hex_str, bin_str, u_str, i_str, f_str]

    def _setbits(self, bs: BitsType, length: None = None) -> None:
        bs = Bits._create_from_bitstype(bs)
        self._bitstore = bs._bitstore

    def _setbytes(self, data: bytearray | bytes | list, length: None = None) -> None:
        """Set the data from a bytes or bytearray object."""
        self._bitstore = BitStore.from_bytes(bytes(data))

    def _getbytes(self) -> bytes:
        """Return the data as an ordinary bytes object."""
        if len(self) % 8:
            raise ValueError(f"Cannot interpret as bytes - length of {len(self)} not a multiple of 8 bits.")
        return self._bitstore.to_bytes()

    _unprintable = list(range(0x00, 0x20))  # ASCII control characters
    _unprintable.extend(range(0x7f, 0xff))  # DEL char + non-ASCII

    def _getbytes_printable(self) -> str:
        """Return an approximation of the data as a string of printable characters."""
        bytes_ = self._getbytes()
        # For everything that isn't printable ASCII, use value from 'Latin Extended-A' unicode block.
        string = ''.join(chr(0x100 + x) if x in Bits._unprintable else chr(x) for x in bytes_)
        return string

    def _setuint(self, uint: int, length: int | None = None) -> None:
        """Reset the Bits to have given unsigned int interpretation."""
        if length is None or length == 0:
            raise ValueError("A non-zero length must be specified with a uint initialiser.")
        self._bitstore = BitStore.from_int(uint, length, False)

    def _getuint(self) -> int:
        """Return data as an unsigned int."""
        if len(self) == 0:
            raise ValueError("Cannot interpret empty Bits as an integer.")
        return self._bitstore.slice_to_uint()

    def _setint(self, int_: int, length: int | None = None) -> None:
        """Reset the Bits to have given signed int interpretation."""
        if length is None or length == 0:
            raise ValueError("A non-zero length must be specified with an int initialiser.")
        self._bitstore = BitStore.from_int(int_, length, True)

    def _getint(self) -> int:
        """Return data as a two's complement signed int."""
        if len(self) == 0:
            raise ValueError("Cannot interpret empty Bits as an integer.")
        return self._bitstore.slice_to_int()

    def _setfloat(self, f: float, length: int | None) -> None:
        self._bitstore = BitStore.from_float(f, length)

    def _getfloat(self) -> float:
        """Interpret the whole Bits as a big-endian float."""
        fmt = {16: '>e', 32: '>f', 64: '>d'}[len(self)]
        return struct.unpack(fmt, self._bitstore.to_bytes())[0]

    def _setbool(self, value: bool | str) -> None:
        # We deliberately don't want to have implicit conversions to bool here.
        # If we did then it would be difficult to deal with the 'False' string.
        match value:
            case 1 | 'True' | '1':
                self._bitstore = BitStore.from_binstr('1')
            case 0 | 'False' | '0':
                self._bitstore = BitStore.from_binstr('0')
            case _:
                raise ValueError(f"Cannot initialise boolean with {value}.")

    def _getbool(self) -> bool:
        return self[0]

    def _getpad(self) -> None:
        return None

    def _setpad(self, value: None, length: int) -> None:
        self._bitstore = BitStore.from_zeros(length)

    def _setbin_safe(self, binstring: str, length: None = None) -> None:
        """Reset the Bits to the value given in binstring."""
        self._bitstore = BitStore.from_bin(binstring)

    def _getbin(self) -> str:
        """Return interpretation as a binary string."""
        return self._bitstore.slice_to_bin()

    def _setoct(self, octstring: str, length: None = None) -> None:
        """Reset the Bits to have the value given in octstring."""
        self._bitstore = BitStore.from_oct(octstring)

    def _getoct(self) -> str:
        """Return interpretation as an octal string."""
        return self._bitstore.slice_to_oct()

    def _sethex(self, hexstring: str, length: None = None) -> None:
        """Reset the Bits to have the value given in hexstring."""
        self._bitstore = BitStore.from_hex(hexstring)

    def _gethex(self) -> str:
        """Return the hexadecimal representation as a string.

        Raises an InterpretError if the Bits's length is not a multiple of 4.

        """
        return self._bitstore.slice_to_hex()

    def _copy(self: Bits) -> Bits:
        """Create and return a new copy of the Bits (always in memory)."""
        # Note that __copy__ may choose to return self if it's immutable. This method always makes a copy.
        s_copy = self.__class__()
        s_copy._bitstore = self._bitstore._copy()
        return s_copy

    def _slice_copy(self: Bits, start: int, end: int) -> Bits:
        """Used internally to get a copy of a slice, without error checking."""
        bs = self.__class__()
        bs._bitstore = self._bitstore.getslice(start, end)
        return bs

    def _addright(self, bs: Bits, /) -> None:
        """Add a Bits to the RHS of the current Bits."""
        self._bitstore += bs._bitstore

    def _invert(self, pos: int, /) -> None:
        """Flip bit at pos 1<->0."""
        assert 0 <= pos < len(self)
        self._bitstore.invert(pos)

    def _invert_all(self) -> None:
        """Invert every bit."""
        self._bitstore.invert()

    def _imul(self, n: int, /) -> Bits:
        """Concatenate n copies of self in place. Return self."""
        assert n > 0
        m = 1
        old_len = len(self)
        # Keep doubling the length for as long as we can
        while m * 2 < n:
            self._addright(self)
            m *= 2
        # Then finish off with the remaining copies
        self._addright(self[0:(n - m) * old_len])
        return self

    def _getbits(self: Bits):
        return self._copy()

    def _validate_slice(self, start: int | None, end: int | None) -> tuple[int, int]:
        """Validate start and end and return them as positive bit positions."""
        start = 0 if start is None else (start + len(self) if start < 0 else start)
        end = len(self) if end is None else (end + len(self) if end < 0 else end)
        if not 0 <= start <= end <= len(self):
            raise ValueError(f"Invalid slice positions for Bits length {len(self)}: start={start}, end={end}.")
        return start, end

    def _simple_str(self) -> str:
        length = len(self)
        if length == 0:
            s = ''
        elif length % 4 == 0:
            s = '0x' + self.hex
        else:
            s = '0b' + self.bin
        return s

    @staticmethod
    def _format_bits(bits: Bits, bits_per_group: int, sep: str, dtype: Dtype,
                     colour_start: str, colour_end: str, width: int | None = None) -> tuple[str, int]:
        get_fn = dtype.get_fn
        if dtype.name == 'bytes':  # Special case for bytes to print one character each.
            get_fn = Bits._getbytes_printable
        if dtype.name == 'bool':  # Special case for bool to print '1' or '0' instead of `True` or `False`.
            get_fn = dtype_register.get_dtype('uint', bits_per_group).get_fn
        if bits_per_group == 0:
            if dtype.name == 'bits':
                x = bits._simple_str()
            else:
                x = str(get_fn(bits))
        else:
            align = '<' if dtype.name in ['bin', 'oct', 'hex', 'bits', 'bytes'] else '>'
            chars_per_group = 0
            if dtype_register[dtype.name].bitlength2chars_fn is not None:
                chars_per_group = dtype_register[dtype.name].bitlength2chars_fn(bits_per_group)
            if dtype.name == 'bits':
                x = sep.join(f"{b._simple_str(): {align}{chars_per_group}}" for b in bits.cut(bits_per_group))
            else:
                x = sep.join(f"{str(get_fn(b)): {align}{chars_per_group}}" for b in bits.cut(bits_per_group))

        chars_used = len(x)
        padding_spaces = 0 if width is None else max(width - len(x), 0)
        x = colour_start + x + colour_end
        # Pad final line with spaces to align it
        x += ' ' * padding_spaces
        return x, chars_used

    @staticmethod
    def _chars_per_group(bits_per_group: int, fmt: str | None):
        """How many characters are needed to represent a number of bits with a given format."""
        if fmt is None or dtype_register[fmt].bitlength2chars_fn is None:
            return 0
        return dtype_register[fmt].bitlength2chars_fn(bits_per_group)

    @staticmethod
    def _bits_per_char(fmt: str):
        """How many bits are represented by each character of a given format."""
        if fmt not in ['bin', 'oct', 'hex', 'bytes']:
            raise ValueError
        return 24 // dtype_register[fmt].bitlength2chars_fn(24)

    def _pp(self, dtype1: Dtype, dtype2: Dtype | None, bits_per_group: int, width: int, sep: str, format_sep: str,
            show_offset: bool, stream: TextIO, offset_factor: int) -> None:
        """Internal pretty print method."""
        name1 = dtype1.name
        name2 = dtype2.name if dtype2 is not None else None
        offset_width = 0
        offset_sep = ': '
        if show_offset:
            # This could be 1 too large in some circumstances. Slightly recurrent logic needed to fix it...
            offset_width = len(str(len(self))) + len(offset_sep)
        if bits_per_group > 0:
            group_chars1 = Bits._chars_per_group(bits_per_group, name1)
            group_chars2 = Bits._chars_per_group(bits_per_group, name2)
            # The number of characters that get added when we add an extra group (after the first one)
            total_group_chars = group_chars1 + group_chars2 + len(sep) + len(sep) * bool(group_chars2)
            width_excluding_offset_and_final_group = width - offset_width - group_chars1 - group_chars2 - len(
                format_sep) * bool(group_chars2)
            width_excluding_offset_and_final_group = max(width_excluding_offset_and_final_group, 0)
            groups_per_line = 1 + width_excluding_offset_and_final_group // total_group_chars
            max_bits_per_line = groups_per_line * bits_per_group  # Number of bits represented on each line
        else:
            assert bits_per_group == 0  # Don't divide into groups
            width_available = width - offset_width - len(format_sep) * (name2 is not None)
            width_available = max(width_available, 1)
            if name2 is None:
                max_bits_per_line = width_available * Bits._bits_per_char(name1)
            else:
                chars_per_24_bits = dtype_register[name1].bitlength2chars_fn(24) + dtype_register[name2].bitlength2chars_fn(24)
                max_bits_per_line = 24 * (width_available // chars_per_24_bits)
                if max_bits_per_line == 0:
                    max_bits_per_line = 24  # We can't fit into the width asked for. Show something small.
        assert max_bits_per_line > 0

        bitpos = 0
        first_fb_width = second_fb_width = None
        for bits in self.cut(max_bits_per_line):
            offset_str = ''
            if show_offset:
                offset = bitpos // offset_factor
                bitpos += len(bits)
                offset_str = colour.green + f'{offset: >{offset_width - len(offset_sep)}}' + offset_sep + colour.off

            fb1, chars_used = Bits._format_bits(bits, bits_per_group, sep, dtype1, colour.purple, colour.off, first_fb_width)
            if first_fb_width is None:
                first_fb_width = chars_used

            fb2 = ''
            if dtype2 is not None:
                fb2, chars_used = Bits._format_bits(bits, bits_per_group, sep, dtype2, colour.blue, colour.off, second_fb_width)
                if second_fb_width is None:
                    second_fb_width = chars_used
                fb2 = format_sep + fb2

            line_fmt = offset_str + fb1 + fb2 + '\n'
            stream.write(line_fmt)
        return

    @staticmethod
    def _process_pp_tokens(token_list, fmt):
        if len(token_list) not in [1, 2]:
            raise ValueError(
                f"Only one or two tokens can be used in an pp() format - '{fmt}' has {len(token_list)} tokens.")
        has_length_in_fmt = True
        name1, length1 = _utils.parse_name_length_token(token_list[0])
        dtype1 = Dtype(name1, length1)
        bits_per_group = dtype1.bitlength
        dtype2 = None

        if len(token_list) == 2:
            name2, length2 = _utils.parse_name_length_token(token_list[1])
            dtype2 = Dtype(name2, length2)
            if 0 not in {dtype1.bitlength, dtype2.bitlength} and dtype1.bitlength != dtype2.bitlength:
                raise ValueError(
                    f"Differing bit lengths of {dtype1.bitlength} and {dtype2.bitlength} in format string '{fmt}'.")
            if bits_per_group == 0:
                bits_per_group = dtype2.bitlength

        if bits_per_group == 0:
            has_length_in_fmt = False
            if len(token_list) == 1:
                bits_per_group = {'bin': 8, 'hex': 8, 'oct': 12, 'bytes': 32}.get(dtype1.name)
                if bits_per_group == 0:
                    raise ValueError(f"No length or default length available for pp() format '{fmt}'.")
            else:
                try:
                    bits_per_group = 2 * Bits._bits_per_char(dtype1.name) * Bits._bits_per_char(dtype2.name)
                except ValueError:
                    raise ValueError(f"Can't find a default bitlength to use for pp() format '{fmt}'.")
                if bits_per_group >= 24:
                    bits_per_group //= 2
        return dtype1, dtype2, bits_per_group, has_length_in_fmt

    # ----- Special Methods -----

    # ----- Logical
    def __and__(self: Bits, bs: BitsType, /) -> Bits:
        """Bit-wise 'and' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        if bs is self:
            return self
        bs = Bits._create_from_bitstype(bs)
        s = object.__new__(self.__class__)
        s._bitstore = self._bitstore & bs._bitstore
        return s

    def __or__(self: Bits, bs: BitsType, /) -> Bits:
        """Bit-wise 'or' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        if bs is self:
            return self
        bs = Bits._create_from_bitstype(bs)
        s = object.__new__(self.__class__)
        s._bitstore = self._bitstore | bs._bitstore
        return s

    def __xor__(self: Bits, bs: BitsType, /) -> Bits:
        """Bit-wise 'xor' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        bs = Bits._create_from_bitstype(bs)
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
        """Return string representations of Bits for printing.

        Very long strings will be truncated with '...'.

        """
        length = len(self)
        if length == 0:
            return ''
        if length > MAX_CHARS * 4:
            # Too long for hex. Truncate...
            return '0x' + self[0:MAX_CHARS*4].hex + f'...  # {length} bits'
        return self._simple_str()

    def __repr__(self) -> str:
        """Return representation that could be used to recreate the Bits..

        """
        interpretations = '\n'.join('# ' + x for x in self._str_interpretations() if x != '')
        repr_ = f"{self.__class__.__name__}('{self._simple_str()}')"
        return f"{repr_}\n{interpretations}" if interpretations else repr_

    # ----- Comparisons

    def __eq__(self, bs: Any, /) -> bool:
        """Return True if two Bits have the same binary representation.

        >>> Bits('0b1110') == '0xe'
        True

        """
        try:
            return self._bitstore == Bits._create_from_bitstype(bs)._bitstore
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

        >>> Bits('0b111') == '0x7'
        False

        """
        return not self.__eq__(bs)

    # ----- Operators

    def __add__(self: Bits, bs: BitsType, /) -> Bits:
        """Concatenate Bits and return a new Bits."""
        bs = self.__class__._create_from_bitstype(bs)
        s = self._copy()
        s._addright(bs)
        return s

    @overload
    def __getitem__(self: Bits, key: slice, /) -> Bits:
        ...

    @overload
    def __getitem__(self, key: int, /) -> bool:
        ...

    def __getitem__(self: Bits, key: slice | int, /) -> Bits | bool:
        """Return a new Bits representing a slice of the current Bits.
        """
        if isinstance(key, numbers.Integral):
            return bool(self._bitstore.getindex(key))
        bs = super().__new__(self.__class__)
        bs._bitstore = self._bitstore.getslice_withstep(key)
        return bs

    def __invert__(self: Bits) -> Bits:
        """Return the Bits with every bit inverted.

        Raises Error if the Bits is empty.

        """
        if len(self) == 0:
            raise ValueError("Cannot invert empty Bits.")
        s = self._copy()
        s._invert_all()
        return s

    def __lshift__(self: Bits, n: int, /) -> Bits:
        """Return Bits shifted by n to the left.

        n -- the number of bits to shift. Must be >= 0.

        """
        if n < 0:
            raise ValueError("Cannot shift by a negative amount.")
        if len(self) == 0:
            raise ValueError("Cannot shift an empty Bits.")
        n = min(n, len(self))
        s = self._slice_copy(n, len(self))
        s._addright(Bits.zeros(n))
        return s

    def __mul__(self: Bits, n: int, /) -> Bits:
        """Return new Bits consisting of n concatenations of self.

        Called for expression of the form 'a = b*3'.
        n -- The number of concatenations. Must be >= 0.

        """
        if n < 0:
            raise ValueError("Cannot multiply by a negative integer.")
        if n == 0:
            return self.__class__()
        s = self._copy()
        s._imul(n)
        return s

    def __radd__(self: Bits, bs: BitsType, /) -> Bits:
        """Concatenate Bits and return a new Bits."""
        bs = self.__class__._create_from_bitstype(bs)
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
        if not n:
            return self._copy()
        s = self.__class__.zeros(min(n, len(self)))
        n = min(n, len(self))
        s._addright(self._slice_copy(0, len(self) - n))
        return s

    # ----- Other

    def __contains__(self, bs: BitsType, /) -> bool:
        """Return whether bs is contained in the current Bits.

        bs -- The Bits to search for.

        """
        found = Bits.find(self, bs, bytealigned=False)
        return False if found is None else True

    def __copy__(self: Bits) -> Bits:
        """Return a new copy of the Bits for the copy module.

        Note that if you want a new copy (different ID), use _copy instead.
        This copy will return self as it's immutable.

        """
        return self

    def __hash__(self) -> int:
        """Return an integer hash of the object."""
        # Only requirement is that equal Bits should return the same hash.
        # For equal Bits the bytes at the start/end will be the same and they will have the same length
        # (need to check the length as there could be zero padding when getting the bytes). We do not check any
        # bit position inside the Bits as that does not feature in the __eq__ operation.
        if len(self) <= 2000:
            # Use the whole Bits.
            return hash((self.to_bytes(), len(self)))
        else:
            # We can't in general hash the whole Bits (it could take hours!)
            # So instead take some bits from the start and end.
            return hash(((self._slice_copy(0, 800) + self._slice_copy(len(self) - 800, len(self))).to_bytes(), len(self)))

    def __iter__(self) -> Iterable[bool]:
        """Iterate over the bits."""
        return iter(self._bitstore)

    def __len__(self) -> int:
        """Return the length of the Bits in bits."""
        return len(self._bitstore)
