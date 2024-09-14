#!/usr/bin/env python
import pytest
import io
import re
from hypothesis import given
import hypothesis.strategies as st
import bitformat
from bitformat import Dtype, Bits, Field


def test_build():
    a = Bits.pack('u12', 104)
    assert a == 'u12 = 104'
    b = Bits.pack('bool', False)
    assert len(b) == 1
    assert b[0] == 0
    c = Bits.pack(Dtype('f64'), 13.75)
    assert len(c) == 64
    assert c.unpack(['f64']) == [13.75]


def remove_unprintable(s: str) -> str:
    colour_escape = re.compile(r'(?:\x1B[@-_])[0-?]*[ -/]*[@-~]')
    return colour_escape.sub('', s)

class TestCreation:
    def test_creation_from_bytes(self):
        s = Bits.from_bytes(b'\xa0\xff')
        assert (len(s), s.unpack('hex')) == (16, 'a0ff')

    @given(st.binary())
    def test_creation_from_bytes_roundtrip(self, data):
        s = Bits.pack('bytes', data)
        assert s.bytes == data

    def test_creation_from_hex(self):
        s = Bits.pack('hex', '0xA0ff')
        assert (len(s), s.unpack('hex')) == (16, 'a0ff')

    def test_creation_from_hex_with_whitespace(self):
        s = Bits('  \n0 X a  4e       \r3  \n')
        assert s.hex == 'a4e3'

    @pytest.mark.parametrize("bad_val", ['0xx0', '0xX0', '0Xx0', '-2e'])
    def test_creation_from_hex_errors(self, bad_val: str):
        with pytest.raises(ValueError):
            Bits.pack('hex', bad_val)

    def test_creation_from_bin(self):
        s = Bits.pack('bin', '1010000011111111')
        assert (len(s), s.hex) == (16, 'a0ff')
        s = Bits.from_string('0b00')[:1]
        assert s.unpack('bin') == '0'
        s = Bits.pack('bin', ' 0000 \n 0001\r ')
        assert s.bin == '00000001'

    def test_creation_from_uint_errors(self):
        # test = Bits.pack('u10', -1)

        with pytest.raises(ValueError):
            Bits.pack('u10', -1)
        with pytest.raises(ValueError):
            Bits.pack('uint', 12)
        with pytest.raises(ValueError):
            Bits.pack('uint2', 4)
        with pytest.raises(ValueError):
            Bits.pack('u0', 1)
        with pytest.raises(ValueError):
            Bits.pack('u2', 12)

    def test_creation_from_int(self):
        s = Bits.pack('i4', 0)
        assert s.unpack([Dtype.from_string('bin4')])[0] == '0000'
        s = Bits.pack(Dtype.from_string('i2'), 1)
        assert s.bin == '01'
        s = Bits.pack('i11', -1)
        assert s.bin == '11111111111'
        s = Bits.from_string('i12=7')
        assert s.i == 7
        s = Bits.pack(Dtype.from_string('i108'), -243)
        assert (s.unpack(Dtype('i')), len(s)) == (-243, 108)
        for length in range(6, 10):
            for value in range(-17, 17):
                s = Bits.pack(Dtype.from_parameters('i', length), value)
                assert (s.i, len(s)) == (value, length)

    @pytest.mark.parametrize("int_, length", [[-1, 0], [12, 0], [4, 3], [-5, 3]])
    def test_creation_from_int_errors(self, int_, length):
        with pytest.raises(ValueError):
            _ = Bits.pack(Dtype.from_parameters('int', length), int_)

    def test_creation_from_bool(self):
        a = Bits.pack('bool', False)
        assert a == '0b0'
        b = Bits.from_string('bool=0')
        assert b == [0]

    def test_creation_from_bool_errors(self):
        with pytest.raises(ValueError):
            _ = Bits.pack('bool2', 0)

    def test_creation_keyword_error(self):
        with pytest.raises(ValueError):
            Bits.pack('squirrel', 5)

    def test_creation_from_memoryview(self):
        x = bytes(bytearray(range(20)))
        m = memoryview(x[10:15])
        b = Bits.pack('bytes', m)
        assert b.unpack(['[u8; 5]']) == [(10, 11, 12, 13, 14)]


class TestInitialisation:
    def test_empty_init(self):
        a = Bits()
        assert a == ''

    def test_find(self):
        a = Bits.from_string('0xabcd')
        r = a.find('0xbc')
        assert r == 4
        r = a.find('0x23462346246', bytealigned=True)
        assert r is None

    def test_rfind(self):
        a = Bits.from_string('0b11101010010010')
        b = a.rfind('0b010')
        assert b == 11

    def test_find_all(self):
        a = Bits('0b0010011')
        b = list(a.find_all([1]))
        assert b == [2, 5, 6]
        t = Bits('0b10')
        tp = list(t.find_all('0b1'))
        assert tp == [0]


