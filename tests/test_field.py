import keyword

import pytest
from bitformat import Dtype, Bits, Field, DtypeSingle, Expression, DtypeArray, DtypeTuple
from bitformat._common import DtypeName
from hypothesis import given, assume
import hypothesis.strategies as st


class TestCreation:
    def test_creation_from_dtype(self):
        d = DtypeSingle.from_params(DtypeName.BYTES, 2)
        assert d.size == 2
        assert d.bit_length == 16

        ds = [Dtype.from_string(x) for x in ["bytes3", "u9", "i4", "f32", "bits11"]]
        for d in ds:
            f = Field.from_params(d)
            assert f.dtype == d
            f2 = Field(str(d))
            assert f2.dtype == f.dtype

    @given(st.integers(0, 255))
    def test_creation_from_dtype_with_value(self, x):
        f = Field.from_params(Dtype.from_string("u8"), value=x)
        assert f.value == x
        f2 = Field(f"const u8 = {x}")
        assert f2.value == x

    def test_creation_from_bits1(self):
        b = Bits("0xf, 0b1")
        f1 = Field.from_bits(b)
        assert f1.to_bits() == b
        assert f1.const is True
        f2 = Field.from_bits(b"123")
        assert f2.value == b"123"
        b = f2.to_bits()
        assert b.to_bytes() == b"123"

# TODO: Reinstate this test
    # @given(name=st.text())
    # def test_creation_with_names(self, name):
    #     assume(name != "")
    #     if name.isidentifier() and "__" not in name and not keyword.iskeyword(name):
    #         f = Field.from_params("u8", name)
    #         assert f.name == name
    #         f2 = Field.from_string(f"{name}: u8")
    #         assert f2.name == name
    #         with pytest.raises(ValueError):
    #             _ = Field.from_params(f"{name}: u8", name=name)
    #     else:
    #         with pytest.raises(ValueError):
    #             _ = Field.from_params("u8", name)

    def test_creation_from_strings(self):
        f = Field.from_string(" flag_12 : bool")
        assert f.dtype == DtypeSingle.from_params(DtypeName.BOOL)
        assert f.name == "flag_12"
        assert f.value is None
        f = Field.from_string("const u3 = 3")
        assert f.dtype == DtypeSingle.from_params(DtypeName.UINT, 3)
        assert f.value == 3
        assert f.name == ""
        assert f.to_bits() == "0b011"

    @given(st.binary())
    def test_creation_from_bytes(self, b):
        f = Field.from_params("bytes", name="hello", value=b)
        assert f.value == b
        assert f.name == "hello"
        assert f.dtype == DtypeSingle.from_params(DtypeName.BYTES, size=len(b))
        assert f.dtype.bit_length == len(b) * 8

        f = Field.from_bytes(b, name="hello")
        assert f.value == b
        assert f.name == "hello"
        assert f.dtype == DtypeSingle.from_params(DtypeName.BYTES, size=len(b))
        assert f.dtype.bit_length == len(b) * 8

    @given(st.binary())
    def test_creation_from_bits(self, b):
        b = Bits.from_bytes(b)
        if b:
            f = Field.from_bits(b, "hello")
            assert f.value == b
            assert f.name == "hello"
            assert f.dtype.name is DtypeName.BITS
            assert f.dtype.bit_length == len(b)

    def test_string_creation_with_const(self):
        f1 = Field.from_string("f1: u1 = 1")
        f2 = Field.from_string("f2: const u1 = 1")
        assert f1 != f2
        assert f2.const
        assert not f1.const
        f1.clear()
        f2.clear()
        f1.pack(0)
        assert f1.to_bits() == "0b0"
        assert f2.to_bits() == "0b1"


class TestBuilding:
    # @given(x=st.integers(0, 1023), name=st.text().filter(str.isidentifier or keyword.iskeyword))
    # def test_building_with_keywords(self, x, name):
    #     assume("__" not in name)
    #     f = Field.from_string(f"{name} :u10")
    #     f.pack([], **{name: x})
    #     assert f.to_bits() == Bits.from_string(f"u10={x}")

    def test_building_lots_of_types(self):
        f = Field("u4")
        f.pack(15)
        assert f.to_bits() == "0xf"
        f = Field("i4")
        f.pack(-8)
        assert f.to_bits() == "0x8"
        f = Field("bytes3")
        f.pack(b"abc")
        assert f.to_bits() == "0x616263"
        f = Field("bits11")
        with pytest.raises(ValueError):
            f.pack(Bits.from_string("0x7ff"))
        f.pack(Bits.from_string("0b111, 0xff"))
        assert f.to_bits() == "0b11111111111"

    def test_building_with_const(self):
        f = Field.from_string("  const  u4 =8")
        b = f.to_bits()
        assert b == "0x8"
        f.clear()
        b = f.to_bits()
        assert b == "0x8"
        f.const = False
        assert f.value == 8
        f.clear()
        assert f.value is None


