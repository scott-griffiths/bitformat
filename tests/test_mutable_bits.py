#!/usr/bin/env python
import pytest
from bitformat import Dtype, Bits, MutableBits, DtypeTuple, DtypeSingle, DtypeArray, DtypeKind


def test_creation():
    a = MutableBits.from_zeros(5)
    b = MutableBits.from_bools([1, 0, 0])
    c = MutableBits.from_bytes(b'123')
    d = MutableBits.from_dtype('u8', 254)
    e = MutableBits.from_string('0b1110')
    for x in [a, b, c, d, e]:
        assert isinstance(x, MutableBits)

# def test_set_mut():
#     a = MutableBits('0x000')
#     b = a.set_mut(1, 1)
#     assert a == '0x400'
#     assert b == '0x400'
#     with pytest.raises(AttributeError):
#         _ = a.set(1, 1)
