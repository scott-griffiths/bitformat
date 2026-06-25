from __future__ import annotations

import io
import sys
from ast import literal_eval
from collections.abc import Sequence
from typing import Any, TextIO

from bitformat._common import Colour, DtypeKind
from bitformat._options import Options
from bitformat._tibs import Mutibs, Tibs, TibsLike, mutibs_from_any, tibs_from_any
from bitformat._dtypes import Dtype, DtypeArray, DtypeSingle, DtypeTuple, Register

__all__ = ["Tibs", "Mutibs", "TibsLike", "tibs_from_any", "mutibs_from_any"]

_unprintable = list(range(0x00, 0x20))
_unprintable.extend(range(0x7F, 0xFF))


def _validate_slice(length: int, start: int | None, end: int | None) -> tuple[int, int]:
    start = 0 if start is None else (start + length if start < 0 else start)
    end = length if end is None else (end + length if end < 0 else end)
    if not 0 <= start <= end <= length:
        raise ValueError(f"Invalid slice positions for Tibs length {length}: start={start}, end={end}.")
    return start, end


def _convert_bytes_to_printable(data: bytes) -> str:
    return "".join(chr(0x100 + x) if x in _unprintable else chr(x) for x in data)


def _chars_per_dtype(dtype: Dtype, bits_per_group: int) -> int:
    if isinstance(dtype, (DtypeSingle, DtypeArray)):
        return Register().kind_to_def[dtype.kind].bitlength2chars_fn(bits_per_group)
    assert isinstance(dtype, DtypeTuple)
    return sum(_chars_per_dtype(d, bits_per_group) for d in dtype) + 2 + 2 * (dtype.items - 1)


def _format_tibs(bits: Tibs | Mutibs, bits_per_group: int, sep: str, dtype: Dtype, colour_start: str,
                 colour_end: str, width: int | None = None) -> tuple[str, int]:
    get_fn = dtype.unpack
    chars_per_group = _chars_per_dtype(dtype, bits_per_group)
    if isinstance(dtype, (DtypeSingle, DtypeArray)):
        kind = dtype.kind
        if kind is DtypeKind.BYTES:
            get_fn = lambda b: _convert_bytes_to_printable(b.bytes)
        elif kind is DtypeKind.BOOL:
            get_fn = Register().get_single_dtype(DtypeKind.UINT, bits_per_group).unpack
        align = "<" if kind in {DtypeKind.BIN, DtypeKind.OCT, DtypeKind.HEX, DtypeKind.BITS, DtypeKind.BYTES} else ">"
        if kind is DtypeKind.BITS:
            text = sep.join(f"{str(b): {align}{chars_per_group}}" for b in bits.chunks(bits_per_group))
        else:
            text = sep.join(f"{str(get_fn(b)): {align}{chars_per_group}}" for b in bits.chunks(bits_per_group))
        chars_used = len(text)
        padding_spaces = 0 if width is None else max(width - chars_used, 0)
        return colour_start + text + colour_end + " " * padding_spaces, chars_used

    assert isinstance(dtype, DtypeTuple)
    strings = []
    for b in bits.chunks(bits_per_group):
        chars_per_dtype_list = [_chars_per_dtype(d, d.bit_length) for d in dtype]
        values = get_fn(b)
        strings.append(f"[{', '.join(f'{str(v): >{c}}' for v, c in zip(values, chars_per_dtype_list))}]")
    text = sep.join(strings)
    chars_used = len(text)
    padding_spaces = 0 if width is None else max(width - chars_used, 0)
    return colour_start + text + colour_end + " " * padding_spaces, chars_used


def _process_pp_tokens(dtype1: Dtype, dtype2: Dtype | None) -> tuple[int, bool]:
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


