import pytest
import sys

import bitformat
from bitformat import Dtype, Bits, Endianness, DtypeTuple, DtypeSingle, DtypeArray
from bitformat._dtypes import DtypeDefinition, Register
from bitformat._common import DtypeKind, Expression, ExpressionError

sys.path.insert(0, "..")


class TestBasicFunctionality:
    def test_setting_bool(self):
        b = Dtype("bool")
        assert str(b) == "bool"
        assert b.kind is DtypeKind.BOOL
        assert b.size == 1
        assert b.bit_length == 1

        b2 = Dtype.from_string("bool1")
        assert b == b2
        # self.assertTrue(b is b2)

    def test_setting_with_length(self):
        d = DtypeSingle.from_params(DtypeKind.UINT, 12)
        assert str(d) == "u12"
        assert d.size == 12
        assert d.kind is DtypeKind.UINT

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
            d.kind = "uint8"

    def test_building_bits(self):
        d = Dtype.from_string("bits3")
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
        u = r.kind_to_def[DtypeKind("u")]
        u2 = r.kind_to_def[DtypeKind("u")]
        assert u == u2
        with pytest.raises(KeyError):
            _ = r.kind_to_def["bool"]

    # def test_removing_type(self):
    #     del Register()['bool']
    #     with pytest.raises(KeyError):
    #         i = Register()['bool']
    #     with pytest.raises(KeyError):
    #         del Register()['penguin']


# class TestCreatingNewDtypes:
#     def test_new_type(self):
#
#         md = DtypeDefinition("uintr", "A new type", Bits._set_u, Bits._get_u)
#         Register().add_dtype(md)
#         a = Bits("0xf")
#         assert a.uintr == 15
#         a = Bits.from_dtype("uintr4", 1)
#         assert a == "0x1"
#         a += "uintr100=0"
#         assert a == "0x1, 0b" + "0" * 100
#
#     def test_new_type_with_getter(self):
#         def get_fn(bs):
#             return bs.count(1)
#
#         md = DtypeDefinition("counter", "Some sort of counter", None, get_fn)
#         Register().add_dtype(md)
#         a = Bits.from_string("0x010f")
#         assert a.counter == 5
#         with pytest.raises(AttributeError):
#             a.counter = 4

    def test_invalid_dtypes(self):
        with pytest.raises(TypeError):
            _ = Dtype()
        with pytest.raises(ValueError):
            _ = Dtype.from_string("float17")
        with pytest.raises(ValueError):
            _ = Dtype("[u8]")
        with pytest.raises(ValueError):
            _ = Dtype("u8, i8")


def test_len():
    a = Dtype("bytes2")
    assert isinstance(a, DtypeSingle)
    assert a.size == 2
    assert a.bit_length == 16
    a = Dtype("[bytes1; 2]")
    assert isinstance(a, DtypeArray)
    assert a.size == 1
    assert a.items == 2
    assert a.bit_length == 16
    a = DtypeSingle("u8")
    assert a.size == 8
    assert a.bit_length == 8
    a = DtypeSingle("bits8")
    assert a.size == 8
    assert a.bit_length == 8
    a = DtypeSingle("bool")
    assert a.size == 1
    assert a.bit_length == 1
    a = DtypeSingle("bytes4")
    assert a.size == 4
    assert a.bit_length == 32
    a = DtypeSingle("f")
    assert a.size == Expression('{None}')
    assert a.size.is_none()
    assert a.bit_length is None
    a = DtypeArray("[u8; 3]")
    assert a.size == 8
    assert a.bit_length == 24
    assert a.items == 3
    a = DtypeArray("[bytes3;]")
    assert a.size == 3
    assert a.bit_length is None
    assert a.items is None
    a = DtypeArray("[bytes3; 4]")
    assert a.size == 3
    assert a.bit_length == 96
    assert a.items == 4
    a = Dtype("(u8, f16, bool)")
    assert isinstance(a, DtypeTuple)
    assert a.bit_length == 25
    assert a.items == 3
    a = DtypeTuple("([u8; 10], [bool; 0], i20)")
    assert a.bit_length == 100
    assert a.items == 3


