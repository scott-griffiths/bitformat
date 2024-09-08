#!/usr/bin/env python
import pytest
import sys
import array
import os
from bitformat import Array, Bits
import copy
import itertools
import io
from bitformat._dtypes import Dtype
import re
import collections

sys.path.insert(0, '..')


THIS_DIR = os.path.dirname(os.path.abspath(__file__))

def remove_unprintable(s: str) -> str:
    colour_escape = re.compile(r'(?:\x1B[@-_])[0-?]*[ -/]*[@-~]')
    return colour_escape.sub('', s)

class TestCreation:

    def test_creation_from_int(self):
        a = Array('u12', 20)
        assert len(a) == 20
        assert a[19] == 0
        with pytest.raises(IndexError):
            _ = a[20]

    def test_creation_from_int_list(self):
        a = Array('i4', [-3, -2, -1, 0, 7])
        assert len(a) == 5
        assert a[2] == -1
        assert a[-1] == 7

    def test_creation_from_bytes_explicit(self):
        a = Array('hex8', Bits.from_bytes(b'ABCD'))
        assert a[0] == '41'
        assert a[1] == '42'
        assert a[2] == '43'
        assert a[3] == '44'

    def test_creation_from_bits_format(self):
        a = Bits.from_string('0x000102030405')
        b = Array('bits8', a)
        c = Array('bits8', [Bits.from_string('0x00'), '0x01', '0x02', '0x03', '0x04', '0x05'])
        assert b.equals(c)

    # def test_creation_from_float8(self):
    #     a = Array('p4binary')
    #     a.data.bytes = b'\x7f\x00'
    #     assert a[0] == float('inf')
    #     assert a[1] == 0.0
    #     b = Array('p4binary', [100000, -0.0])
    #     assert a.equals(b)

    def test_creation_from_multiple(self):
        with pytest.raises(ValueError):
            _ = Array('2*float16')

    def test_changing_fmt(self):
        d = Dtype.from_parameters('u', 8)
        a = Array(d, [255]*100)
        assert len(a) == 100
        a.dtype = Dtype('i4')
        assert len(a) == 200
        assert a.count(-1) == 200
        a.append(5)
        assert len(a) == 201
        assert a.count(-1) == 200

        a = Array('f64', [0, 0, 1])
        with pytest.raises(ValueError):
            a.dtype = 'se'
        assert a[-1] == 1.0
        assert a.dtype == Dtype.from_string('f64')

    def test_changing_format_with_trailing_bits(self):
        a = Array('bool', 803)
        assert len(a) == 803
        a.dtype = 'f16'
        assert len(a) == 803 // 16
        b = Array('f32', [0])
        b.dtype = 'i3'
        assert b.unpack() == [0]*10

    def test_creation_with_trailing_bits(self):
        a = Array('bool', trailing_bits='0xf')
        assert a.data == '0b1111'
        assert len(a) == 4

        b = Array('bin3', ['111', '000', '111'])
        assert len(b) == 3
        assert b.data == '0b111000111'
        b.dtype = 'hex4'
        assert len(b) == 2
        with pytest.raises(ValueError):
            b.append('f')
        b = Array(b.dtype, b.data[1:])
        b.append('f')
        assert len(b) == 3

        c = Array('f16', trailing_bits='0x0000, 0b1')
        assert c[0] == 0.0
        assert c.unpack() == [0.0]

    def test_creation_from_bytes(self):
        a = Array('u8', b'ABC')
        assert len(a) == 3
        assert a[0] == 65
        assert not a.trailing_bits

    def test_creation_from_bytearray(self):
        a = Array('u7', bytearray(range(70)))
        assert len(a) == 80
        assert not a.trailing_bits

    def test_creation_from_memoryview(self):
        x = b'1234567890'
        m = memoryview(x[2:5])
        assert m == b'345'
        a = Array('u8', m)
        assert a.unpack() == [ord('3'), ord('4'), ord('5')]

    def test_creation_from_bits(self):
        a = Bits.join([Bits.pack('i19', x) for x in range(-10, 10)])
        b = Array('i19', a)
        assert b.unpack() == list(range(-10, 10))

    def test_format_changes(self):
        a = Array('u8', [5, 4, 3])
        with pytest.raises(ValueError):
            a.dtype = 'ue3'
        b = a[:]
        b.dtype = 'i8'
        assert a.unpack() == b.unpack()
        assert not a.equals(b)
        with pytest.raises(ValueError):
            b.dtype = 'hello_everyone'
        with pytest.raises(ValueError):
            b.dtype = 'f'
        with pytest.raises(ValueError):
            b.dtype = 'u_le12'
            _ = b[0]
        with pytest.raises(ValueError):
            b.dtype = 'float17'


