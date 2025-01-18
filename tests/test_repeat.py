import pytest
from bitformat import Repeat, Format, Bits, Field


def test_creation():
    p = Repeat.from_params(3, "u8")
    assert p.count == 3
    assert p.field == Field("u8")


def test_from_string():
    # p = Repeat.from_string('Repeat{3}: u8')
    # assert p.count == 3
    # assert p.field == Field('u8')
    # s = """
    # Repeat(2,
    #     fred = (
    #         bool,
    #         john: i7
    #     )
    # )
    # """
    s = """
    Repeat {2}:
        fred = (
            bool,
            john: i7
        )
    """

    q = Repeat(s)
    assert q.count == 2
    assert q.unpack(Bits("0x8710")) == [[True, 7], [False, 16]]


def test_edge_cases():
    p = Repeat.from_params(-1, "x: u8")
    assert p.unpack("0xff") == []


def test_pack():
    f = Repeat("Repeat {4}: bool")
    f.pack([True, False, True, False])
    assert f.value == [True, False, True, False]


def test_simple_parse_and_unpack():
    p = Repeat.from_params(3, "u8")
    p.parse("0x010203")
    assert p.value == [1, 2, 3]
    assert p.unpack("0x030201") == [3, 2, 1]
