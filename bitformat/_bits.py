from __future__ import annotations

import numbers
import random
import sys
import io
from ast import literal_eval
from typing import Union, Iterable, Any, TextIO
from bitformat._dtypes import Dtype, DtypeSingle, Register, DtypeTuple, DtypeArray
from bitformat._common import Colour, DtypeKind
from bitformat._options import Options
from bitformat.rust import Bits, MutableBits, bits_from_any, mutable_bits_from_any
from collections.abc import Sequence

__all__ = ["Bits", "MutableBits", "BitsType"]

_unprintable = list(range(0x00, 0x20))  # ASCII control characters
_unprintable.extend(range(0x7F, 0xFF))  # DEL char + non-ASCII


# Things that can be converted to Bits or MutableBits.
BitsType = Union["Bits", "MutableBits", str, bytearray, bytes, memoryview]

# The size of various caches used to improve performance
CACHE_SIZE = 256


def _validate_slice(length: int, start: int | None, end: int | None) -> tuple[int, int]:
    """Validate start and end and return them as positive bit positions."""
    start = 0 if start is None else (start + length if start < 0 else start)
    end = length if end is None else (end + length if end < 0 else end)
    if not 0 <= start <= end <= length:
        raise ValueError(f"Invalid slice positions for Bits length {length}: start={start}, end={end}.")
    return start, end

def convert_bytes_to_printable(b: bytes) -> str:
    # For everything that isn't printable ASCII, use value from 'Latin Extended-A' unicode block.
    string = "".join(chr(0x100 + x) if x in _unprintable else chr(x) for x in b)
    return string


def format_bits(bits: Bits, bits_per_group: int, sep: str, dtype: Dtype, colour_start: str,
                colour_end: str, width: int | None = None) -> tuple[str, int]:
    get_fn = dtype.unpack
    chars_per_group = chars_per_dtype(dtype, bits_per_group)
    if isinstance(dtype, (DtypeSingle, DtypeArray)):
        n = dtype.kind
        if n is DtypeKind.BYTES:  # Special case for bytes to print one character each.
            get_fn = lambda b: convert_bytes_to_printable(b.bytes)
        elif n is DtypeKind.BOOL:  # Special case for bool to print '1' or '0' instead of `True` or `False`.
            get_fn = Register().get_single_dtype(DtypeKind.UINT, bits_per_group).unpack
        align = ">"
        if any(x is n for x in [DtypeKind.BIN, DtypeKind.OCT, DtypeKind.HEX, DtypeKind.BITS, DtypeKind.BYTES]):
            align = "<"
        if dtype.kind is DtypeKind.BITS:
            x = sep.join(f"{str(b): {align}{chars_per_group}}" for b in bits._chunks(bits_per_group))
        else:
            x = sep.join(f"{str(get_fn(b)): {align}{chars_per_group}}" for b in bits._chunks(bits_per_group))

        chars_used = len(x)
        padding_spaces = 0 if width is None else max(width - len(x), 0)
        x = colour_start + x + colour_end
        # Pad final line with spaces to align it
        x += " " * padding_spaces
        return x, chars_used
    else:  # DtypeTuple
        assert isinstance(dtype, DtypeTuple)
        align = ">"
        s = []
        for b in bits.chunks(bits_per_group):
            chars_per_dtype_list = [chars_per_dtype(d, d.bit_length) for d in dtype]
            values = get_fn(b)
            strings = [f"{str(v): {align}{c}}" for v, c in zip(values, chars_per_dtype_list)]
            s.append(f"[{', '.join(strings)}]")
        x = sep.join(s)
        chars_used = len(x)
        padding_spaces = 0 if width is None else max(width - len(x), 0)
        x = colour_start + x + colour_end
        # Pad final line with spaces to align it
        x += " " * padding_spaces
        return x, chars_used


