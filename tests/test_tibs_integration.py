import io

import pytest
import tibs

import bitformat
from bitformat import Mutibs, Tibs


def test_tibs_exports_are_direct_classes():
    assert bitformat.Tibs is tibs.Tibs
    assert bitformat.Mutibs is tibs.Mutibs
    assert "Bits" not in bitformat.__all__
    assert "MutableBits" not in bitformat.__all__
    assert not hasattr(bitformat, "Bits")
    assert not hasattr(bitformat, "MutableBits")


def test_old_bitformat_container_aliases_are_not_patched():
    t = Tibs("0x1234")
    m = t.to_mutibs()

    for name in ["to_bits", "to_mutable_bits", "as_bits", "u_le", "u_be"]:
        assert not hasattr(t, name)
        assert not hasattr(m, name)


def test_patched_info_and_pp_are_available_on_direct_tibs_classes():
    t = Tibs.from_dtype("u8", 10)
    m = t.to_mutibs()

    assert "unsigned int = 10" in t.info()
    assert "unsigned int = 10" in m.info()

    stream = io.StringIO()
    t.pp("u4", "bin4", show_offset=False, stream=stream)
    text = stream.getvalue()
    assert "<Tibs, dtype1='u4', dtype2='bin4', length=8 bits>" in text
    assert "10" in text


@pytest.mark.parametrize("cls", [Tibs, Mutibs])
def test_patched_from_dtype_and_unpack(cls):
    b = cls.from_dtype("u16_le", 0x1234)
    assert isinstance(b, cls)
    assert b.unpack("u16_le") == 0x1234
    assert b.le.u == 0x1234
    assert b.be.u == 0x3412

    native = cls.from_dtype("u16_ne", 0x2345)
    assert native.unpack("u16_ne") == 0x2345


@pytest.mark.parametrize("cls", [Tibs, Mutibs])
def test_patched_bool_and_bits_properties(cls):
    assert cls.from_dtype("bool", True).bool is True
    assert cls.from_dtype("bool", False).bool is False

    bits = cls.from_dtype("bits3", "0b101").bits
    assert isinstance(bits, Tibs)
    assert bits == "0b101"


def test_mutibs_replace_uses_tibs_native_return_value():
    m = Mutibs("0b0101")
    count = m.replace("0b1", "0b11")
    assert count == 2
    assert m == "0b011011"