class TestArrayMethods:

    def test_count(self):
        a = Array('u9', [0, 4, 3, 2, 3, 4, 2, 3, 2, 1, 2, 11, 2, 1])
        assert a.count(0) == 1
        assert a.count(-1) == 0
        assert a.count(2) == 5

    # def test_count_nan(self):
    #     a = Array('uint8', [0, 10, 128, 128, 4, 2, 1])
    #     a.dtype = 'p3binary'
    #     assert a.count(float('nan')) == 2

    def test_from_bytes(self):
        a = Array('i16')
        assert len(a) == 0
        a = Array(a.dtype, a.to_bits() + bytearray([0, 0, 0, 55]))
        assert len(a) == 2
        assert a[0] == 0
        assert a[1] == 55
        a.extend(b'\x01\x00')
        assert len(a) == 3
        assert a[-1] == 256
        a.extend(bytearray())
        assert len(a) == 3

    def test_equals(self):
        a = Array('i40')
        b = Array('i40')
        assert a.equals(b)
        c = Array('bin40')
        assert not a.equals(c)
        v = ['1234567890']
        a.extend(v)
        b.extend(v)
        assert a.equals(b)
        b.extend(v)
        assert not a.equals(b)

        a = Array('u20', [16, 32, 64, 128])
        b = Array('u10', [0, 16, 0, 32, 0, 64, 0, 128])
        assert not b.equals(a)
        b.dtype = 'u20'
        assert a.equals(b)
        a = Array(a.dtype, a.data + '0b1')
        assert not a.equals(b)
        b = Array(b.dtype, b.data + '0b1')
        assert a.equals(b)

        c = Array('u8', [1, 2])
        assert not c.equals('hello')
        assert not c.equals(array.array('B', [1, 3]))

    def test_equals_with_trailing_bits(self):
        a = Array('hex4', ['a', 'b', 'c', 'd', 'e', 'f'])
        c = Array('hex4', Bits.from_string('0xabcdef, 0b11'))
        assert a.unpack() == c.unpack()
        assert a != c
        a = Array(a.dtype, a.data + '0b11')
        assert a.unpack() == c.unpack()
        assert a.equals(c)

    def test_setting(self):
        a = Array('bool', b'\x00')
        a[0] = 1
        assert a[0] is True

        b = Array('hex12')
        with pytest.raises(ValueError):
            b.append('12')
        b.append('123')
        with pytest.raises(ValueError):
            b.extend(['3456'])
        b.extend(['345'])
        assert b.unpack() == ['123', '345']
        with pytest.raises(ValueError):
            b[0] = 'abcd'
        with pytest.raises(TypeError):
            b[0] = 12
        with pytest.raises(TypeError):
            b[0] = Bits.from_string('0xfff')
        b[0] = 'fff'
        assert b.data.hex == 'fff345'

    def test_setting_from_iterable(self):
        a = Array('u99', range(100))
        x = itertools.chain([1, 2, 3], [4, 5])
        a[10:15] = x
        assert a[10:15].unpack() == list(range(1, 6))
        x = itertools.chain([1, 2, 3], [4, 5])
        a[50:60:2] = x
        assert a[50:60:2].unpack() == list(range(1, 6))


    def test_extend(self):
        a = Array('u3', (1, 2, 3))
        a.extend([4, 5, 6])
        assert a.unpack() == [1, 2, 3, 4, 5, 6]
        a.extend([])
        assert a.unpack() == [1, 2, 3, 4, 5, 6]
        a.extend(a)
        assert a.unpack() == [1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6]
        b = Array('i3', [0])
        with pytest.raises(TypeError):
            a.extend(b)
        a = Array(a.dtype, a.data[1:])
        with pytest.raises(ValueError):
            a.extend([1, 0])
        a = Array(a.dtype)
        with pytest.raises(TypeError):
            a.extend('u3=3')  # Can't extend with a str even though it's iterable

    def test_extend_with_mixed_classes(self):
        a = Array('u8', [1, 2, 3])
        b = array.array('B', [4, 5, 6])
        ap = Array('u8', a[:])
        bp = array.array('B', b[:])
        a.extend(b)
        bp.extend(ap)
        assert a.unpack() == [1, 2, 3, 4, 5, 6]
        assert bp.tolist() == [4, 5, 6, 1, 2, 3]

        a.dtype = 'i8'
        ap = Array('u8', a.unpack())
        assert not a.equals(ap)
        assert a.unpack() == ap.unpack()

    def test_insert(self):
        a = Array('hex12', ['abc', 'def'])
        assert a.data.hex == 'abcdef'
        a.insert(0, '000')
        assert a.data.hex == '000abcdef'
        a.insert(-1, '111')
        assert a[-1] == 'def'
        assert a[-2] == '111'
        a = Array(a.dtype, a.data + '0b1')
        assert a[-1] == 'def'
        a.insert(1, '111')
        assert a.unpack() == ['000', '111', 'abc', '111', 'def']

        with pytest.raises(ValueError):
            a.insert(2, 'hello')
        with pytest.raises(ValueError):
            a.insert(2, 'ab')

    def test_pop(self):
        a = Array('oct6', ['33', '21', '11', '76'])
        with pytest.raises(IndexError):
            _ = a.pop(4)
        assert len(a) == 4
        x = a.pop()
        assert len(a) == 3
        assert x == '76'
        with pytest.raises(IndexError):
            _ = a.pop(3)
        x = a.pop(2)
        assert x == '11'
        x = a.pop(0)
        assert x == '33'
        x = a.pop()
        assert x == '21'
        with pytest.raises(IndexError):
            _ = a.pop()

    def test_reverse(self):
        a = Array('i30', [])
        a.reverse()
        assert a.unpack() == []
        a.append(2)
        a.reverse()
        assert a.unpack() == [2]
        a.append(3)
        a.reverse()
        assert a.unpack() == [3, 2]
        a = Array(a.dtype)
        a.extend(list(range(1000)))
        a.reverse()
        assert a.unpack() == list(range(999, -1, -1))
        x = a.pop(0)
        assert x == 999
        a.reverse()
        assert a.unpack() == list(range(0, 999))
        a = Array(a.dtype, a.data + '0b1')
        with pytest.raises(ValueError):
            a.reverse()

    def test_byteswap(self):
        a = Array('u16')
        a.byteswap()
        assert a.unpack() == []
        b = Array('u17')
        with pytest.raises(ValueError):
            b.byteswap()
        a.extend([1, 0, 256])
        a.byteswap()
        assert a.unpack() == [256, 0, 1]
        a.byteswap()
        assert a.unpack() == [1, 0, 256]

    def test_getting(self):
        a = Array('i17')
        with pytest.raises(IndexError):
            _ = a[0]
        a.extend([1, 2, 3, 4])
        assert a[:].equals(Array('i17', [1, 2, 3, 4]))
        assert a[:1].equals(Array('i17', [1]))
        assert a[1:3].equals(Array('i17', [2, 3]))
        assert a[-2:].equals(Array('i17', [3, 4]))
        assert a[::2].equals(Array('i17', [1, 3]))
        assert a[::-2].equals(Array('i17', [4, 2]))

    def test_more_setting(self):
        a = Array('i1', [0, -1, -1, 0, 0, -1, 0])
        a[0] = -1
        assert a[0] == -1
        a[0:3] = [0, 0]
        assert a.unpack() == [0, 0, 0, 0, -1, 0]
        b = Array('i20', a.unpack())
        with pytest.raises(TypeError):
            b[::2] = 9
        b[::2] = [9]*3
        assert b.unpack() == [9, 0, 9, 0, 9, 0]
        b[1:4] = a[-2:]
        assert b.unpack() == [9, -1, 0, 9, 0]

    def test_deleting(self):
        a = Array('u99', list(range(1000)))
        del a[::2]
        assert len(a) == 500
        del a[-100:]
        assert len(a) == 400
        assert a[:10].unpack() == [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
        with pytest.raises(IndexError):
            del a[len(a)]
        with pytest.raises(IndexError):
            del a[-len(a) - 1]

    def test_deleting_more_ranges(self):
        a = Array('u18', [1, 2, 3, 4, 5, 6])
        del a[3:1:-1]
        assert a.unpack() == [1, 2, 5, 6]


    def test_repr(self):
        a = Array('i5')
        b = eval(a.__repr__())
        assert a.equals(b)
        a = Array(a.dtype, Bits.from_string('0b11'))

        b = eval(a.__repr__())
        assert a.equals(b)

        a = Array(a.dtype, a.data + '0b000')
        b = eval(a.__repr__())
        assert a.equals(b)

        a.extend([1]*9)
        b = eval(a.__repr__())
        assert a.equals(b)

        a.extend([-4]*100)
        b = eval(a.__repr__())
        assert a.equals(b)

        a.dtype = 'f32'
        b = eval(a.__repr__())
        assert a.equals(b)

    def test__add__(self):
        a = Array('u8', [1, 2, 3])
        b = Array('u8', [3, 4])
        c = a[:]
        c.extend(b)
        assert a.equals(Array('u8', [1, 2, 3]))
        assert c.equals(Array('u8', [1, 2, 3, 3, 4]))
        d = a[:]
        d.extend([10, 11, 12])
        assert d.equals(Array('u8', [1, 2, 3, 10, 11, 12]))

    def test__contains__(self):
        a = Array('i9', [-1, 88, 3])
        assert 88 in a
        assert not 89 in a

    def test__copy__(self):
        a = Array('i4', Bits.from_string('0x123451234561'))
        b = copy.copy(a)
        assert a.equals(b)
        a = Array(a.dtype, a.data + '0b1010')
        assert not a.equals(b)

    def test__iadd__(self):
        a = Array('u999')
        a.extend([4])
        assert a.unpack() == [4]
        a += 5
        a.extend(a)
        assert a.unpack() == [9, 9]

    # def test_float8_bug(self):
    #     a = Array('p3binary', [0.0, 1.5])
    #     b = Array('p4binary')
    #     b[:] = a[:]
    #     assert b[:].equals(Array('p4binary', [0.0, 1.5]))

#     def test_pp(self):
#         a = Array('bfloat', [-3, 1, 2])
#         s = io.StringIO()
#         a.pp('hex', stream=s)
#         assert remove_unprintable(s.getvalue()) ==  "<Array fmt='hex', length=3, item_size=16 bits, total data size=6 bytes> [\n" \
#                                         " 0: c040 3f80 4000\n" \
#                                         "]\n"
#         a.data += '0b110'
#         a.dtype='hex16'
#         s = io.StringIO()
#         a.pp(stream=s)
#         assert remove_unprintable(s.getvalue()) ==  """<Array dtype='hex16', length=3, item_size=16 bits, total data size=7 bytes> [
#  0: c040 3f80 4000
# ] + trailing_bits = 0b110\n"""

    def test_pp_uint(self):
        a = Array('u32', [12, 100, 99])
        s = io.StringIO()
        a.pp(stream=s)
        assert remove_unprintable(s.getvalue()) == """<Array dtype='u32', length=3, item_size=32 bits, total data size=12 bytes> [
 0:         12        100         99
]\n"""

    def test_pp_bits(self):
        a = Array('bits2', b'89')
        s = io.StringIO()
        a.pp(stream=s, width=0, show_offset=True)
        assert remove_unprintable(s.getvalue()) == """<Array dtype='bits2', length=8, item_size=2 bits, total data size=2 bytes> [
 0: 0b00
 1: 0b11
 2: 0b10
 3: 0b00
 4: 0b00
 5: 0b11
 6: 0b10
 7: 0b01
]\n"""

#     def test_pp_two_formats(self):
#         a = Array('float16', bytearray(20))
#         s = io.StringIO()
#         a.pp(stream=s, fmt='p3binary, bin', show_offset=False)
#         assert remove_unprintable(s.getvalue()) == """<Array fmt='p3binary, bin', length=20, item_size=8 bits, total data size=20 bytes> [
#                 0.0                 0.0                 0.0                 0.0 : 00000000 00000000 00000000 00000000
#                 0.0                 0.0                 0.0                 0.0 : 00000000 00000000 00000000 00000000
#                 0.0                 0.0                 0.0                 0.0 : 00000000 00000000 00000000 00000000
#                 0.0                 0.0                 0.0                 0.0 : 00000000 00000000 00000000 00000000
#                 0.0                 0.0                 0.0                 0.0 : 00000000 00000000 00000000 00000000
# ]\n"""

    def test_pp_two_formats_no_length(self):
        a = Array('f16', bytearray(range(50, 56)))
        s = io.StringIO()
        a.pp(stream=s, fmt='u, bin')
        assert remove_unprintable(s.getvalue()) == """<Array fmt='u, bin', length=3, item_size=16 bits, total data size=6 bytes> [
 0: 12851 13365 13879 : 0011001000110011 0011010000110101 0011011000110111
]\n"""


class TestArrayOperations:

    def test_in_place_add(self):
        a = Array('i7', [-9, 4, 0])
        a += 9
        assert a.unpack() == [0, 13, 9]
        assert len(a.data) == 21

    def test_add(self):
        a = Array('f64')
        a.extend([1.0, -2.0, 100.5])
        b = a + 2
        assert a.equals(Array('f64', [1.0, -2.0, 100.5]))
        assert b.equals(Array('f64', [3.0, 0.0, 102.5]))

    def test_sub(self):
        a = Array('u44', [3, 7, 10])
        b = a - 3
        assert b.equals(Array('u44', [0, 4, 7]))
        with pytest.raises(ValueError):
            _ = a - 4

    def test_in_place_sub(self):
        a = Array('f16', [-9, -10.5])
        a -= -1.5
        assert a.unpack() == [-7.5, -9.0]

    def test_mul(self):
        a = Array('i21', [-5, -4, 0, 2, 100])
        b = a * 2
        assert b.unpack() == [-10, -8, 0, 4, 200]
        a = Array('i9', [-1, 0, 3])
        b = a * 2
        assert a.unpack() == [-1, 0, 3]
        assert b.unpack() == [-2, 0, 6]
        c = a * 2.5
        assert c.unpack() == [-2, 0, 7]

    def test_in_place_mul(self):
        a = Array('i21', [-5, -4, 0, 2, 100])
        a *= 0.5
        assert a.unpack() == [-2, -2, 0, 1, 50]

    def test_div(self):
        a = Array('i32', [-2, -1, 0, 1, 2])
        b = a // 2
        assert a.unpack() == [-2, -1, 0, 1, 2]
        assert b.unpack() == [-1, -1, 0, 0, 1]

    def test_in_place_div(self):
        a = Array('i10', [-4, -3, -2, -1, 0, 1, 2])
        a //= 2
        assert a.equals(Array('i10', [-2, -2, -1, -1, 0, 0, 1]))

    def test_true_div(self):
        a = Array('f16', [5, 10, -6])
        b = a / 4
        assert a.equals(Array('f16', [5.0, 10.0, -6.0]))
        assert b.equals(Array('f16', [1.25, 2.5, -1.5]))

    def test_in_place_true_div(self):
        a = Array('i71', [-4, -3, -2, -1, 0, 1, 2])
        a /= 2
        assert a.equals(Array('i71', [-2, -1, -1, 0, 0, 0, 1]))

    def test_and(self):
        a = Array('i16', [-1, 100, 9])
        with pytest.raises(TypeError):
            _ = a & 0
        b = a & '0x0001'
        assert b.unpack() == [1, 0, 1]
        b = a & '0xffff'
        assert b.dtype == Dtype.from_string('i16')
        assert b.unpack() == [-1, 100, 9]

    def test_in_place_and(self):
        a = Array('bool', [True, False, True])
        with pytest.raises(TypeError):
            a &= 0b1
        a = Array('u10', a.unpack())
        a <<= 3
        assert a.unpack() == [8, 0, 8]
        a += 1
        assert a.unpack() == [9, 1, 9]
        with pytest.raises(ValueError):
            a &= '0b111'
        a &= '0b0000000111'
        assert a.data == '0b 0000000001 0000000001 0000000001'

    # def test_or(self):
    #     a = Array('p4binary', [-4, 2.5, -9, 0.25])
    #     b = a | '0b10000000'
    #     assert a.unpack() == [-4,  2.5, -9,  0.25]
    #     assert b.unpack() == [-4, -2.5, -9, -0.25]

    def test_in_place_or(self):
        a = Array('hex12')
        a.append('f0f')
        a.extend(['000', '111'])
        a |= '0x00f'
        assert a.unpack() == ['f0f', '00f', '11f']
        with pytest.raises(TypeError):
            a |= 12

    def test_xor(self):
        a = Array('hex8', ['00', 'ff', 'aa'])
        b = a ^ '0xff'
        assert a.unpack() == ['00', 'ff', 'aa']
        assert b.unpack() == ['ff', '00', '55']

    def test_in_place_xor(self):
        a = Array('u10', [0, 0xf, 0x1f])
        a ^= '0b00, 0x0f'

    def test_rshift(self):
        a = Array('u8', Bits.from_string('0x00010206'))
        b = a >> 1
        assert a.unpack() == [0, 1, 2, 6]
        assert b.unpack() == [0, 0, 1, 3]

        a = Array('i10', [-1, 0, -20, 10])
        b = a >> 1
        assert b.unpack() == [-1, 0, -10, 5]
        c = a >> 0
        assert c.unpack() == [-1, 0, -20, 10]
        with pytest.raises(ValueError):
            _ = a >> -1

    def test_in_place_rshift(self):
        a = Array('i8', [-8, -1, 0, 1, 100])
        a >>= 1
        assert a.unpack() == [-4, -1, 0, 0, 50]
        a >>= 100000
        assert a.unpack() == [-1, -1, 0, 0, 0]

    def test_lshift(self):
        a = Array('f16', [0.3, 1.2])
        with pytest.raises(TypeError):
            _ = a << 3
        a = Array('i16', [-2, -1, 0, 128])
        b = a << 4
        assert a.unpack() == [-2, -1, 0, 128]
        assert b.unpack() == [-32, -16, 0, 2048]
        with pytest.raises(ValueError):
            _ = a << 1000

    def test_in_place_lshift(self):
        a = Array('u11', [0, 5, 10, 1, 2, 3])
        a <<= 2
        assert a.unpack() == [0, 20, 40, 4, 8, 12]
        a <<= 0
        assert a.unpack() == [0, 20, 40, 4, 8, 12]
        with pytest.raises(ValueError):
            a <<= -1

    def test_neg(self):
        a = Array('i92', [-1, 1, 0, 100, -100])
        b = -a
        assert b.unpack() == [1, -1, 0, -100, 100]
        assert str(b.dtype) == 'i92'

    def test_abs(self):
        a = Array('f16', [-2.0, 0, -0, 100, -5.5])
        b = abs(a)
        assert b.equals(Array('f16', [2.0, 0, 0, 100, 5.5]))


class TestCreationFromBits:

    def test_appending_auto(self):
        a = Array('bits8')
        a.append('0xff')
        assert len(a) == 1
        assert a[0] == Bits.from_string('0xff')
        with pytest.raises(TypeError):
            a += 8
        a.append(Bits.zeros(8))
        assert a[:].equals(Array('bits8', ['0b1111 1111', Bits.zeros(8)]))
        a.extend(['0b10101011'])
        assert a[-1].hex == 'ab'


class TestSameSizeArrayOperations:

    def test_adding_same_types(self):
        a = Array('u8', [1, 2, 3, 4])
        b = Array('u8', [5, 5, 5, 4])
        c = a + b
        assert c.unpack() == [6, 7, 8, 8]
        assert c.dtype == Dtype.from_string('u8')

    def test_adding_different_types(self):
        a = Array('u8', [1, 2, 3, 4])
        b = Array('i6', [5, 5, 5, 4])
        c = a + b
        assert c.unpack() == [6, 7, 8, 8]
        assert c.dtype == Dtype.from_string('i6')
        d = Array('f16', [-10, 0, 5, 2])
        e = d + a
        assert e.unpack() == [-9.0, 2.0, 8.0, 6.0]
        assert e.dtype == Dtype.from_string('f16')
        e = a + d
        assert e.unpack() == [-9.0, 2.0, 8.0, 6.0]
        assert e.dtype == Dtype.from_string('f16')
        x1 = a[:]
        x2 = a[:]
        # x1.dtype = 'p3binary'
        # x2.dtype = 'p4binary'
        # y = x1 + x2
        # assert y.dtype == x1.dtype

    def test_adding_errors(self):
        a = Array('f16', [10, 100, 1000])
        b = Array('i3', [-1, 2])
        with pytest.raises(ValueError):
            _ = a + b
        b.append(0)
        c = a + b
        assert c.unpack() == [9, 102, 1000]
        a.dtype = 'hex16'
        with pytest.raises(ValueError):
            _ = a + b


class TestComparisonOperators:

    def test_less_than_with_scalar(self):
        a = Array('u16', [14, 16, 100, 2, 100])
        b = a < 80
        assert b.unpack() == [True, True, False, True, False]
        assert b.dtype == Dtype('bool')

    def test_less_than_with_array(self):
        a = Array('u16', [14, 16, 100, 2, 100])
        b = Array('f16', [1000, -54, 0.2, 55, 9])
        c = a < b
        assert c.unpack() == [True, False, False, True, False]
        assert c.dtype == Dtype('bool')

    def test_array_equals(self):
        a = Array('i12', [1, 2, -3, 4, -5, 6])
        b = Array('i12', [6, 5, 4, 3, 2, 1])
        assert abs(a).equals(b[::-1])
        assert (a == b) == [False, False, False, False, False, False]
        assert (a != b) == [True, True, True, True, True, True]
        with pytest.raises(ValueError):
            _ = a == b[:-1]
        with pytest.raises(ValueError):
            _ = a == [1, 2, 3]
        with pytest.raises(ValueError):
            _ = [1, 2, 3] == a
        with pytest.raises(ValueError):
            _ = a == [1, 2, 3, 4, 5, 6, 7]

class TestAsType:

    def test_switching_int_types(self):
        a = Array('u8', [15, 42, 1])
        b = a.astype('i8')
        assert a.unpack() == b.unpack()
        assert b.dtype == Dtype.from_string('i8')

    def test_switching_float_types(self):
        a = Array('f64', [-990, 34, 1, 0.25])
        b = a.astype('f16')
        assert a.unpack() == b.unpack()
        assert b.dtype == Dtype.from_string('f16')


class TestReverseMethods:

    def test_radd(self):
        a = Array('u6', [1,2,3])
        b = 5 + a
        assert b.equals(Array('u6', [6, 7, 8]))

    # def test_rmul(self):
    #     a = Array('bfloat', [4, 2, 8])
    #     b = 0.5 * a
    #     assert b.equals(Array('bfloat16', [2.0, 1.0, 4.0]))

    def test_rsub(self):
        a = Array('i90', [-1, -10, -100])
        b = 100 - a
        assert b.equals(Array('i90', [101, 110, 200]))

    def test_rmod(self):
        a = Array('i8', [1, 2, 4, 8, 10])
        with pytest.raises(TypeError):
            _ = 15 % a

    def test_rfloordiv(self):
        a = Array('i16', [1, 2, 3, 4, 5])
        with pytest.raises(TypeError):
            _ = 100 // a

    def test_rtruediv(self):
        a = Array('i16', [1, 2, 3, 4, 5])
        with pytest.raises(TypeError):
            _ = 100 / a

    def test_rand(self):
        a = Array('u8', [255, 8, 4, 2, 1, 0])
        b = '0x0f' & a
        assert b.unpack() == [15, 8, 4, 2, 1, 0]

    def test_ror(self):
        a = Array('u8', [255, 8, 4, 2, 1, 0])
        b = '0x0f' | a
        assert b.unpack() == [255, 15, 15, 15, 15, 15]

    def test_rxor(self):
        a = Array('u8', [255, 8, 4, 2, 1, 0])
        b = '0x01' ^ a
        assert b.unpack() == [254, 9, 5, 3, 0, 1]


class TestMisc:

    def test_invalid_type_assignment(self):
        a = Array('u8', [1,2,3])
        with pytest.raises(ValueError):
            a.dtype = 'penguin'

    def test_set_extended_slice(self):
        a = Array('bool', [0,1,1,1,0])
        with pytest.raises(ValueError):
            a[0:5:2] = [1, 0]

    def test_set_out_of_range_element(self):
        a = Array(Dtype.from_parameters('f', 16), [1, 2, 3, 4.5])
        a[3] = 100.0
        a[-4] = 100.0
        with pytest.raises(IndexError):
            a[4] = 100.0
        with pytest.raises(IndexError):
            a[-5] = 100.0

    def test_bytes(self):
        a = Array('bytes8', 5)
        assert a.data == b'\x00'*40

        b = Array('bytes1', 5)
        assert b.data == b'\x00'*5

    def test_bytes_trailing_bits(self):
        b = Bits.from_string('0x000000, 0b111')
        a = Array('bytes1', b)
        assert a.trailing_bits == '0b111'

    def test_operation_with_bool(self):
        x = Array('i4', [1, 2, 3, 4])
        y = Array('f16', [100, 2.0, 0.0, 4])
        x = x + (y == 0.0)
        assert x.unpack() == [1, 2, 4, 4]


def test_mutability():
    a = Array('u8', [1, 2])
    b = a.to_bits()
    assert b.to_bytes() == b'\x01\x02'
    assert isinstance(b, Bits)
    a[0] += 5
    assert b.to_bytes() == b'\x01\x02'


class TestDelegation:

    def test_delegation_methods(self):
        x = Array('u8', [1, 2, 3])
        y = x.data.starts_with('0x01')
        assert y is True
        x.insert(0, 15)
        y = x.data.starts_with('0x01')
        assert y is False
        assert len(x.data) == 32

    def test_getitem(self):
        a = Array('i4', [1, 2, 5, -1])
        assert a.data[-4:] == '0xf'

    def test_setitem(self):
        a = Array('i4', [1, 2, 5, 5])
        with pytest.raises(TypeError):
            a.data[-4:] = '0xf'

    def test_mutability(self):
        a = Array('i4', [1, 2, 5, 5])
        b = a.data
        a[0] = 3
        assert b[0:4] == '0b0011'

    def test_str(self):
        a = Array('f32', [0, -10, 0.5])
        b = a.to_bits()
        assert str(a.data) == str(b)
        assert repr(a.data) == repr(b)

    def test_copy(self):
        a = Array('u8', [1, 2, 3])
        c = copy.copy(a)
        d = copy.copy(a.data)
        assert a.data == c.data
        assert a.data == d
        a[0] = 5
        assert a.data != c.data
        assert a.data != d

    def test_setting_data(self):
        a = Array('u8')
        a.append(4)
        assert a[0] == 4
        a.data = a.data + '0xff'
        assert a[0] == 4
        assert a[1] == 255

    def test_hash(self):
        a = Array('u8', [1])
        assert isinstance(a.data, collections.abc.Hashable) is False
        with pytest.raises(TypeError):
            _ = set([a.data])


def test_array_of_array():
    a = Array('[u8;3]', [[1, 2, 3], [4, 5, 6]])
    assert len(a) == 2
    assert a[0] == (1, 2, 3)
    assert a[1] == (4, 5, 6)
    with pytest.raises(ValueError):
        a[0] = (10, 5)
    with pytest.raises(ValueError):
        a[1] = [1, 2, 3, 4]
    a[0] = [9, 9, 0]
    assert a[0] == (9, 9, 0)

def test_rgb_array():
    a = Array('[u10; 3]', bytearray(30))
    assert len(a) == 8
    assert a[0] == (0, 0, 0)
    assert a[1] == (0, 0, 0)
    assert a.unpack() == [(0, 0, 0)]*8
    a[5] = (5, 4, 3)
    assert a[5] == (5, 4, 3)

    with pytest.raises(ValueError):
        a.pp()

def test_dtype_array_byteswap():
    a = Array('[u_le16; 3]', [(1, 2, 3), (4, 5, 6)])
    assert a[1] == (4, 5, 6)
    a.byteswap()
    a.dtype = '[u_be16; 3]'
    assert a[1] == (4, 5, 6)

    