#!/usr/bin/env python

from bitformat import Format, Dtype, Bits, Field, Register
from hypothesis import given, settings
import hypothesis.strategies as st
import math


def get_allowed_length(dtype_name, length):
    al = Register().name_to_def[dtype_name].allowed_sizes
    if al and al.values:
        if al.values[-1] is Ellipsis:
            return al.values[1] * length
        else:
            return al.values[length % len(al.values)]
    return length


def compare_fields(f, f2):
    if isinstance(f.value, float) and math.isnan(f.value):
        assert math.isnan(f2.value)
    assert f == f2, f"Fields are not equal: {f} != {f2}"


@given(
    dtype_name=st.sampled_from(sorted(Register().name_to_def.keys())),
    length=st.integers(1, 100),
    const=st.booleans(),
    int_value=st.integers(0, 2**800 - 1),
)
def test_field_consistency(dtype_name, length, const, int_value):
    length = get_allowed_length(dtype_name, length)
    f = Field.from_params(Dtype.from_params(dtype_name, length))
    f2 = Field.from_string(str(f))
    compare_fields(f, f2)

    # Create some bits of the right length
    bits_per_character = Register().name_to_def[dtype_name].bits_per_character
    if bits_per_character is not None:
        length *= bits_per_character
    b = Bits.from_dtype("u800", int_value)[0:length]
    f.parse(b)
    assert f.to_bits() == b
    v = f.value
    if v is not None:
        f2.value = v
    else:
        f2.clear()
    if dtype_name != "pad" and not (isinstance(v, float) and math.isnan(v)):
        assert f.to_bits() == f2.to_bits()
        f.const = const
        f3 = eval(repr(f))
        compare_fields(f, f3)


@given(
    dtype_name=st.sampled_from(sorted(Register().name_to_def.keys())),
    length=st.integers(1, 5),
    int_value=st.integers(0, 2**160 - 1),
    items=st.integers(1, 4),
)
def test_field_array_consistency(dtype_name, length, int_value, items):
    length = get_allowed_length(dtype_name, length)

    f = Field.from_params(Dtype.from_params(dtype_name, length, True, items))
    f2 = Field.from_string(str(f))
    assert f == f2

    # Create some bits of the right length
    bits_per_character = Register().name_to_def[dtype_name].bits_per_character
    if bits_per_character is not None:
        length *= bits_per_character
    b = Bits.from_dtype("u320", int_value)[0: length * items]
    f.parse(b)
    assert f.to_bits() == b
    if (
        not isinstance(f.value[0], float) and not f.dtype.name == "pad"
    ):  # Can't compare NaN or pad
        f2.pack([f.value])
        assert f.to_bits() == f2.to_bits()
        assert f.value == f2.value


@given(
    dtype_names=st.lists(
        st.sampled_from(sorted(Register().name_to_def.keys())), min_size=5, max_size=5
    ),
    lengths=st.lists(st.integers(1, 5), min_size=5, max_size=5),
)
def test_format_consistency(dtype_names, lengths):
    bits_per_characters = [
        Register().name_to_def[dtype_name].bits_per_character
        for dtype_name in dtype_names
    ]
    bits_per_characters = [b if b is not None else 1 for b in bits_per_characters]
    als = []
    for al, length in zip(
        [
            Register().name_to_def[dtype_name].allowed_sizes
            for dtype_name in dtype_names
        ],
        lengths,
    ):
        if al.values:
            if al.values[-1] is Ellipsis:
                als.append(al.values[1] * length)
            else:
                als.append(al.values[length % len(al.values)])
        else:
            als.append(length)

    zipped = list(zip(dtype_names, als, bits_per_characters))
    for i in range(6):
        dtypes = [
            Dtype.from_params(dtype_name, length * bits_per_character)
            for dtype_name, length, bits_per_character in zipped[:i]
        ]
        f = Format.from_params([Field.from_params(dtype) for dtype in dtypes])
        f2 = f
        assert f == f2
        # Create some bits of the right length
        b = Bits.from_ones(f.bit_length)
        f.parse(b)
        assert f.to_bits() == b
