
from bitformat.bit_rust import BitRust
import pytest

def test_creation():
    b = BitRust.from_zeros(10)
    assert b.length() == 10
    assert b.to_bin() == '0000000000'

    b2 = BitRust.from_ones(8)
    assert b2.to_bin() == '11111111'
    assert b2.to_hex() == 'ff'

def test_creation_from_bytes():
    b3 = BitRust.from_bytes(b'hello')
    assert b3.to_hex() == '68656c6c6f'
    assert b3.to_bytes() == b'hello'
    b4 = b3.getslice(8, 40)
    assert b4.to_hex() == '656c6c6f'
    assert b4.to_bytes() == b'ello'

def test_join():
    a = BitRust.from_zeros(4)
    b = BitRust.from_ones(4)
    c = BitRust.join([a, b])
    assert c.to_bin() == '00001111'
    d = c.reverse()
    assert d.to_bin() == '11110000'
    e = c & d
    assert e.to_bin() == '00000000'

def test_find():
    a = BitRust.from_bin('00000110001110')
    b = BitRust.from_bin('11')
    assert a.find(b, 0, False) == 5
    assert a.find(b, 0, True) is None

def test_from_oct():
    a = BitRust.from_oct('776')
    assert a.to_bin() == '111111110'
    with pytest.raises(ValueError):
        b = BitRust.from_oct_checked('abc')
    assert a.to_oct() == "776"

def test_to_bytes():
    a = BitRust.from_ones(16)
    assert a.to_bytes() == b"\xff\xff"
    b = a.getslice(7, None)
    assert b.to_bytes() == b"\xff\x80"
