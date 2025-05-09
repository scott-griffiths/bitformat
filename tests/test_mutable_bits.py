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

def test_append():
    # Basic append functionality
    a = MutableBits('0x0f')
    a.append('0x0a')
    assert a == '0x0f0a'

    # Verify method chaining
    a = MutableBits('0x01')
    result = a.append('0x02').append('0x03')
    assert a == '0x010203'
    assert result is a  # Should return self

    # Different input types
    a = MutableBits('0b1010')
    a.append(Bits('0b1111'))  # Bits object
    assert a == '0b10101111'
    a.append(Bits.from_bools([True, False, True]))
    assert a == '0b10101111101'

    # Empty append
    a = MutableBits('0x42')
    a.append(Bits())
    assert a == '0x42'


def test_prepend():
    # Basic prepend functionality
    a = MutableBits('0x0f')
    a.prepend('0x0a')
    assert a == '0x0a0f'

    # Verify method chaining
    a = MutableBits('0x03')
    result = a.prepend('0x02').prepend('0x01')
    assert a == '0x010203'
    assert result is a  # Should return self

    # Different input types
    a = MutableBits('0b1010')
    a.prepend(Bits('0b1111'))  # Bits object
    assert a == '0b11111010'
    a.prepend(Bits.from_bools([True, False, True]))  # Boolean list
    assert a == '0b10111111010'

    # Empty prepend
    a = MutableBits('0x42')
    a.prepend(Bits())
    assert a == '0x42'


def test_append_prepend_together():
    # Test combining both operations
    a = MutableBits('0xAA')
    a.append('0xBB').prepend('0xCC')
    assert a == '0xCCAABB'