def dtype_token_to_tibs(token: str) -> Tibs:
    try:
        dtype_str, value_str = token.split("=", 1)
        dtype = Dtype.from_string(dtype_str)
    except ValueError:
        raise ValueError(f"Can't parse token '{token}'. It should be in the form 'kind[length][_endianness]=value' "
                         f"(e.g. 'u16_le = 44') or a literal starting with '0b', '0o' or '0x'.")
    if isinstance(dtype, DtypeSingle) and dtype._definition.return_type not in (bool, bytes):
        return dtype.pack(value_str)
    try:
        value = literal_eval(value_str)
    except ValueError:
        raise ValueError(f"Can't parse token '{token}'. The value '{value_str}' can't be converted to the appropriate type.")
    return dtype.pack(value)


def _unpack(self: Tibs | Mutibs, dtype: Dtype | str | Sequence[Dtype | str], /,
            start: int | None = None, end: int | None = None) -> Any | list[Any]:
    if isinstance(dtype, str):
        dtype = Dtype.from_string(dtype)
    elif isinstance(dtype, Sequence):
        dtype = DtypeTuple.from_params(dtype)
    dtype = dtype.evaluate()

    if start is None and end is None:
        if dtype.bit_length is not None:
            if dtype.bit_length == len(self):
                return dtype._unpack_no_checks(self)
            if dtype.bit_length < len(self):
                return dtype._unpack_no_checks(self[:dtype.bit_length])
            raise ValueError(f"Not enough bits to unpack the requested Dtype. {len(self)} bits are available but "
                             f"{dtype} needs {dtype.bit_length} bits.")
        if isinstance(dtype, DtypeArray) and dtype._dtype_single.bit_length is not None:
            if dtype._dtype_single.bit_length < len(self):
                usable = len(self) - (len(self) % dtype._dtype_single.bit_length)
                return dtype._unpack_no_checks(self[:usable])
            raise ValueError(f"Not enough bits to unpack the requested Dtype. {len(self)} bits are available but "
                             f"{dtype} needs at least {dtype._dtype_single.bit_length} bits.")
        return dtype._unpack_no_checks(self)
    start, end = _validate_slice(len(self), start, end)
    return dtype.unpack(self[start:end])


def _pp_data(bits: Tibs | Mutibs, dtype1: Dtype, dtype2: Dtype | None, bits_per_group: int,
             width: int, sep: str, format_sep: str, show_offset: bool, stream: TextIO, offset_factor: int,
             groups: int | None) -> None:
    if dtype2 is not None:
        if dtype1.bit_length is not None:
            try:
                _ = dtype2.unpack(Tibs.from_zeros(dtype1.bit_length))
            except ValueError:
                raise ValueError(f"The Dtype '{dtype2}' can't be used alongside '{dtype1}' as it's not compatible with its length.")
        if dtype2.bit_length is not None:
            try:
                _ = dtype1.unpack(Tibs.from_zeros(dtype2.bit_length))
            except ValueError:
                raise ValueError(f"The Dtype '{dtype1}' can't be used alongside '{dtype2}' as it's not compatible with its length.")

    colour = Colour(not Options().no_color)
    offset_width = len(str(len(bits))) + 2 if show_offset else 0
    group_chars1 = _chars_per_dtype(dtype1, bits_per_group)
    group_chars2 = 0 if dtype2 is None else _chars_per_dtype(dtype2, bits_per_group)
    if groups is None:
        total_group_chars = group_chars1 + group_chars2 + len(sep) + len(sep) * bool(group_chars2)
        width_excluding_offset_and_final_group = width - offset_width - group_chars1 - group_chars2 - len(format_sep) * bool(group_chars2)
        groups_per_line = 1 + max(width_excluding_offset_and_final_group, 0) // total_group_chars
    else:
        groups_per_line = groups

    max_bits_per_line = groups_per_line * bits_per_group
    assert max_bits_per_line > 0

    bitpos = 0
    first_width = second_width = None
    for chunk in bits.chunks(max_bits_per_line):
        offset_str = ""
        if show_offset:
            offset = bitpos // offset_factor
            bitpos += len(chunk)
            offset_str = colour.green + f"{offset: >{offset_width - 2}}: " + colour.off
        fb1, chars_used = _format_tibs(chunk, bits_per_group, sep, dtype1, colour.magenta, colour.off, first_width)
        if first_width is None:
            first_width = chars_used
        fb2 = ""
        if dtype2 is not None:
            fb2, chars_used = _format_tibs(chunk, bits_per_group, sep, dtype2, colour.blue, colour.off, second_width)
            if second_width is None:
                second_width = chars_used
            fb2 = format_sep + fb2
        stream.write(offset_str + fb1 + fb2 + "\n")