class TestCut:
    def test_cut(self):
        s = Bits().join(['0b000111']*10)
        for t in s.cut(6):
            assert t == '0b000111'

def test_unorderable():
    a = Bits('0b000111')
    b = Bits('0b000111')
    with pytest.raises(TypeError):
        _ = a < b
    with pytest.raises(TypeError):
        _ = a > b
    with pytest.raises(TypeError):
        _ = a <= b
    with pytest.raises(TypeError):
        _ = a >= b


class TestPadToken:

    def test_creation(self):
        with pytest.raises(ValueError):
            _ = Bits.from_string('pad10')
        with pytest.raises(ValueError):
            _ = Bits.from_string('pad')

    def test_unpack(self):
        s = Bits.from_string('0b111000111')
        x, y = s.unpack(['bits3', 'pad3', 'bits3'])
        assert (x, y.unpack('u')) == ('0b111', 7)
        x, y = s.unpack(['bits2', 'pad2', 'bin5'])
        assert (x.unpack(['u2'])[0], y) == (3, '00111')
        x = s.unpack(['pad1', 'pad2', 'pad3'])
        assert x == []


def test_adding():
    a = Bits.from_string('0b0')
    b = Bits.from_string('0b11')
    c = a + b
    assert c == '0b011'
    assert a == '0b0'
    assert b == '0b11'

        
class TestContainsBug:

    def test_contains(self):
        a = Bits.from_string('0b1, 0x0001dead0001')
        assert '0xdead' in a
        assert not '0xfeed' in a

        assert '0b1' in Bits.from_string('0xf')
        assert not '0b0' in Bits.from_string('0xf')


class TestUnderscoresInLiterals:
    def test_hex_creation(self):
        a = Bits.pack('hex', 'ab_cd__ef')
        assert a.hex == 'abcdef'
        b = Bits.from_string('0x0102_0304')
        assert b.u == 0x0102_0304

    def test_binary_creation(self):
        a = Bits.pack('bin', '0000_0001_0010')
        assert a.bin == '000000010010'
        b = Bits.from_string('0b0011_1100_1111_0000')
        assert b.bin == '0011110011110000'
        v = 0b1010_0000
        c = Bits.pack('u8', 0b1010_0000)
        assert c.u == v

    def test_octal_creation(self):
        a = Bits.pack('oct', '0011_2233_4455_6677')
        assert a.u == 0o001122334455_6677
        b = Bits.from_string('0o123_321_123_321')
        assert b.u == 0o123_321_123321


