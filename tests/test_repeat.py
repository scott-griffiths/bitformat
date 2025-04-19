from bitformat import Repeat, Bits, Field, Format
import pytest

def test_creation():
    p = Repeat.from_params(3, "u8")
    assert p.count == 3
    assert p.field == Field("u8")


def test_from_string():
    p = Repeat.from_string('repeat{3}: u8')
    assert p.count == 3
    assert p.field == Field('u8')
    s = """repeat {2}:
        fred: (
            bool,
            john: i7
        )
    """
    q = Repeat(s)
    assert q.count == 2
    assert q.unpack(Bits("0x8710")) == [[True, 7], [False, 16]]


def test_pack():
    f = Repeat("repeat {4}: bool")
    f.pack([True, False, True, False])
    assert f.value == [True, False, True, False]


def test_simple_parse_and_unpack():
    p = Repeat.from_params("{x}", "u8")
    p.parse("0x010203", x=3)
    assert p.value == [1, 2, 3]
    p.count = p.count.evaluate(x=3)
    assert p.unpack("0x030201") == [3, 2, 1]

def test_parsing_repeat():
    f = Format('(repeat {4}: u8)')
    g = f[:]
    assert f.bit_length == 32
    assert str(f[0]) == 'repeat{4}:\n    u8\n    u8\n    u8\n    u8'
    f.parse("0x01020304")
    assert f != g
    assert f.value[0] == [1, 2, 3, 4]
    assert str(f[0]) == 'repeat{4}:\n    u8 = 1\n    u8 = 2\n    u8 = 3\n    u8 = 4'

def test_pack_errors():
    r = Repeat("repeat {x}: u8")
    with pytest.raises(ValueError):
        r.pack([1, 2, 3])