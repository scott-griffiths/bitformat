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


def test_setitem_single_bit():
    a = MutableBits('0b0010')
    a[0] = 1
    assert a == '0b1010'
    a[2] = 0
    assert a == '0b1000'
    a[-1] = True
    assert a == '0b1001'
    a[-4] = False
    assert a == '0b0001'
    # Out of range
    with pytest.raises(IndexError):
        a[4] = 1
    with pytest.raises(IndexError):
        a[-5] = 0

def test_setitem_slice():
    a = MutableBits('0b101010')
    a[1:4] = '0b111'
    assert a == '0b111110'
    a[0:2] = Bits('0b00')
    assert a == '0b001110'
    a[2:5] = MutableBits('0b101')
    assert a == '0b001010'
    # Negative indices
    a[-3:-1] = '0b11'
    assert a == '0b001110'
    # Full slice
    a[:] = '0b000000'
    assert a == '0b000000'
    # Empty slice
    a[2:2] = '0b'
    assert a == '0b000000'
    a[1:3] = '0b1'
    assert a == '0b01000'
    # Stepping is not allowed
    with pytest.raises(ValueError):
        a[::2] = '0b00'
    a[10:12] = '0b00'  # Out of range, so just extends.
    assert a == '0b0100000'

def test_setitem_slice_length_change():
    a = MutableBits('0b1010')
    a[1:3] = '0b111'
    assert a == '0b11110'  # Length increased by 1
    a[0:2] = '0b0'
    assert a == '0b0110'
    a[1:2] = '0b1111'
    assert a == '0b0111110'
    a[0:15] = '0b1'
    assert a == '0b1'
    # Setting to empty
    a[:] = ''
    assert a == ''
    # Setting empty slice to non-empty
    a[0:0] = '0b101'
    assert a == '0b101'

def test_delitem_single_bit():
    # Test deleting single bits
    a = MutableBits('0b1010')
    del a[1]
    assert a == '0b110'

    a = MutableBits('0b1010')
    del a[-1]
    assert a == '0b101'

    # Out of range
    with pytest.raises(IndexError):
        a = MutableBits('0b101')
        del a[3]

    with pytest.raises(IndexError):
        a = MutableBits('0b101')
        del a[-4]


def test_delitem_slice():
    # Test deleting slices
    a = MutableBits('0b101010')
    del a[1:4]
    assert a == '0b110'

    # Negative indices
    a = MutableBits('0b101010')
    del a[-4:-2]
    assert a == '0b1010'

    # Empty slice should do nothing
    a = MutableBits('0b1010')
    del a[2:2]
    assert a == '0b1010'

    # Full slice deletion
    a = MutableBits('0b1010')
    del a[:]
    assert a == ''

    # Partial indices
    a = MutableBits('0b101010')
    del a[2:]  # Delete from index 2 to the end
    assert a == '0b10'

    a = MutableBits('0b101010')
    del a[:2]  # Delete from start to index 2
    assert a == '0b1010'


def test_delitem_with_step():
    # Test slices with step
    a = MutableBits('0b101010')
    with pytest.raises(ValueError):
        del a[::2]  # Delete every other bit


def test_delitem_edge_cases():
    # Empty bits
    a = MutableBits()
    with pytest.raises(IndexError):
        del a[0]

    a = MutableBits('0b1010')
    del a[10:20]  # Out of range slice, should do nothing
    assert a == '0b1010'

    # Delete last bit
    a = MutableBits('0b1')
    del a[0]
    assert a == ''

def test_inplace_add():
    a = MutableBits('0x123')
    a += '0xff'
    assert a == '0x123ff'