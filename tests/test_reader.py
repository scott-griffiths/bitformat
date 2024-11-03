import pytest
from bitformat import Reader, Field


def test_creation():
    r = Reader()
    assert len(r.bits) == 0
    assert r.pos == 0

    r = Reader('0x12345', 4)
    assert len(r.bits) == 20
    assert r.pos == 4

    r = Reader(b'hello')
    assert len(r.bits) == 40


def test_read():
    r = Reader('0x12345', 4)
    assert r.pos == 4
    assert r.read(4) == '0x2'
    assert r.pos == 8
    assert r.read('u4') == 3
    assert r.pos == 12

def test_parse():
    r = Reader()
    r.bits = b'hello_world'
    r.pos = 6*8
    f = Field('bytes3')
    assert r.parse(f) == 24
    assert f.value == b'wor'
    r.parse(g := Field('bool'))
    assert g.value is False