def test_len_errors():
    for x in ["u", "[u8;]"]:
        d = Dtype(x)
        with pytest.raises(TypeError):
            _ = len(d)


def test_endianness():
    d_le = DtypeSingle.from_params(DtypeKind.UINT, 16, endianness=Endianness.LITTLE)
    d_be = DtypeSingle.from_params(DtypeKind.UINT, 16, endianness=Endianness.BIG)
    d_ne = DtypeSingle.from_params(DtypeKind.UINT, 16, endianness=Endianness.NATIVE)

    be = d_be.pack(0x1234)
    le = d_le.pack(0x1234)

    assert be.unpack(d_be) == 0x1234
    assert le.unpack(d_le) == 0x1234

    assert be == "0x1234"
    assert le == "0x3412"


def test_endianness_type_str():
    d_le = DtypeSingle.from_params(DtypeKind.UINT, 16, endianness=Endianness.LITTLE)
    d_be = DtypeSingle.from_params(DtypeKind.UINT, 16, endianness=Endianness.BIG)
    d_ne = DtypeSingle.from_params(DtypeKind.UINT, 16, endianness=Endianness.NATIVE)

    d_le2 = Dtype("u_le16")
    d_be2 = Dtype("u_be16")
    d_ne2 = Dtype("u_ne16")

    assert d_le == d_le2
    assert d_be == d_be2
    assert d_ne == d_ne2


def test_endianness_errors():
    with pytest.raises(ValueError):
        _ = DtypeSingle.from_params(DtypeKind.UINT, 15, endianness=Endianness.BIG)
    with pytest.raises(ValueError):
        _ = DtypeSingle.from_params(DtypeKind.BOOL, endianness=Endianness.LITTLE)
    with pytest.raises(ValueError):
        _ = DtypeSingle.from_params(DtypeKind.BYTES, 16, endianness=Endianness.LITTLE)


def test_dtype_tuple_packing():
    d = DtypeTuple("(bool, u8, f16)")
    a = d.pack([1, 254, 0.5])
    assert a == "0b1, 0xfe, 0x3800"
    with pytest.raises(ValueError):
        _ = d.pack([0, 0, 0, 0])
    with pytest.raises(ValueError):
        _ = d.pack([0, 0])


def test_dtype_tuple_unpacking():
    d = Dtype("(bool, u8, f16)")
    a = d.unpack("0b1, 0xfe, 0x3800")
    assert a == (1, 254, 0.5)


def test_dtype_tuple_unpacking_with_pad():
    s = Bits.from_string("0b111000111")
    d = Dtype(" ( bits3 , pad3 , bits3 , ) ")
    x, y = d.unpack(s)
    assert (x, y.unpack("u")) == ("0b111", 7)


def test_dtype_tuple_slicing():
    d = DtypeTuple("(u1, u2, u3, u4, u5)")
    d2 = d[1:4]
    assert d2 == DtypeTuple("(u2, u3, u4)")


def test_dtype_str_with_le():
    d = Dtype("u_le16")
    assert str(d) == "u_le16"
    d = Dtype.from_string("f_be16")
    assert str(d) == "f_be16"
    d = Dtype("i_ne16")
    assert str(d) == "i_ne16"
    assert repr(d) == "DtypeSingle('i_ne16')"


def test_hashing():
    a = Dtype('u8')
    b = Dtype('u_be8')
    c = Dtype('u_le8')
    d = Dtype('u_ne8')
    e = Dtype('i8')
    f = Dtype('[u8; 1]')
    g = Dtype('[u8; 2]')
    h = Dtype('(u8)')
    i = Dtype('(u8, u8)')
    s = {a, b, c, d, e, f, g, h, i}
    assert len(s) == 9

def test_str():
    a = Dtype('u_le8')
    b = Dtype('(bool, [i5; 1])')
    assert str(a) == 'u_le8'
    assert str(b) == '(bool, [i5; 1])'
    assert repr(a) == "DtypeSingle('u_le8')"
    assert repr(b) == "DtypeTuple('(bool, [i5; 1])')"
    nt = DtypeDefinition("pingu", "A new type", "new", Bits._set_u, Bits._get_u)
    s = "DtypeDefinition(kind='pingu', description='A new type', short_description='new', return_type=Any, is_signed=False, allowed_lengths=(), bits_per_character=None)"
    assert str(nt) == s
    assert repr(nt) == s

