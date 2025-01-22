import pytest
import sys
from bitformat import Dtype, Bits, Endianness, DtypeTuple
from bitformat._dtypes import DtypeDefinition, Register

sys.path.insert(0, "..")


class TestBasicFunctionality:
    def test_setting_bool(self):
        b = Dtype("bool")
        assert str(b) == "bool"
        assert b.name == "bool"
        assert b.size == 1
        assert b.bit_length == 1

        b2 = Dtype.from_string("bool1")
        assert b == b2
        # self.assertTrue(b is b2)

    def test_setting_with_length(self):
        d = Dtype.from_params("u", 12)
        assert str(d) == "u12"
        assert d.size == 12
        assert d.name == "u"

    def test_build_errors(self):
        dtype = Dtype.from_string("u8")
        value = "not_an_integer"
        with pytest.raises(ValueError):
            dtype.pack(value)

    def test_pack(self):
        dtype = Dtype("i88")
        x = dtype.pack(10001)
        assert x.i == 10001

    def test_unpack(self):
        dtype = Dtype("u12")
        x = dtype.unpack("0x3ff")
        assert x == 1023

    def test_immutability(self):
        d = Dtype("f32")
        with pytest.raises(AttributeError):
            d.name = "uint8"

    def test_building_bits(self):
        d = Dtype("bits3")
        a = d.pack("0b101")
        assert a == "0b101"
        with pytest.raises(ValueError):
            d.pack("0b1010")

    def test_building_bin(self):
        d = Dtype.from_string("bin9")
        a = d.pack("0b000111000")
        assert a == "0b000111000"
        with pytest.raises(ValueError):
            d.pack("0b0001110000")

    def test_building_ints(self):
        d = Dtype("i3")
        a = d.pack(-3)
        assert a == "0b101"
        with pytest.raises(ValueError):
            d.pack(4)


class TestChangingTheRegister:
    def test_retrieving_meta_dtype(self):
        r = Register()
        u = r.name_to_def["u"]
        u2 = r.name_to_def["u"]
        assert u == u2
        with pytest.raises(KeyError):
            i = r.name_to_def["integer"]

    # def test_removing_type(self):
    #     del Register()['bool']
    #     with pytest.raises(KeyError):
    #         i = Register()['bool']
    #     with pytest.raises(KeyError):
    #         del Register()['penguin']


class TestCreatingNewDtypes:
    def test_new_type(self):
        md = DtypeDefinition("uintr", "A new type", Bits._setuint, Bits._getuint)
        Register().add_dtype(md)
        a = Bits("0xf")
        assert a.uintr == 15
        a = Bits.from_dtype("uintr4", 1)
        assert a == "0x1"
        a += "uintr100=0"
        assert a == "0x1, 0b" + "0" * 100

    def test_new_type_with_getter(self):
        def get_fn(bs):
            return bs.count(1)

        md = DtypeDefinition("counter", "Some sort of counter", None, get_fn)
        Register().add_dtype(md)
        a = Bits.from_string("0x010f")
        assert a.counter == 5
        with pytest.raises(AttributeError):
            a.counter = 4

    def test_invalid_dtypes(self):
        with pytest.raises(TypeError):
            _ = Dtype()
        with pytest.raises(ValueError):
            _ = Dtype("float17")
        with pytest.raises(ValueError):
            _ = Dtype("[u8]")
        with pytest.raises(ValueError):
            _ = Dtype("u8, i8")


def test_len():
    a = Dtype("bytes2")
    assert a.size == 2
    assert a.items == 1
    assert a.bit_length == 16
    a = Dtype("[bytes1; 2]")
    assert a.size == 1
    assert a.items == 2
    assert a.bit_length == 16
    a = Dtype("u8")
    assert a.size == 8
    assert a.bit_length == 8
    assert a.items == 1
    a = Dtype("bits8")
    assert a.size == 8
    assert a.bit_length == 8
    assert a.items == 1
    a = Dtype("bool")
    assert a.size == 1
    assert a.bit_length == 1
    assert a.items == 1
    a = Dtype("bytes4")
    assert a.size == 4
    assert a.bit_length == 32
    assert a.items == 1
    a = Dtype("[u8; 3]")
    assert a.size == 8
    assert a.bit_length == 24
    assert a.items == 3
    a = Dtype("[bytes3; 4]")
    assert a.size == 3
    assert a.bit_length == 96
    assert a.items == 4