class TestPrettyPrinting:

    def test_simplest_cases(self):
        a = Bits.from_string('0b101011110000')
        s = io.StringIO()
        a.pp(stream=s)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='bin', length=12 bits> [
 0: 10101111 0000    
]
"""

        s = io.StringIO()
        a.pp('hex', stream=s)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='hex', length=12 bits> [
 0: af 0 
]
"""

        s = io.StringIO()
        a.pp('oct', stream=s)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='oct', length=12 bits> [
 0: 5360
]
"""

    def test_small_width(self):
        a = Bits.pack('u20', 0)
        s = io.StringIO()
        a.pp(fmt='bin', stream=s, width=5)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='bin', length=20 bits> [
 0: 00000000
 8: 00000000
16: 0000    
]
"""

    def test_separator(self):
        a = Bits.from_string('0x' + '0f0f'*9)
        s = io.StringIO()
        a.pp('hex32', sep='!-!', stream=s)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='hex32', length=144 bits> [
  0: 0f0f0f0f!-!0f0f0f0f!-!0f0f0f0f!-!0f0f0f0f
] + trailing_bits = 0b0000111100001111
"""

    def test_multi_line(self):
        a = Bits.zeros(100)
        s = io.StringIO()
        a.pp('bin', sep='', stream=s, width=80)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='bin', length=100 bits> [
  0: 000000000000000000000000000000000000000000000000000000000000000000000000
 72: 0000000000000000000000000000                                            
]
"""

    def test_multiformat(self):
        a = Bits.from_string('0b1111000011110000')
        s = io.StringIO()
        a.pp(stream=s, fmt='bin, hex')
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='bin, hex', length=16 bits> [
 0: 11110000 11110000 : f0 f0
]
"""
        s = io.StringIO()
        a.pp(stream=s, fmt='hex, bin12')
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='hex, bin12', length=16 bits> [
 0: f0f : 111100001111
] + trailing_bits = 0b0000
"""

    def test_multi_line_multi_format(self):
        a = Bits.ones(112)
        s = io.StringIO()
        a.pp(stream=s, fmt='bin8, hex8', width=42)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='bin8, hex8', length=112 bits> [
  0: 11111111 11111111 11111111 : ff ff ff
 24: 11111111 11111111 11111111 : ff ff ff
 48: 11111111 11111111 11111111 : ff ff ff
 72: 11111111 11111111 11111111 : ff ff ff
 96: 11111111 11111111          : ff ff   
]
"""
        s = io.StringIO()
        a.pp(stream=s, fmt='bin, hex', width=41)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='bin, hex', length=112 bits> [
  0: 11111111 11111111 : ff ff
 16: 11111111 11111111 : ff ff
 32: 11111111 11111111 : ff ff
 48: 11111111 11111111 : ff ff
 64: 11111111 11111111 : ff ff
 80: 11111111 11111111 : ff ff
 96: 11111111 11111111 : ff ff
]
"""

        a = bytearray(range(0, 256))
        b = Bits.pack('bytes', a)
        s = io.StringIO()
        b.pp(stream=s, fmt='bytes')
        assert remove_unprintable(s.getvalue()) == r"""<Bits, fmt='bytes', length=2048 bits> [
   0: ĀāĂă ĄąĆć ĈĉĊċ ČčĎď ĐđĒē ĔĕĖė ĘęĚě ĜĝĞğ  !"# $%&' ()*+ ,-./ 0123 4567 89:; <=>? @ABC DEFG HIJK LMNO PQRS TUVW XYZ[
 736: \]^_ `abc defg hijk lmno pqrs tuvw xyz{ |}~ſ ƀƁƂƃ ƄƅƆƇ ƈƉƊƋ ƌƍƎƏ ƐƑƒƓ ƔƕƖƗ Ƙƙƚƛ ƜƝƞƟ ƠơƢƣ ƤƥƦƧ ƨƩƪƫ ƬƭƮƯ ưƱƲƳ ƴƵƶƷ
1472: Ƹƹƺƻ Ƽƽƾƿ ǀǁǂǃ ǄǅǆǇ ǈǉǊǋ ǌǍǎǏ ǐǑǒǓ ǔǕǖǗ ǘǙǚǛ ǜǝǞǟ ǠǡǢǣ ǤǥǦǧ ǨǩǪǫ ǬǭǮǯ ǰǱǲǳ ǴǵǶǷ ǸǹǺǻ ǼǽǾÿ                         
]
"""

    def test_group_size_errors(self):
        a = Bits.zeros(120)
        with pytest.raises(ValueError):
            a.pp('hex3')
        with pytest.raises(ValueError):
            a.pp('hex4, oct')

    def test_zero_group_size(self):
        a = Bits.zeros(600)
        s = io.StringIO()
        a.pp('bin120', stream=s, show_offset=False)
        expected_output = """<Bits, fmt='bin120', length=600 bits> [
000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
]
"""
        assert remove_unprintable(s.getvalue()) == expected_output

        a = Bits.zeros(400)
        s = io.StringIO()
        a.pp(stream=s, fmt='hex', show_offset=False)
        expected_output = """<Bits, fmt='hex', length=400 bits> [
00000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000                                                            
]
"""
        # TODO Reallow not dividing into sections. Previously this was done using a length of 0.
        # assert remove_unprintable(s.getvalue()) == expected_output

        s = io.StringIO()
        a = Bits.from_string('u48 = 10')
        a.pp(stream=s, width=20, fmt='hex24, oct24', show_offset=False)
        expected_output = """<Bits, fmt='hex24, oct24', length=48 bits> [
000000 : 00000000
00000a : 00000012
]
"""
        assert remove_unprintable(s.getvalue()) == expected_output

    def test_oct(self):
        a = Bits.from_string('0o' + '01234567'*20)
        s = io.StringIO()
        a.pp(stream=s, fmt='oct', show_offset=False, width=20)
        expected_output = """<Bits, fmt='oct', length=480 bits> [
0123 4567 0123 4567
0123 4567 0123 4567
0123 4567 0123 4567
0123 4567 0123 4567
0123 4567 0123 4567
0123 4567 0123 4567
0123 4567 0123 4567
0123 4567 0123 4567
0123 4567 0123 4567
0123 4567 0123 4567
]
"""
        assert remove_unprintable(s.getvalue()) == expected_output

        t = io.StringIO()
        a.pp('hex24, oct', width=1, show_offset=False, stream=t)
        expected_output = """<Bits, fmt='hex24, oct', length=480 bits> [
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
053977 : 01234567
]
"""
        assert remove_unprintable(t.getvalue()) == expected_output

    def test_bytes(self):
        a = Bits.from_bytes(b'helloworld!!' * 5)
        s = io.StringIO()
        a.pp(stream=s, fmt='bytes', show_offset=False, width=48)
        expected_output = (
"""<Bits, fmt='bytes', length=480 bits> [
hell owor ld!! hell owor ld!! hell owor ld!!
hell owor ld!! hell owor ld!!               
]
""")
        assert remove_unprintable(s.getvalue()) == expected_output
        s = io.StringIO()
        a.pp(stream=s, fmt='bytes0', show_offset=False, width=40)
        expected_output = (
"""<Bits, fmt='bytes', length=480 bits> [
helloworld!!helloworld!!helloworld!!hell
oworld!!helloworld!!                    
]
"""
        )
        # TODO: Reallow not dividing into sections. Previously this was done using a length of 0.
        # assert remove_unprintable(s.getvalue()) == expected_output

    def test_bool(self):
        a = Bits.from_string('0b1100')
        s = io.StringIO()
        a.pp(stream=s, fmt='bool', show_offset=False, width=20)
        expected_output = """<Bits, fmt='bool', length=4 bits> [
1 1 0 0
]
"""
        assert remove_unprintable(s.getvalue()) == expected_output


