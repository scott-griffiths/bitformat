import pytest

from bitformat import Mutibs, Tibs


def test_tibs_to_bytes_is_strict_for_partial_bytes():
    b = Tibs.from_bytes(b"ABCD") + "0b1"
    with pytest.raises(ValueError):
        b.to_bytes()


def test_tibs_native_endian_views():
    little = Tibs.from_dtype("u16_le", 0x1234)
    assert little == "0x3412"
    assert little.le.u == 0x1234
    assert little.be.u == 0x3412
    assert little.unpack("u16_le") == 0x1234


def test_tibs_byte_aligned_search_is_explicit_argument():
    b = Tibs("0x00 ff 0f f")
    assert b.find_all("0xff") == [8, 20]
    assert b.find_all("0xff", byte_aligned=True) == [8]


def test_mutibs_slice_assignment_uses_direct_tibs_semantics():
    b = Mutibs("0b101010")
    b[1:4] = "0b111"
    assert b == "0b111110"
    b[0:2] = Tibs("0b00")
    assert b == "0b001110"