def test_len_errors():
    for x in ["u", "[u8;]"]:
        d = Dtype(x)
        with pytest.raises(TypeError):
            _ = len(d)


def test_endianness():
    d_le = Dtype.from_params("u", 16, endianness=Endianness.LITTLE)
    d_be = Dtype.from_params("u", 16, endianness=Endianness.BIG)
    d_ne = Dtype.from_params("u", 16, endianness=Endianness.NATIVE)

    be = d_be.pack(0x1234)
    le = d_le.pack(0x1234)

    assert be.unpack(d_be) == 0x1234
    assert le.unpack(d_le) == 0x1234

    assert be == "0x1234"
    assert le == "0x3412"


def test_endianness_type_str():
    d_le = Dtype.from_params("u", 16, endianness=Endianness.LITTLE)
    d_be = Dtype.from_params("u", 16, endianness=Endianness.BIG)
    d_ne = Dtype.from_params("u", 16, endianness=Endianness.NATIVE)

    d_le2 = Dtype("u_le16")
    d_be2 = Dtype("u_be16")
    d_ne2 = Dtype("u_ne16")

    assert d_le == d_le2
    assert d_be == d_be2
    assert d_ne == d_ne2


def test_endianness_errors():
    with pytest.raises(ValueError):
        _ = Dtype.from_params("u", 15, endianness=Endianness.BIG)
    with pytest.raises(ValueError):
        _ = Dtype.from_params("bool", endianness=Endianness.LITTLE)
    with pytest.raises(ValueError):
        _ = Dtype.from_params("bytes", 16, endianness=Endianness.LITTLE)


def test_dtype_list_creation():
    d = DtypeTuple("u8, u16, u32, bool")
    assert len(d) == 4
    assert d.bit_length == 8 + 16 + 32 + 1

    d2 = DtypeTuple.from_params(d)
    assert d == d2
    d = DtypeTuple.from_params(["i5", *d[1:]])
    assert d[0] == "i5"
    assert d.bit_length == 5 + 16 + 32 + 1
    assert d != d2


def test_dtype_list_packing():
    d = DtypeTuple("bool, u8, f16")
    a = d.pack([1, 254, 0.5])
    assert a == "0b1, 0xfe, 0x3800"
    with pytest.raises(ValueError):
        _ = d.pack([0, 0, 0, 0])
    with pytest.raises(ValueError):
        _ = d.pack([0, 0])


def test_dtype_list_unpacking():
    d = DtypeTuple("bool, u8, f16")
    a = d.unpack("0b1, 0xfe, 0x3800")
    assert a == (1, 254, 0.5)


def test_dtype_list_unpacking_with_pad():
    s = Bits.from_string("0b111000111")
    d = DtypeTuple("bits3, pad3, bits3")
    x, y = d.unpack(s)
    assert (x, y.unpack("u")) == ("0b111", 7)


def test_dtype_list_slicing():
    d = DtypeTuple("u1, u2, u3, u4, u5")
    d2 = d[1:4]
    assert d2 == DtypeTuple("u2, u3, u4")


def test_dtype_str_with_le():
    d = Dtype("u_le16")
    assert str(d) == "u_le16"
    d = Dtype("f_be16")
    assert str(d) == "f_be16"
    d = Dtype("i_ne16")
    assert str(d) == "i_ne16"
    assert repr(d) == "Dtype('i_ne16')"


def test_hashing():
    a = Dtype('u8')
    b = Dtype('u_be8')
    c = Dtype('u_le8')
    d = Dtype('u_ne8')
    e = Dtype('i8')
    f = Dtype('[u8; 1]')
    g = Dtype('[u8; 2]')
    h = DtypeTuple('u8')
    i = DtypeTuple('u8, u8')
    s = {a, b, c, d, e, f, g, h, i}
    assert len(s) == 9

def test_str():
    a = Dtype('u_le8')
    b = DtypeTuple('bool, [i5; 1]')
    assert str(a) == 'u_le8'
    assert str(b) == 'bool, [i5; 1]'
    assert repr(a) == "Dtype('u_le8')"
    assert repr(b) == "DtypeTuple('bool, [i5; 1]')"
    nt = DtypeDefinition("pingu", "A new type", Bits._setuint, Bits._getuint)
    s = "DtypeDefinition(name='pingu', description='A new type', return_type=Any, is_signed=False, allowed_lengths=(), bits_per_character=None)"
    assert str(nt) == s
    assert repr(nt) == s