def _pp(self: Tibs | Mutibs, dtype1: str | Dtype | None = None, dtype2: str | Dtype | None = None,
        groups: int | None = None, width: int = 80, show_offset: bool = True, stream: TextIO = sys.stdout) -> None:
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

    bits_per_group, has_length_in_fmt = _process_pp_tokens(dtype1, dtype2)
    trailing_bit_length = len(self) % bits_per_group if has_length_in_fmt and bits_per_group else 0
    data = self if trailing_bit_length == 0 else self[:-trailing_bit_length]
    output_stream = io.StringIO()
    dtype2_str = "" if dtype2 is None else f", dtype2='{dtype2}'"
    output_stream.write(f"<{self.__class__.__name__}, dtype1='{dtype1}'{dtype2_str}, "
                        f"length={colour.green}{len(self)}{colour.off} bits> [\n")
    _pp_data(data, dtype1, dtype2, bits_per_group, width, " ", " : ", show_offset, output_stream, 1, groups)
    output_stream.write("]")
    if trailing_bit_length:
        output_stream.write(" + trailing_bits = 0b" + DtypeSingle("bin").unpack(self[-trailing_bit_length:]))
    output_stream.write("\n")
    stream.write(output_stream.getvalue())


def _info(self: Tibs | Mutibs) -> str:
    def with_underscores(s: str) -> str:
        return "_".join(s[x:x + 4] for x in range(0, len(s), 4))

    length = len(self)
    if length == 0:
        return "0 bits: empty"
    max_interpretation_length = 64
    len_str = f"{length} bit{'' if length == 1 else 's'}: "
    if length <= max_interpretation_length:
        hex_str = f_str = ""
        bin_str = f"binary = {with_underscores(self.unpack('bin'))}"
        if length % 4 == 0:
            hex_str = f"hex = {with_underscores(self.unpack('hex'))}"
        u_str = f"unsigned int = {self.unpack('u')}"
        i_str = f"signed int = {self.unpack('i')}"
        if length in Register().kind_to_def[DtypeKind.FLOAT].allowed_sizes:
            f_str = f"float = {self.unpack('f')}"
        return len_str + ", ".join(x for x in [bin_str, hex_str, f_str, u_str, i_str] if x)
    if length <= 4 * max_interpretation_length and length % 4 == 0:
        return f"{len_str}hex = {with_underscores(self.unpack('hex'))}"
    if length % 4 == 0:
        return f"{len_str}hex ~= {with_underscores(self[:4 * max_interpretation_length].unpack('hex'))}..."
    return f"{len_str}binary ~= {with_underscores(self[:max_interpretation_length].unpack('bin'))}..."


def _tibs_from_dtype(cls, dtype: Dtype | str, value: Any, /) -> Tibs:
    if isinstance(dtype, str):
        dtype = Dtype.from_string(dtype)
    try:
        return dtype.pack(value)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Can't pack a value of {value} with a Dtype '{dtype}': {e}")


def _mutibs_from_dtype(cls, dtype: Dtype | str, value: Any, /) -> Mutibs:
    return _tibs_from_dtype(Tibs, dtype, value).to_mutibs()


def _patch_tibs_classes() -> None:
    Tibs.info = _info
    Mutibs.info = _info
    Tibs.pp = _pp
    Mutibs.pp = _pp
    Tibs.unpack = _unpack
    Mutibs.unpack = _unpack
    Tibs.from_dtype = classmethod(_tibs_from_dtype)
    Mutibs.from_dtype = classmethod(_mutibs_from_dtype)


_patch_tibs_classes()