def chars_per_dtype(dtype: Dtype, bits_per_group: int) -> int:
    """How many characters are needed to represent a number of bits with a given Dtype."""
    if isinstance(dtype, (DtypeSingle, DtypeArray)):
        # TODO: Not sure this is right for DtypeArray. Maybe needs a refactor?
        return Register().kind_to_def[dtype.kind].bitlength2chars_fn(bits_per_group)
    assert isinstance(dtype, DtypeTuple)
    # Start with '[' then add the number of characters for each element and add ', ' for each element, ending with a ']'.
    chars = sum(chars_per_dtype(d, bits_per_group) for d in dtype) + 2 + 2 * (dtype.items - 1)
    return chars


def process_pp_tokens(dtype1: Dtype, dtype2: Dtype | None) -> tuple[int, bool]:
    has_length_in_fmt = True
    bits_per_group: int = 0 if dtype1.bit_length is None else dtype1.bit_length

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


def dtype_token_to_bits(token: str) -> Bits:
    try:
        dtype_str, value_str = token.split("=", 1)
        dtype = Dtype.from_string(dtype_str)
    except ValueError:
        raise ValueError(f"Can't parse token '{token}'. It should be in the form 'kind[length][_endianness]=value' (e.g. "
                         "'u16_le = 44') or a literal starting with '0b', '0o' or '0x'.")
    if isinstance(dtype, DtypeSingle) and dtype._definition.return_type not in (bool, bytes):
        return dtype.pack(value_str)
    try:
        value = literal_eval(value_str)
    except ValueError:
        raise ValueError(f"Can't parse token '{token}'. The value '{value_str}' can't be converted to the appropriate type.")
    return dtype.pack(value)


