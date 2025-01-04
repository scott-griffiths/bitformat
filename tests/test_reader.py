import pytest
from bitformat import Reader, Field, Bits


def test_creation():
    r = Reader()
    assert len(r.bits) == 0
    assert r.pos == 0

    r = Reader(Bits.from_string("0x12345"), 4)
    assert len(r.bits) == 20
    assert r.pos == 4

    r = Reader(Bits.from_bytes(b"hello"))
    assert len(r.bits) == 40


def test_read():
    r = Reader(Bits("0x12345"), 4)
    assert r.pos == 4
    assert r.read("bits4") == "0x2"
    assert r.pos == 8
    assert r.read("u4") == 3
    assert r.pos == 12
    r.pos = 0
    b = r.read(8)
    assert b == '0x12'


def test_parse():
    r = Reader()
    r.bits = Bits.from_bytes(b"hello_world")
    r.pos = 6 * 8
    f = Field("bytes3")
    assert r.parse(f) == 24
    assert f.value == b"wor"
    r.parse(g := Field("bool"))
    assert g.value is False