class TestPrettyPrintingErrors:

    def test_wrong_formats(self):
        a = Bits.from_string('0x12341234')
        with pytest.raises(ValueError):
            a.pp('binary')
        with pytest.raises(ValueError):
            a.pp('bin, bin, bin')

    def test_interpret_problems(self):
        a = Bits.zeros(7)
        with pytest.raises(ValueError):
            a.pp('oct')
        with pytest.raises(ValueError):
            a.pp('hex')
        with pytest.raises(ValueError):
            a.pp('bin, bytes')


class TestPrettyPrinting_NewFormats:

    def test_float(self):
        a = Bits.from_string('f_le32=10.5')
        s = io.StringIO()
        a.pp('f_le32', stream=s)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='f_le32', length=32 bits> [
 0:                    10.5
]
"""
        s = io.StringIO()
        a.pp('f_be16', stream=s)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='f_be16', length=32 bits> [
 0:                2.578125                     0.0
]
"""

    def test_uint(self):
        a = Bits().join([Bits.pack('u12', x) for x in range(40, 105)])
        s = io.StringIO()
        a.pp('u, hex12', stream=s)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='u, hex12', length=780 bits> [
  0:   40   41   42   43   44   45   46   47   48   49   50   51 : 028 029 02a 02b 02c 02d 02e 02f 030 031 032 033
144:   52   53   54   55   56   57   58   59   60   61   62   63 : 034 035 036 037 038 039 03a 03b 03c 03d 03e 03f
288:   64   65   66   67   68   69   70   71   72   73   74   75 : 040 041 042 043 044 045 046 047 048 049 04a 04b
432:   76   77   78   79   80   81   82   83   84   85   86   87 : 04c 04d 04e 04f 050 051 052 053 054 055 056 057
576:   88   89   90   91   92   93   94   95   96   97   98   99 : 058 059 05a 05b 05c 05d 05e 05f 060 061 062 063
720:  100  101  102  103  104                                    : 064 065 066 067 068                            
]
"""

    def test_float(self):
        a = Bits.pack('f64', 76.25) + '0b11111'
        s = io.StringIO()
        a.pp('i64, f', stream=s)
        assert remove_unprintable(s.getvalue()) == """<Bits, fmt='i64, f', length=69 bits> [
 0:  4635066033680416768 :                    76.25
] + trailing_bits = 0b11111
"""

def test_unpack_array():
    a = Bits.from_string('0b1010101010101010')
    assert a.unpack(['u8', 'u4', 'u4']) == [170, 10, 10]
    assert a.unpack(['u4', 'u4', 'u8']) == [10, 10, 170]
    assert a.unpack(['u4', 'u4', 'u4', 'u4']) == [10, 10, 10, 10]

    assert a.unpack(['[u4; 4]']) == [(10, 10, 10, 10)]
    assert a.unpack('[u4; 3]') == (10, 10, 10)

def test_unpack_errors():
    with pytest.raises(ValueError):
        _ = Bits().unpack('bool')
    with pytest.raises(ValueError):
        _ = Bits('0b1').unpack('u2')
    a = Bits.from_string('0b101010101')
    with pytest.raises(ValueError):
        _ = a.unpack(['u4', 'u4', 'u4'])
    with pytest.raises(ValueError):
        _ = a.unpack('i10')
    with pytest.raises(ValueError):
        _ = a.unpack(['u8', 'u'])

def test_unpack_single():
    a = Bits('0x12345')
    assert a.unpack('[u4; 5]') == (1, 2, 3, 4, 5)
    assert a.unpack('u8') == 0x12

def test_pack_array():
    d = Dtype.from_parameters('u', 33, True, 5)
    a = Bits.pack(d, [10, 100, 1000, 32, 1])
    assert a.unpack(d) == (10, 100, 1000, 32, 1)
    assert d.return_type == tuple

def test_from_iterable():
    with pytest.raises(TypeError):
       _ = Bits.from_iterable()
    a = Bits.from_iterable([])
    assert a == Bits()
    a = Bits.from_iterable([1, 0, 1, 1])
    assert a == '0b1011'
    a = Bits.from_iterable((True,))
    assert a == 'bool=1'

def test_mul_by_zero():
    a = Bits.from_string('0b1010')
    b = a * 0
    assert b == Bits()
    b = a * 1
    assert b == a
    b = a * 2
    assert b == a + a


def test_uintne():
    s = Bits.pack('u_ne160', 454)
    t = Bits('u_ne160=454')
    assert s == t


def test_float_endianness():
    a = Bits('f_le64=12, f_be64=-0.01, f_ne64=3e33')
    x, y, z = a.unpack(['f_le64', 'f_be64', 'f_ne64'])
    assert x == 12.0
    assert y == -0.01
    assert z == 3e33
    a = Bits('f_le16=12, f_be32=-0.01, f_ne32=3e33')
    x, y, z = a.unpack(['f_le16', 'f_be32', 'f_ne32'])
    assert x / 12.0 == pytest.approx(1.0)
    assert y / -0.01 == pytest.approx(1.0)
    assert z / 3e33 == pytest.approx(1.0)


def test_non_aligned_float_reading():
    s = Bits('0b1, f32 = 10.0')
    y, = s.unpack(['pad1', 'f32'])
    assert y == 10.0
    s = Bits('0b1, f_le32 = 20.0')
    x, y = s.unpack(['bits1', 'f_le32'])
    assert y == 20.0

def test_float_errors():
    a = Bits('0x3')
    with pytest.raises(ValueError):
        _ = a.f
    for le in (8, 10, 12, 18, 30, 128, 200):
        with pytest.raises(ValueError):
            _ = Bits.pack(Dtype.from_parameters('f', le), 1.0)

def test_little_endian_uint():
    s = Bits('u16 = 100')
    assert s.unpack('u_le') == 25600
    assert s.u_le == 25600
    s = Bits('u_le16=100')
    assert s.u == 25600
    assert s.u_le == 100
    s = Bits('u_le32=999')
    assert s.u_le == 999
    s = s.byteswap()
    assert s.u == 999
    s = Bits.pack('u_le24', 1001)
    assert s.u_le == 1001
    assert len(s) == 24
    assert s.unpack('u_le') == 1001

def test_little_endian_errors():
    with pytest.raises(ValueError):
        _ = Bits('uint_le15=10')
    with pytest.raises(ValueError):
        _ = Bits('i_le31=-999')
    s = Bits('0xfff')
    with pytest.raises(ValueError):
        _ = s.i_le
    with pytest.raises(ValueError):
        _ = s.u_be
    with pytest.raises(ValueError):
        _ = s.unpack('uint_le')
    with pytest.raises(ValueError):
        _ = s.unpack('i_ne')

def test_big_endian_errors():
    a = Bits('u_be16 = 10')
    with pytest.raises(ValueError):
        _ = Bits('u_be15 = 10')
    b = Bits('0xabc')
    with pytest.raises(ValueError):
        _ = b.f_be


def test_native_endian_floats():
    if bitformat.byteorder == 'little':
        a = Bits.pack('f_ne64', 0.55)
        assert a.unpack('f_ne64') == 0.55
        assert a.f_le == 0.55
        assert a.f_ne == 0.55
        d = Dtype('f_ne64')
        d2 = Dtype.from_parameters('f', 64, endianness='ne')
        assert d == d2
        assert d.endianness == 'ne'
        d3 = Dtype.from_parameters('f', 64, endianness='le')
        assert d != d3


def test_unpack_field():
    f = Field('tadpole: u12')
    a = Bits('u12=100')
    assert f.unpack(a) == 100
    assert a.unpack(f) == 100

    a = Bits('0x000001b3, u12=352, u12=288, bool=1')
    v = a.unpack(['hex32', '[u12; 2]' , 'bool'])
    assert v == ['000001b3', (352, 288), True]