class BaseBitsMethods:
    """Not a real class! This contains the common methods for Bits and MutableBits, and they
are monkey-patched into those classes later. Yes, it would be more normal to use inheritance, but
this is a step to using the Rust classes as the base classes."""
    # ----- Instance Methods -----


    def find(self, bs: BitsType, /, byte_aligned: bool | None = None) -> int | None:
        """
        Find first occurrence of substring bs.

        Returns the bit position if found, or None if not found.

        :param bs: The Bits to find.
        :param byte_aligned: If ``True``, the Bits will only be found on byte boundaries.
        :return: The bit position if found, or None if not found.

        .. code-block:: pycon

            >>> Bits.from_string('0xc3e').find('0b1111')
            6

        """
        bs = bits_from_any(bs)
        if len(bs) == 0:
            raise ValueError("Cannot find an empty Bits.")
        ba = Options().byte_aligned if byte_aligned is None else byte_aligned
        p = self._find(bs, 0, ba)
        return p

    def info(self) -> str:
        """Return a descriptive string with information about the Bits.

        Note that the output is designed to be helpful to users and is not considered part of the API.
        You should not use the output programmatically as it may change even between point versions.

        .. code-block:: pycon

            >>> Bits('0b1101').info()
            '4 bits: binary = 1101, hex = d, unsigned int = 13, signed int = -3'

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

    def pp(self, dtype1: str | Dtype | None = None, dtype2: str | Dtype | None = None,
           groups: int | None = None, width: int = 80, show_offset: bool = True, stream: TextIO = sys.stdout) -> None:
        """Pretty print the Bits's value.

        :param dtype1: First data type to display.
        :param dtype2: Optional second data type.
        :param groups: How many groups of bits to display on each line. This overrides any value given for width.
        :param width: Max width of printed lines. Defaults to 80, but ignored if groups parameter is set.
            A single group will always be printed per line even if it exceeds the max width.
        :param show_offset: If True (the default) shows the bit offset in the first column of each line.
        :param stream: A TextIO object with a write() method. Defaults to sys.stdout.

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

        bits_per_group, has_length_in_fmt = process_pp_tokens(dtype1, dtype2)
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
            output_stream.write(" + trailing_bits = 0b" + DtypeSingle("bin").unpack(self[-trailing_bit_length:]))
        output_stream.write("\n")
        stream.write(output_stream.getvalue())
        return

    def rfind(self, bs: BitsType, /, byte_aligned: bool | None = None) -> int | None:
        """Find final occurrence of substring bs.

        Returns a the bit position if found, or None if not found.

        :param bs: The Bits to find.
        :param byte_aligned: If True, the Bits will only be found on byte boundaries.
        :return: The bit position if found, or None if not found.

        Raises ValueError if bs is empty, if start < 0, if end > len(self) or
        if end < start.

        .. code-block:: pycon

            >>> Bits('0b110110').rfind('0b1')
            4
            >>> Bits('0b110110').rfind('0b0')
            5

        """
        bs = bits_from_any(bs)
        ba = Options().byte_aligned if byte_aligned is None else byte_aligned
        if len(bs) == 0:
            raise ValueError("Cannot find an empty Bits.")
        p = self._rfind(bs, 0, ba)
        return p

    def unpack(self, fmt: Dtype | str | Sequence[Dtype | str], /) -> Any | list[Any]:
        """
        Interpret the Bits as a given data type or list of data types.

        If a single Dtype is given then a single value will be returned, otherwise a list of values will be returned.
        A single Dtype with no length can be used to interpret the whole Bits - in this common case properties
        are provided as a shortcut. For example instead of ``b.unpack('bin')`` you can use ``b.bin``.

        :param fmt: The data type or sequence of data types to interpret the Bits as.
        :return: The interpreted value(s).

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
        if isinstance(fmt, str):
            fmt = Dtype.from_string(fmt)
        elif isinstance(fmt, Sequence):
            d = DtypeTuple.from_params(fmt)
            return list(d.unpack(self))
        return fmt.unpack(self)

    # ----- Private Methods -----

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
        group_chars1 = chars_per_dtype(dtype1, bits_per_group)
        group_chars2 = 0 if dtype2 is None else chars_per_dtype(dtype2, bits_per_group)
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
        for bits in self._chunks(max_bits_per_line):
            offset_str = ""
            if show_offset:
                offset = bitpos // offset_factor
                bitpos += len(bits)
                offset_str = colour.green + f"{offset: >{offset_width - len(offset_sep)}}" + offset_sep + colour.off
            fb1, chars_used = format_bits(bits, bits_per_group, sep, dtype1, colour.magenta, colour.off, first_fb_width)
            if first_fb_width is None:
                first_fb_width = chars_used
            fb2 = ""
            if dtype2 is not None:
                fb2, chars_used = format_bits(bits, bits_per_group, sep, dtype2, colour.blue, colour.off, second_fb_width)
                if second_fb_width is None:
                    second_fb_width = chars_used
                fb2 = format_sep + fb2

            line_fmt = offset_str + fb1 + fb2 + "\n"
            stream.write(line_fmt)
        return

    # ----- Special Methods -----

    # ----- Logical


    def __rand__(self, bs: BitsType, /) -> Bits | MutableBits:
        """Bit-wise 'and' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        return self.__and__(bs)

    def __ror__(self, bs: BitsType, /) -> Bits | MutableBits:
        """Bit-wise 'or' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        return self.__or__(bs)

    def __rxor__(self, bs: BitsType, /) -> Bits | MutableBits:
        """Bit-wise 'xor' between two Bits. Returns new Bits.

        Raises ValueError if the two Bits have differing lengths.

        """
        return self.__xor__(bs)

    # ----- Conversions

    def __bytes__(self) -> bytes:
        return self.to_bytes()

    # ----- Comparisons

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

    # ----- Operators

    def __mul__(self: Bits, n: int, /) -> Bits:
        """Return new Bits consisting of n concatenations of self.

        Called for expression of the form 'a = b*3'.
        n -- The number of concatenations. Must be >= 0.

        """
        if n < 0:
            raise ValueError("Cannot multiply by a negative integer.")
        mutable = MutableBits()

        if isinstance(self, Bits):
            for _ in range(n):
                mutable.append(self)
            return mutable.as_bits()
        else:
            b = self.to_bits()
            for _ in range(n):
                mutable.append(b)
            return mutable

    def __radd__(self: Bits, bs: BitsType, /) -> Bits:
        """Concatenate Bits and return a new Bits."""
        bs = mutable_bits_from_any(bs)
        bs.append(self)
        if isinstance(self, Bits):
            x = bs.as_bits()
        else:
            x = bs
        return x

    def __rmul__(self: Bits, n: int, /) -> Bits:
        """Return Bits consisting of n concatenations of self.

        Called for expressions of the form 'a = 3*b'.
        n -- The number of concatenations. Must be >= 0.

        """
        return self.__mul__(n)

    # ----- Other

    def __contains__(self, bs: BitsType, /) -> bool:
        """Return whether bs is contained in the current Bits.

        bs -- The Bits to search for.

        """
        found = BaseBitsMethods.find(self, bs, byte_aligned=False)
        return False if found is None else True



class BitsMethods:

    # ----- Class Methods -----

    @classmethod
    def from_dtype(cls, dtype: Dtype | str, value: Any, /) -> Bits :
        """
        Pack a value according to a data type or data type tuple.

        :param dtype: The data type to pack.
        :param value: A value appropriate for the data type.
        :returns: A newly constructed ``Bits``.

        .. code-block:: python

            a = Bits.from_dtype("u8", 17)
            b = Bits.from_dtype("f16, i4, bool", [2.25, -3, False])

        """
        if isinstance(dtype, str):
            dtype = Dtype.from_string(dtype)
        try:
            xt = dtype.pack(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Can't pack a value of {value} with a Dtype '{dtype}': {str(e)}")
        return xt

    @classmethod
    def from_random(cls, n: int, /, seed: int | None = None) -> Bits:
        """
        Create a new instance with all bits pseudo-randomly set.

        :param n: The number of bits. Must be positive.
        :param seed: An optional seed.
        :return: A newly constructed ``Bits`` with random data.

        Note that this uses Python's pseudo-random number generator and so is
        not suitable for cryptographic or other more serious purposes.

        .. code-block:: python

            a = Bits.from_random(1000000)  # A million random bits

        """
        if n == 0:
            return cls()
        if seed is not None:
            random.seed(seed)
        value = random.getrandbits(n)
        return cls.from_dtype(DtypeSingle.from_params(DtypeKind.UINT, n), value)

    def rfind_all(self, bs: BitsType, count: int | None = None, byte_aligned: bool | None = None) -> Iterable[int]:
        """Find all occurrences of bs starting at the end. Return generator of bit positions.

        :param bs: The Bits to find.
        :param count: The maximum number of occurrences to find.
        :param byte_aligned: If True, the Bits will only be found on byte boundaries.
        :return: A generator yielding bit positions.

        Raises ValueError if bs is empty, if start < 0, if end > len(self) or
        if end < start.

        All occurrences of bs are found, even if they overlap.

        Note that this method is not available for :class:`MutableBits` as its value could change while the
        generator is still active. For that case you should convert to a :class:`Bits` first with :meth:`MutableBits.to_bits`.

        .. code-block:: pycon

            >>> list(Bits('0b10111011').rfind_all('0b11'))
            [6, 3, 2]

        """
        # TODO: This is only a (working) placeholder.
        return (p for p in reversed(list(self.find_all(bs, count, byte_aligned))))

    def find_all(self, bs: BitsType, count: int | None = None, byte_aligned: bool | None = None) -> Iterable[int]:
        """Find all occurrences of bs. Return generator of bit positions.

        :param bs: The Bits to find.
        :param count: The maximum number of occurrences to find.
        :param byte_aligned: If True, the Bits will only be found on byte boundaries.
        :return: A generator yielding bit positions.

        Raises ValueError if bs is empty, if start < 0, if end > len(self) or
        if end < start.

        All occurrences of bs are found, even if they overlap.

        Note that this method is not available for :class:`MutableBits` as its value could change while the
        generator is still active. For that case you should convert to a :class:`Bits` first with :meth:`MutableBits.to_bits`.

        .. code-block:: pycon

            >>> list(Bits('0b10111011').find_all('0b11'))
            [2, 3, 6]

        """
        if count is not None and count < 0:
            raise ValueError("In find_all, count must be >= 0.")
        bs = bits_from_any(bs)
        ba = Options().byte_aligned if byte_aligned is None else byte_aligned
        c = 0
        for i in self._findall(bs, ba):
            if count is not None and c >= count:
                return
            c += 1
            yield i
        return

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
            start = self._get_slice_unchecked(0, 800)
            end = self._get_slice_unchecked(length - 800, 800)
            return hash(((start + end).to_bytes(), length))

    def __setitem__(self, key, value):
        raise TypeError(f"'{self.__class__.__name__}' object does not support item assignment. "
        f"Did you mean to use the MutableBits class? Or you could call to_mutable_bits() to convert to a MutableBits.")

    def __delitem__(self, key):
        raise TypeError(f"'{self.__class__.__name__}' object does not support item deletion. "
        f"Did you mean to use the MutableBits class? Or you could call to_mutable_bits() to convert to a MutableBits.")

    def __getattr__(self, name):
        """Catch attribute errors and provide helpful messages for methods that exist in MutableBits."""
        # Check if the method exists in MutableBits
        if hasattr(MutableBits, name) and callable(getattr(MutableBits, name)) and not name.startswith("_"):
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'. "
                f"Did you mean to use the MutableBits class? Or you could replace '.{name}(...)' with '.to_mutable_bits().{name}(...)'."
            )
        # Default behavior
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def __copy__(self: Bits) -> Bits:
        """Return a new copy of the Bits for the copy module.

        This can just return self as it's immutable.

        """
        return self


class MutableBitsMethods:

    # ----- Class Methods -----

    @classmethod
    def from_dtype(cls, dtype: Dtype | str, value: Any, /) -> MutableBits:
        """
        Pack a value according to a data type or data type tuple.

        :param dtype: The data type to pack.
        :param value: A value appropriate for the data type.
        :returns: A newly constructed ``MutableBits``.

        .. code-block:: python

            a = MutableBits.from_dtype("u8", 17)
            b = MutableBits.from_dtype("f16, i4, bool", [2.25, -3, False])

        """
        if isinstance(dtype, str):
            dtype = Dtype.from_string(dtype)
        try:
            xt = dtype.pack(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Can't pack a value of {value} with a Dtype '{dtype}': {str(e)}")
        return xt._as_mutable_bits()

    @classmethod
    def from_random(cls, n: int, /, seed: int | None = None) -> MutableBits:
        """
        Create a new instance with all bits pseudo-randomly set.

        :param n: The number of bits. Must be positive.
        :param seed: An optional seed.
        :return: A newly constructed ``MutableBits`` with randomly data.

        Note that this uses Python's pseudo-random number generator and so is
        not suitable for cryptographic or other more serious purposes.

        .. code-block:: python

            a = MutableBits.from_random(1000000)  # A million random bits

        """
        if n == 0:
            return cls()
        if seed is not None:
            random.seed(seed)
        value = random.getrandbits(n)
        return cls.from_dtype(DtypeSingle.from_params(DtypeKind.UINT, n), value)

    def __iter__(self):
        """Iterating over the bits is not supported for this mutable type."""
        raise TypeError("MutableBits objects are not iterable. "
                        "You can use .to_bits() to convert to a Bits object that does support iteration.")

    def __getattr__(self, name):
        """Catch attribute errors and provide helpful messages for methods that exist in Bits."""
        # Check if the method exists in Bits
        if hasattr(Bits, name) and callable(getattr(Bits, name)) and not name.startswith("_"):
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'. "
                f"Did you mean to use the Bits class? Or you could replace '.{name}(...)' with '.to_bits().{name}(...)'."
            )

        # Default behaviour
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def byte_swap(self, byte_length: int | None = None, /) -> MutableBits:
        """Change the byte endianness in-place. Returns self.

        The whole of the MutableBits will be byte-swapped. It must be a multiple
        of byte_length long.

        :param byte_length: An int giving the number of bytes in each swap.
        :return: self

        .. code-block:: pycon

            >>> a = MutableBits('0x12345678')
            >>> a.byte_swap(2)
            MutableBits('0x34127856')

        """
        if len(self) % 8 != 0:
            raise ValueError(f"Bit length must be an multiple of 8 to use byte_swap (got length of {len(self)} bits). "
                             "This error can also be caused by using an endianness modifier on non-whole byte data.")
        if byte_length is None:
            if len(self) == 0:
                return MutableBits()
            byte_length = len(self) // 8
        if byte_length <= 0:
            raise ValueError(f"Need a positive definite byte length for byte_swap. Received '{byte_length}'.")
        if len(self) % (byte_length * 8) != 0:
            raise ValueError(f"The MutableBits to byte_swap is {len(self) // 8} bytes long, "
                             f"but it needs to be a multiple of {byte_length} bytes.")
        chunks = []
        for startbit in range(0, len(self), byte_length * 8):
            x = self._get_slice_unchecked(startbit, byte_length * 8).to_bytes()
            chunks.append(MutableBits.from_bytes(x[::-1]))
        x = MutableBits.from_joined(chunks)
        self[:] = x
        return self

    def replace(self, old: BitsType, new: BitsType, /, start: int | None = None, end: int | None = None,
                count: int | None = None, byte_aligned: bool | None = None) -> MutableBits:
        """Replaces all occurrences of old with new. Returns self.

        :param old: The Bits or to replace.
        :param new: The replacement Bits.
        :param start: Any occurrences that start before this bit position will not be replaced.
        :param end: Any occurrences that finish after this bit position will not be replaced.
        :param count: The maximum number of replacements to make. Defaults to all.
        :param byte_aligned: If True, replacements will only be made on byte boundaries.
        :return: self

        :raises ValueError: if old is empty or if start or end are out of range.

        .. code-block:: pycon

            >>> s = MutableBits('0b10011')
            >>> s.replace('0b1', '0xf')
            MutableBits('0b11110011111111')

        """
        if count == 0:
            return self
        old_bits = bits_from_any(old)
        new_bits = bits_from_any(new)
        if len(old_bits) == 0:
            raise ValueError("Empty Bits cannot be replaced.")
        start, end = _validate_slice(len(self), start, end)
        if byte_aligned is None:
            byte_aligned = Options().byte_aligned
        # First find all the places where we want to do the replacements
        starting_points: list[int] = []
        if byte_aligned:
            start += (8 - start % 8) % 8
        for x in self[start:end].as_bits().find_all(old, byte_aligned=byte_aligned):
            x += start
            if not starting_points:
                starting_points.append(x)
            elif x >= starting_points[-1] + len(old_bits):
                # Can only replace here if it hasn't already been replaced!
                starting_points.append(x)
            if count != 0 and len(starting_points) == count:
                break
        if not starting_points:
            return self
        original = self.as_bits()
        replacement_list = [original._getslice(0, starting_points[0])]
        for i in range(len(starting_points) - 1):
            replacement_list.append(new_bits)
            replacement_list.append(original._getslice(starting_points[i] + len(old_bits), starting_points[i + 1]))
        # Final replacement
        replacement_list.append(new_bits)
        replacement_list.append(original._getslice(starting_points[-1] + len(old_bits), len(original)))
        self[:] = MutableBits.from_joined(replacement_list)
        return self


# Patching on the methods to Bits and MutableBits to avoid inheritance.
def _patch_classes():
    for name, method in BaseBitsMethods.__dict__.items():
        if isinstance(method, classmethod):
            setattr(Bits, name, classmethod(method.__func__))
            setattr(MutableBits, name, classmethod(method.__func__))
        elif callable(method):
            setattr(Bits, name, method)
            setattr(MutableBits, name, method)

    for name, method in BitsMethods.__dict__.items():
        if isinstance(method, classmethod):
            setattr(Bits, name, classmethod(method.__func__))
        elif callable(method):
            setattr(Bits, name, method)

    for name, method in MutableBitsMethods.__dict__.items():
        if isinstance(method, classmethod):
            setattr(MutableBits, name, classmethod(method.__func__))
        elif callable(method):
            setattr(MutableBits, name, method)


# The hash method is not available for a ``MutableBits`` object as it is mutable.
MutableBits.__hash__ = None


_patch_classes()

Sequence.register(Bits)
Sequence.register(MutableBits)