def test_unpacking_dtype_array_with_no_length():
    d = Dtype('[bool;]')
    assert str(d) == '[bool;]'
    assert d.unpack('0b110') == (True, True, False)
    assert Dtype('[u8;]').unpack('0x0001f') == (0, 1)

# def test_unpacking_dtypetuple_array_with_no_length():
#     # We shouldn't even be able to create the dtypetuple with no length array
#     with pytest.raises(ValueError):
#         _ = DtypeTuple('([bool;], u8)')
#     with pytest.raises(ValueError):
#         _ = DtypeTuple('([u8;],)')

def test_creating_dtype_with_no_size():
    d = Dtype('f')
    with pytest.raises(ValueError):
        _ = d.pack(5.0)
    b = Bits.from_dtype('f32', 12.5)
    assert b.unpack(d) == 12.5
    with pytest.raises(ValueError):
        _ = Dtype('[u;4]')
    with pytest.raises(ValueError):
        _ = Dtype('[i;]')

def test_from_string_methods():
    a = Dtype.from_string('u_le16')
    b = Dtype.from_string('[u8; 2]')
    c = Dtype.from_string('(bool, u15)')
    ap = DtypeSingle('u_le16')
    bp = DtypeArray('[u8; 2]')
    cp = DtypeTuple('(bool, u15)')
    assert isinstance(a, DtypeSingle)
    assert isinstance(b, DtypeArray)
    assert isinstance(c, DtypeTuple)
    assert isinstance(ap, DtypeSingle)
    assert isinstance(bp, DtypeArray)
    assert isinstance(cp, DtypeTuple)
    assert a == ap
    assert b == bp
    assert c == cp

def test_expression_dtype_single():
    a = Dtype('u{x}')
    assert isinstance(a, DtypeSingle)
    assert a.kind is DtypeKind.UINT
    assert str(a) == 'u{x}'

def test_dtype_array_from_str():
    a = Dtype('[u8; 2]')
    assert isinstance(a, DtypeArray)
    assert a.size == 8
    assert a.items == 2
    assert a.bit_length == 16
    b = Dtype('[f{x}; {y}]')
    assert isinstance(b, DtypeArray)
    assert b.size == Expression('{x}')
    assert b.items == Expression('{y}')
    assert b.bit_length is None

def test_dtype_str():
    try:
        bitformat.Options().no_color = False
        a = Dtype('u8')
        assert str(a) == 'u8'
        b = Dtype('[u8; 3]')
        assert str(b) == '[u8; 3]'
        c = Dtype('(bool, u8)')
        assert str(c) == '(bool, u8)'
    finally:
        bitformat.Options().no_color = True

def test_evaluate():
    concrete = Dtype('u32')
    e1 = Dtype('u{my_size}')
    e2 = Dtype('[u8; {my_items}]')

    assert e1.evaluate(my_size=32) == concrete
    assert e2.evaluate(my_items=10).bit_length == 80

def test_unpack_dtype_tuple():
    s = Bits('0x100')
    with pytest.raises(ExpressionError):
        _ = s.unpack('u{x}')
    x = s.unpack('u')
    y = s.unpack('(u)')
    assert y[0] == x

def test_unpack_dtype_tuple_with_single_dynamic_type():
    d = Dtype('(u8, [u8;], u8)')
    s = Bits.from_string('0x010203040506')
    x = d.unpack(s)
    assert x == (1, (2, 3, 4, 5), 6)
    x = s.unpack(d)
    assert x == (1, (2, 3, 4, 5), 6)
    x = s.unpack('(u8, u, u8)')
    assert x == (1, 0x02030405, 6)

def test_unpack_dtype_array_with_no_length():
    d = Dtype('[u{x};]')
    b = Bits('0x1234')
    with pytest.raises(ValueError):
        _ = d.unpack(b)