def test_field_str():
    f = Field.from_params("u8", name="x")
    assert str(f) == "x: u8"
    f = Field("u8")
    assert str(f) == "u8"
    f = Field.from_params("u8", value=8)
    assert str(f) == "u8 = 8"
    f = Field.from_params("u8", value=8, name="x")
    assert str(f) == "x: u8 = 8"


def test_field_array():
    f = Field.from_string("[u8; 3]")
    assert f.dtype == Dtype.from_string("[u8; 3]")
    assert f.dtype == DtypeArray.from_params(DtypeName.UINT, 8, 3)
    f.pack([1, 2, 3])
    b = f.to_bits()
    assert b == "0x010203"
    assert type(b) is Bits
    f.clear()
    assert f.value is None
    v = f.parse(b)
    assert f.value == (1, 2, 3)
    assert v == 24


def test_simple_array_parse():
    f = Field.from_string("[u8; 2]")
    f.parse("0x0102")
    assert f.value == (1, 2)


def test_creation():
    f = Field("u8 = 12")
    assert f.value == 12
    assert f.const is False
    f2 = Field("const u8 = 12")
    assert f2.const is True


def test_creation_with_bytes_string():
    f = Field.from_string('bytes3 = b"abc"')
    assert f.value == b"abc"
    f = Field('const bytes3 = b"abc"')
    assert f.const is True
    assert f.value == b"abc"


def test_creation_with_bool_string():
    f = Field.from_string("bool=True")
    assert f.value == True
    f = Field("const bool=False")
    assert f.const is True
    assert f.value == False
    g = Field("x: bool=1")
    assert g.value == True
    with pytest.raises(ValueError):
        _ = Field("x: bool=false")


def test_const_equality():
    a = Field("const i5=1")
    b = Field("i5=1")
    assert a != b


def test_size_expression():
    f = Field.from_params(DtypeSingle.from_params(DtypeName.UINT, size=Expression('{5}')))
    s = Dtype("u{5}")
    assert f.dtype == s
    assert str(f) == "u5"
    g = Field(" u { 5 } ")
    assert str(g) == "u5"
    assert f == g

def test_unpack():
    f = Field.from_string("[i9; 4]")
    f.pack([5, -5, 0, 100])
    assert f.unpack() == (5, -5, 0, 100)
    f.clear()
    with pytest.raises(ValueError):
        _ = f.unpack()

def test_unpack_with_unknown_items():
    f = Field("[i9; ]")
    assert str(f) == "[i9;]"
    f.pack([5, -5, 0, 100])
    assert f.unpack() == (5, -5, 0, 100)

def test_multiline_fields():
    f1 = Field.from_string("x: u8")
    f2 = Field.from_string("x: u8\n")
    f3 = Field.from_string("x: \nu8")
    assert f1 == f2
    assert f2 == f3

def test_stretchy_field():
    s = Field("u")
    v = s.unpack("0xff")
    assert v == 255
    assert Dtype("i").unpack("0xf") == -1
    assert Field("i: i").unpack("0xf") == -1
    f = Field("f")
    assert f.unpack("0x0000") == 0.0
    assert f.unpack("0x3f800000") == 1.0
    with pytest.raises(ValueError):
        _ = f.unpack("0x3f")


def test_disallowed_names():
    with pytest.raises(ValueError):
        f = Field("if: u8")
    with pytest.raises(ValueError):
        f = Field("else: u8")
    with pytest.raises(ValueError):
        f = Field("__starting_with_underscores: u8")
    with pytest.raises(ValueError):
        f = Field("containing__double_underscores: u8")


def test_create_from_dtype_list():
    with pytest.raises(ValueError):
        f = Field("u8, u8")


def test_eq():
    f = Field("u8")
    assert f == Field("u8")
    assert f != Field("i8")
    assert f != Field("u8 = 12")
    g = Field("i8 = 12")
    assert g != Field("const i8 = 12")
    h = Field("sparrow: bool")
    assert h != Field("heron: bool")
    a = Field("bool = True")
    b = Field("bool = False")
    assert a != b


def test_field_with_dtype_tuple():
    f = Field("(u8, u8)")
    assert f.dtype == DtypeTuple("(u8, u8)")
    assert f.value is None
    f.pack([1, 2])
    assert f.value == (1, 2)
    assert f.to_bits() == "0x0102"
    f.clear()
    assert f.value is None
    assert str(f) == "(u8, u8)"
    assert repr(f) == "Field('(u8, u8)')"
    # f.parse("0x0304")
    # assert f.value == (3, 4)
    # assert f.bit_length == 16