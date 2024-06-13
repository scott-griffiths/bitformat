#!/usr/bin/env python

import pytest
import bitformat
import copy
from bitformat import Bits


class TestFlexibleInitialisation:
    def test_flexible_initialisation(self):
        a = Bits('uint:8=12')
        c = Bits(' uint : 8 =  12')
        assert a == c == Bits.build('uint8', 12)
        assert a.uint == 12
        a = Bits('     int:2=  -1')
        b = Bits('int :2   = -1')
        c = Bits(' int:  2  =-1  ')
        assert a == b == c == Bits.build('i2', -1)

    def test_flexible_initialisation2(self):
        h = Bits('hex=12')
        o = Bits('oct=33')
        b = Bits('bin=10')
        assert h == '0x12'
        assert o == '0o33'
        assert b == '0b10'

    def test_multiple_string_initialisation(self):
        a = Bits('0b1 , 0x1')
        assert a == '0b10001'
        b = Bits('uint:32 = 12, 0b11') + 'int:100=-100, 0o44'
        assert b[0: 32].uint == 12
        assert b[32: 34].bin == '11'
        assert b[34: 134].int == -100


class TestFind:
    def test_find1(self):
        s = Bits('0b0000110110000')
        assert s.find(Bits('0b11011')) == 4

    def test_find_with_offset(self):
        s = Bits('0x112233')[4:]
        assert s.find('0x23') == 8

    def test_find_corner_cases(self):
        s = Bits('0b000111000111')
        assert s.find('0b000') == 0
        assert s.find('0b0111000111') == 2
        assert s.find('0b000', start=2) == 6

    def test_find_bytes(self):
        s = Bits.from_string('0x010203040102ff')
        assert s.find('0x05', bytealigned=True) is None
        assert s.find('0x02', bytealigned=True) == 8
        assert s.find('0x02', start=16, bytealigned=True) == 40
        assert s.find('0x02', start=1, bytealigned=True) == 8

    def test_find_bytes_aligned_corner_cases(self):
        s = Bits('0xff')
        assert s.find(s) is not None
        assert s.find(Bits('0x12')) is None
        assert s.find(Bits('0xffff')) is None

    def test_find_byte_aligned(self):
        s = Bits.build('hex', '0x12345678')
        assert s.find(Bits('0x56'), bytealigned=True) == 16
        assert not s.find(Bits('0x45'), start=16, bytealigned=True)
        s = Bits('0x1234')
        assert s.find('0x1234') == 0
        s += '0b111'
        s.find('0b1', start=17, bytealigned=True)
        assert s.find('0b1', start=17, bytealigned=True) is None

    def test_find_byte_aligned_with_offset(self):
        s = Bits('0x112233')[4:]
        assert s.find('0x23', bytealigned=True) == 8

    def test_find_byte_aligned_errors(self):
        s = Bits('0xffff')
        with pytest.raises(ValueError):
            s.find('')
        with pytest.raises(ValueError):
            s.find(Bits())


class TestRfind:
    def test_rfind(self):
        a = Bits('0b001001001')
        b = a.rfind('0b001')
        assert b == 6
        big = Bits.zeros(100000) + '0x12' + Bits.zeros(10000)
        found = big.rfind('0x12', bytealigned=True)
        assert found == 100000

    def test_rfind_byte_aligned(self):
        a = Bits('0x8888')
        b = a.rfind('0b1', bytealigned=True)
        assert b == 8

    def test_rfind_startbit(self):
        a = Bits('0x0000ffffff')
        b = a.rfind('0x0000', start=1, bytealigned=True)
        assert b is None
        b = a.rfind('0x00', start=1, bytealigned=True)
        assert b == 8

    def test_rfind_endbit(self):
        a = Bits('0x000fff')
        b = a.rfind('0b011', start=0, end=14, bytealigned=False)
        assert b is not None
        b = a.rfind('0b011', 0, 13, False)
        assert b is None

    def test_rfind_errors(self):
        a = Bits('0x43234234')
        with pytest.raises(ValueError):
            a.rfind('', bytealigned=True)
        with pytest.raises(ValueError):
            a.rfind('0b1', start=-99, bytealigned=True)
        with pytest.raises(ValueError):
            a.rfind('0b1', end=33, bytealigned=True)
        with pytest.raises(ValueError):
            a.rfind('0b1', start=10, end=9, bytealigned=True)


class TestShift:
    def test_shift_left(self):
        s = Bits.from_string('0b1010')
        t = s << 1
        assert s.bin == '1010'
        assert t.bin == '0100'
        s = t << 0
        assert s == '0b0100'
        t = s << 100
        assert t.bin == '0000'

    def test_shift_left_errors(self):
        s = Bits()
        with pytest.raises(ValueError):
            _ = s << 1
        s = Bits('0xf')
        with pytest.raises(ValueError):
            _ = s << -1

    def test_shift_right(self):
        s = Bits('0b1010')
        t = s >> 1
        assert s.bin == '1010'
        assert t.bin == '0101'
        q = s >> 0
        assert q == '0b1010'
        t = s >> 100
        assert t.bin == '0000'

    def test_shift_right_errors(self):
        s = Bits()
        with pytest.raises(ValueError):
            _ = s >> 1
        s = Bits('0xf')
        with pytest.raises(ValueError):
            _ = s >> -1


class TestReplace:
    def test_replace1(self):
        a = Bits('0b1')
        a = a.replace('0b1', '0b0', bytealigned=True)
        assert a.bin == '0'
        a = a.replace('0b1', '0b0', bytealigned=True)
        assert a.bin == '0'

    def test_replace2(self):
        a = Bits('0b00001111111')
        a = a.replace('0b1', '0b0', bytealigned=True)
        assert a.bin == '00001111011'
        a = a.replace('0b1', '0b0', bytealigned=False)
        assert a.bin == '00000000000'

    def test_replace3(self):
        a = Bits('0b0')
        a = a.replace('0b0', '0b110011111', bytealigned=True)
        assert a.bin == '110011111'
        a = a.replace('0b11', '', bytealigned=False)
        assert a.bin == '001'

    def test_replace4(self):
        a = Bits('0x00114723ef4732344700')
        a = a.replace('0x47', '0x00', bytealigned=True)
        assert a.hex == '00110023ef0032340000'
        a = a.replace('0x00', '', bytealigned=True)
        assert a.hex == '1123ef3234'
        a = a.replace('0x11', '', start=1, bytealigned=True)
        assert a.hex == '1123ef3234'
        a = a.replace('0x11', '0xfff', end=7, bytealigned=True)
        assert a.hex == '1123ef3234'
        a = a.replace('0x11', '0xfff', end=8, bytealigned=True)
        assert a.hex == 'fff23ef3234'

    def test_replace5(self):
        a = Bits.from_string('0xab')
        b = Bits.from_string('0xcd')
        c = Bits.from_string('0xabef')
        c = c.replace(a, b)
        assert c == '0xcdef'
        assert a == '0xab'
        assert b == '0xcd'
        a = Bits('0x0011223344').replace('0x11', '0xfff', bytealigned=True)
        assert a == '0x00fff223344'

    def test_replace_with_self(self):
        a = Bits('0b11')
        a = a.replace('0b1', a)
        assert a == '0xf'
        a = a.replace(a, a)
        assert a == '0xf'

    def test_replace_count(self):
        a = Bits('0x223344223344223344')
        a = a.replace('0x2', '0x0', count=0, bytealigned=True)
        assert a.hex == '223344223344223344'
        a = a.replace('0x2', '0x0', count=1, bytealigned=True)
        assert a.hex == '023344223344223344'
        a = a.replace('0x33', '', count=2, bytealigned=True)
        assert a.hex == '02442244223344'
        a = a.replace('0x44', '0x4444', count=1435, bytealigned=True)
        assert a.hex == '02444422444422334444'

    def test_replace_errors(self):
        a = Bits('0o123415')
        with pytest.raises(ValueError):
            a.replace('', Bits('0o7'), bytealigned=True)
        with pytest.raises(ValueError):
            a.replace('0b1', '0b1', start=-100, bytealigned=True)
        with pytest.raises(ValueError):
            a.replace('0b1', '0b1', end=19, bytealigned=True)

class TestSimpleConversions:
    def test_convert_to_uint(self):
        assert Bits('0x10').uint == 16
        assert Bits('0b000111').u == 7

    def test_convert_to_int(self):
        assert Bits('0x10').int == 16
        assert Bits('0b11110').i == -2

    def test_convert_to_hex(self):
        assert Bits.from_bytes(b'\x00\x12\x23\xff').hex == '001223ff'
        s = Bits('0b11111')
        with pytest.raises(bitformat.InterpretError):
            _ = s.hex

def test_empty_bitstring():
    s = Bits()
    assert s.bin == ''
    assert s.hex == ''
    with pytest.raises(bitformat.InterpretError):
        _ = s.int
    with pytest.raises(bitformat.InterpretError):
        _ = s.uint
    assert not s

class TestAppend:
    def test_append(self):
        s1 = Bits('0b00000')
        s1 = s1.append(Bits.build('bool', True))
        assert s1.bin == '000001'
        assert (Bits('0x0102') + Bits('0x0304')).hex == '01020304'

    def test_append_same_bitstring(self):
        s1 = Bits('0xf0')[:6]
        s1 = s1.append(s1)
        assert s1.bin == '111100111100'


def test_insert():
    s = Bits('0x0011')
    s = s.insert(Bits('0x22'), 8)
    assert s.hex == '002211'
    s = Bits.ones(0)
    s = s.insert('0b101', 0)
    assert s.bin == '101'


class TestSlice:
    def test_byte_aligned_slice(self):
        s = Bits('0x123456')
        assert s[8:16].hex == '34'
        s = s[8:24]
        assert len(s) == 16
        assert s.hex == '3456'
        s = s[0:8]
        assert s.hex == '34'

    def test_slice(self):
        s = Bits('0b000001111100000')
        s1 = s[0:5]
        s2 = s[5:10]
        s3 = s[10:15]
        assert s1.bin == '00000'
        assert s2.bin == '11111'
        assert s3.bin == '00000'

class TestInsert:
    def test_insert(self):
        s1 = Bits('0x123456')
        s2 = Bits('0xff')
        s1 = s1.insert(s2, 8)
        assert s1.hex == '12ff3456'
        s1 = s1.insert('0xee', 24)
        assert s1.hex == '12ff34ee56'
        with pytest.raises(ValueError):
            _ = s1.insert('0b1', -1000)
        with pytest.raises(ValueError):
            _ = s1.insert('0b1', 1000)

    def test_insert_null(self):
        s = Bits('0x123')
        s = s.insert(Bits(), 3)
        assert s.hex == '123'

    def test_insert_bits(self):
        one = Bits('0b1')
        zero = Bits('0b0')
        s = Bits('0b00').insert(one, 0)
        assert s.bin == '100'
        s = s.insert(zero, 0)
        assert s.bin == '0100'
        s = s.insert(one, len(s))
        assert s.bin == '01001'
        s = s.insert(s, 2)
        assert s.bin == '0101001001'


class TestOverwriting:
    def test_overwrite_bit(self):
        s = Bits('0b0')
        s = s.overwrite('0b1', 0)
        assert s.bin == '1'

    def test_overwrite_limits(self):
        s = Bits.build('bin', '0b11111')
        s = s.overwrite('0b000', 0)
        assert s.bin == '00011'
        s = s.overwrite('0b000', 2)
        assert s.bin == '00000'

    def test_overwrite_null(self):
        s = Bits('0x342563fedec')
        s2 = s.copy()
        s = s.overwrite(Bits(), 23)
        assert s.bin == s2.bin

    def test_overwrite_position(self):
        s1 = Bits('0x0123456')
        s2 = Bits('0xff')
        s1 = s1.overwrite(s2, 8)
        assert s1.hex == '01ff456'
        s1 = s1.overwrite('0xff', 0)
        assert s1.hex == 'ffff456'

    def test_overwrite_with_self(self):
        s = Bits('0x123')
        s = s.overwrite(s, 0)
        assert s == '0x123'


class TestAdding:
    def test_adding(self):
        s1 = Bits('0x0102')
        s2 = Bits('0x0304')
        s3 = s1 + s2
        assert s1.hex == '0102'
        assert s2.hex == '0304'
        assert s3.hex == '01020304'
        s3 += s1
        assert s3.hex == '010203040102'
        assert s2[9:16].bin == '0000100'
        assert s1[0:9].bin == '000000010'
        s4 = Bits.build('bin', '000000010') + Bits('0b0000100')
        assert s4.bin == '0000000100000100'
        s5 = s1[0:9] + s2[9:16]
        assert s5.bin == '0000000100000100'

    def test_more_adding(self):
        s = Bits('0b00') + Bits() + Bits('0b11')
        assert s.bin == '0011'
        s = '0b01'
        s += Bits('0b11')
        assert s.bin == '0111'
        s = Bits('0x00')
        t = Bits('0x11')
        s += t
        assert s.hex == '0011'
        assert t.hex == '11'
        s += s
        assert s.hex == '00110011'

    def test_radd(self):
        s = '0xff' + Bits('0xee')
        assert s.hex == 'ffee'

    def test_overwrite_errors(self):
        s = Bits('0b11111')
        with pytest.raises(ValueError):
            _ = s.overwrite(Bits('0b1'), -10)
        with pytest.raises(ValueError):
            _ = s.overwrite(Bits('0b1'), 6)
        s = s.overwrite('bin=0', 5)
        assert s.bin == '111110'
        s = s.overwrite(Bits('0x00'), 1)
        assert s.bin == '100000000'

    def test_get_item_with_positive_position(self):
        s = Bits('0b1011')
        assert s[0] == True
        assert s[1] == False
        assert s[2] == True
        assert s[3] == True
        with pytest.raises(IndexError):
            _ = s[4]

    def test_get_item_with_negative_position(self):
        s = Bits('0b1011')
        assert s[-1] == True
        assert s[-2] == True
        assert s[-3] == False
        assert s[-4] == True
        with pytest.raises(IndexError):
            _ = s[-5]

    def test_slicing(self):
        s = Bits('0x0123456789')
        assert s[0:8].hex == '01'
        assert not s[0:0]
        assert not s[23:20]
        assert s[8:12].bin == '0010'
        assert s[32:80] == '0x89'

    def test_negative_slicing(self):
        s = Bits('0x012345678')
        assert s[:-8].hex == '0123456'
        assert s[-16:-8].hex == '56'
        assert s[-24:].hex == '345678'
        assert s[-1000:-24] == '0x012'

    def test_len(self):
        s = Bits()
        assert len(s) == 0
        s = s.append('0b001')
        assert len(s) == 3

    def test_join(self):
        s1 = Bits('0b0')
        s2 = Bits('0b1')
        s3 = Bits('0b000')
        s4 = Bits('0b111')
        strings = [s1, s2, s1, s3, s4]
        s = Bits.join(strings)
        assert s.bin == '010000111'

    def test_join2(self):
        s1 = Bits('0x00112233445566778899aabbccddeeff')
        s2 = Bits('0b000011')
        bsl = [s1[0:32], s1[4:12], s2, s2, s2, s2]
        s = Bits.join(bsl)
        assert s.hex == '00112233010c30c3'

        bsl = [Bits.build('uint12', j) for j in range(10) for _ in range(10)]
        s = Bits.join(bsl)
        assert len(s) == 1200

    def test_join_with_ints(self):
        with pytest.raises(TypeError):
            _ = Bits.join([1, 2])
    def test_various_things2(self):
        s1 = Bits("0x1f08")[:13]
        assert s1.bin == '0001111100001'
        s2 = Bits('0b0101')
        assert s2.bin == '0101'
        s1 += s2
        assert len(s1) == 17
        assert s1.bin == '00011111000010101'
        s1 = s1[3:8]
        assert s1.bin == '11111'

    def test_various_things3(self):
        s1 = Bits('0x012480ff')[2:27]
        s2 = s1 + s1
        assert len(s2) == 50
        s3 = s2[0:25]
        s4 = s2[25:50]
        assert s3.bin == s4.bin

    def test_insert_using_auto(self):
        s = Bits('0xff')
        s = s.insert('0x00', 4)
        assert s.hex == 'f00f'

    def test_overwrite_using_auto(self):
        s = Bits('0x0110')
        s = s.overwrite('0b1', 0)
        assert s.hex == '8110'
        s = s.overwrite('', 0)
        assert s.hex == '8110'

    def test_find_using_auto(self):
        s = Bits('0b000000010100011000')
        assert s.find('0b101') == 7

    def test_findbytealigned_using_auto(self):
        s = Bits('0x00004700')
        assert s.find('0b01000111', bytealigned=True) == 16

    def test_append_using_auto(self):
        s = Bits('0b000')
        s = s.append('0b111')
        assert s.bin == '000111'
        s = s.append('0b0')
        assert s.bin == '0001110'
    def test_prepend(self):
        s = Bits('0b000')
        s = s.prepend('0b11')
        assert s.bin == '11000'
        s = s.prepend(s)
        assert s.bin == '1100011000'
        s = s.prepend('')
        assert s.bin == '1100011000'

    def test_null_slice(self):
        s = Bits('0x111')
        t = s[1:1]
        assert len(t) == 0

    def test_multiple_autos(self):
        s = Bits('0xa')
        s = s.prepend('0xf')
        s = s.append('0xb')
        assert s == '0xfab'
        s = s.prepend(s)
        s = s.append('0x100')
        s = s.overwrite('0x5', 4)
        assert s == '0xf5bfab100'

    def test_reverse(self):
        s = Bits('0b0011')
        s = s.reverse()
        assert s.bin == '1100'
        s = Bits('0b10')
        s = s.reverse()
        assert s.bin == '01'
        s = Bits()
        s = s.reverse()
        assert s.bin == ''

    def test_init_with_concatenated_strings(self):
        s = Bits('0xff 0Xee 0xd 0xcc')
        assert s.hex == 'ffeedcc'
        s = Bits('0b0 0B111 0b001')
        assert s.bin == '0111001'
        s += '0b1' + '0B1'
        assert s.bin == '011100111'
        s = Bits('0xff0xee')
        assert s.hex == 'ffee'
        s = Bits('0b000b0b11')
        assert s.bin == '0011'
        s = Bits('  0o123 0O 7 0   o1')
        assert s.oct == '12371'
        s += '  0 o 332'
        assert s.oct == '12371332'

    def test_equals(self):
        s1 = Bits('0b01010101')
        s2 = Bits('0b01010101')
        assert s1 == s2
        s3 = Bits()
        s4 = Bits()
        assert s3 == s4
        assert not s3 != s4

    def test_large_equals(self):
        s1 = Bits.zeros(1000000)
        s2 = Bits.zeros(1000000)
        s1 = s1.set(True, [-1, 55, 53214, 534211, 999999])
        s2 = s2.set(True, [-1, 55, 53214, 534211, 999999])
        assert s1 == s2
        s1 = s1.set(True, 800000)
        assert s1 != s2

    def test_not_equals(self):
        s1 = Bits('0b0')
        s2 = Bits('0b1')
        assert s1 != s2
        assert not s1 != Bits('0b0')

    def test_equality_with_auto_initialised(self):
        a = Bits('0b00110111')
        assert a == '0b00110111'
        assert a == '0x37'
        assert '0b0011 0111' == a
        assert '0x3 0x7' == a
        assert not a == '0b11001000'
        assert not '0x3737' == a

    def test_invert_special_method(self):
        s = Bits('0b00011001')
        assert (~s).bin == '11100110'
        assert (~Bits('0b0')).bin == '1'
        assert (~Bits('0b1')).bin == '0'
        assert ~~s == s
    def test_invert_special_method_errors(self):
        s = Bits()
        with pytest.raises(bitformat.Error):
            _ = ~s

    def test_join_with_auto(self):
        s = Bits.join(['0xf', '0b00', Bits.build('bin', '11')])
        assert s == '0b11110011'


class TestMultiplication:

    def test_multiplication(self):
        a = Bits('0xff')
        b = a * 8
        assert b == '0xffffffffffffffff'
        b = 4 * a
        assert b == '0xffffffff'
        assert 1 * a == a * 1 == a
        c = a * 0
        assert not c
        a *= 3
        assert a == '0xffffff'
        a *= 0
        assert not a
        one = Bits('0b1')
        zero = Bits('0b0')
        mix = one * 2 + 3 * zero + 2 * one * 2
        assert mix == '0b110001111'
        q = Bits()
        q *= 143
        assert not q
        q += [True, True, False]
        q *= 0
        assert not q

    def test_multiplication_errors(self):
        a = Bits('0b1')
        b = Bits('0b0')
        with pytest.raises(ValueError):
            _ = a * -1
        with pytest.raises(ValueError):
            a *= -1
        with pytest.raises(ValueError):
            _ = -1 * a
        with pytest.raises(TypeError):
            _ = a * 1.2
        with pytest.raises(TypeError):
            _ = b * a
        with pytest.raises(TypeError):
            a *= b


class TestBitWise:

    def test_bitwise_and(self):
        a = Bits('0b01101')
        b = Bits('0b00110')
        assert (a & b).bin == '00100'
        assert (a & '0b11111') == a
        with pytest.raises(ValueError):
            _ = a & '0b1'
        with pytest.raises(ValueError):
            _ = b & '0b110111111'
        c = Bits('0b0011011')
        d = c & '0b1111000'
        assert d.bin == '0011000'
        d = '0b1111000' & c
        assert d.bin == '0011000'

    def test_bitwise_or(self):
        a = Bits('0b111001001')
        b = Bits('0b011100011')
        c = a | b
        assert c.bin == '111101011'
        assert (a | '0b000000000') == a
        with pytest.raises(ValueError):
            _ = a | '0b0000'
        with pytest.raises(ValueError):
            _ = b | (a + '0b1')
        a = '0xff00' | Bits('0x00f0')
        assert a.hex == 'fff0'

    def test_bitwise_xor(self):
        a = Bits('0b111001001')
        b = Bits('0b011100011')
        c = a ^ b
        assert c.bin == '100101010'
        assert (a ^ '0b111100000').bin == '000101001'
        with pytest.raises(ValueError):
            _ = a ^ '0b0000'
        with pytest.raises(ValueError):
            _ = b ^ (a + '0b1')
        a = '0o707' ^ Bits('0o777')
        assert a.oct == '070'


class TestManyDifferentThings:

    def test_find_byte_aligned_with_bits(self):
        a = Bits('0x00112233445566778899')
        x = a.find('0b0001', bytealigned=True)
        assert x == 8

    def test_find_startbit_not_byte_aligned(self):
        a = Bits('0b0010000100')
        found = a.find('0b1', start=4)
        assert found == 7
        found = a.find('0b1', start=2)
        assert found == 2
        found = a.find('0b1', bytealigned=False, start=8)
        assert found is None

    def test_find_endbit_not_byte_aligned(self):
        a = Bits('0b0010010000')
        found = a.find('0b1', bytealigned=False, end=2)
        assert found is None
        found = a.find('0b1', end=3)
        assert found == 2
        found = a.find('0b1', bytealigned=False, start=3, end=5)
        assert found is None
        found = a.find('0b1', start=3, end=6)
        assert found == 5

    def test_find_startbit_byte_aligned(self):
        a = Bits('0xff001122ff0011ff')
        found = a.find('0x22', start=23, bytealigned=True)
        assert found == 24
        found = a.find('0x22', start=24, bytealigned=True)
        assert found == 24
        found = a.find('0x22', start=25, bytealigned=True)
        assert found is None
        found = a.find('0b111', start=40, bytealigned=True)
        assert found == 56

    def test_find_endbit_byte_aligned(self):
        a = Bits('0xff001122ff0011ff')
        found = a.find('0x22', end=31, bytealigned=True)
        assert found is None
        found = a.find('0x22', end=32, bytealigned=True)
        assert found == 24

    def test_find_start_endbit_errors(self):
        a = Bits('0b00100')
        with pytest.raises(ValueError):
            _ = a.find('0b1', bytealigned=False, start=-100)
        with pytest.raises(ValueError):
            _ = a.find('0b1', end=6)
        with pytest.raises(ValueError):
            _ = a.find('0b1', start=4, end=3)
        b = Bits('0x0011223344')
        with pytest.raises(ValueError):
            _ = b.find('0x22', bytealigned=True, start=-100)
        with pytest.raises(ValueError):
            _ = b.find('0x22', end=41, bytealigned=True)

    def test_find_all(self):
        a = Bits('0b11111')
        p = a.find_all('0b1')
        assert list(p) == [0, 1, 2, 3, 4]
        p = a.find_all('0b11')
        assert list(p) == [0, 1, 2, 3]
        p = a.find_all('0b10')
        assert list(p) == []
        a = Bits('0x4733eeff66554747335832434547')
        p = a.find_all('0x47', bytealigned=True)
        assert list(p) == [0, 6 * 8, 7 * 8, 13 * 8]
        p = a.find_all('0x4733', bytealigned=True)
        assert list(p) == [0, 7 * 8]
        a = Bits('0b1001001001001001001')
        p = a.find_all('0b1001', bytealigned=False)
        assert list(p) == [0, 3, 6, 9, 12, 15]

    def test_find_all_generator(self):
        a = Bits('0xff1234512345ff1234ff12ff')
        p = a.find_all('0xff', bytealigned=True)
        assert next(p) == 0
        assert next(p) == 6 * 8
        assert next(p) == 9 * 8
        assert next(p) == 11 * 8
        with pytest.raises(StopIteration):
            _ = next(p)

    def test_find_all_count(self):
        s = Bits('0b1') * 100
        for i in [0, 1, 23]:
            assert len(list(s.find_all('0b1', count=i))) == i
        with pytest.raises(ValueError):
            _ = s.find_all('0b1', bytealigned=True, count=-1)

    def test_contains(self):
        a = Bits('0b1') + '0x0001dead0001'
        assert '0xdead' in a
        assert not '0xfeed' in a

    def test_repr(self):
        max_ = bitformat.bits.MAX_CHARS
        bls = ['', '0b1', '0o5', '0x43412424f41', '0b00101001010101']
        for bs in bls:
            a = Bits(bs)
            b = eval(a.__repr__())
            assert a == b
        a = Bits('0b1')
        assert repr(a) == "Bits('0b1')"
        a += '0b11'
        assert repr(a) == "Bits('0b111')"
        a += '0b1'
        assert repr(a) == "Bits('0xf')"
        a *= max_
        assert repr(a) == "Bits('0x" + "f" * max_ + "')"
        # a += '0xf'
        # assert repr(a) == "Bits('0x" + "f" * max_ + "...')  # length=%d" % (max_ * 4 + 4)

    def test_iter(self):
        a = Bits('0b001010')
        b = Bits()
        for bit in a:
            b = b.append(Bits.build('bool', bit))
        assert a == b

    def test_non_zero_bits_at_end(self):
        a = Bits.from_bytes(b'\xff')[:5]
        b = Bits('0b00')
        a += b
        assert a == '0b1111100'
        assert a.tobytes() == b'\xf8'
        with pytest.raises(ValueError):
            _ = a.bytes

    def test_slice_step(self):
        a = Bits('0x3')
        b = a[::1]
        assert a == b
        assert a[2:4:1] == '0b11'
        assert a[0:2:1] == '0b00'
        assert a[:3] == '0o1'

        a = Bits('0x0011223344556677')
        assert a[-8:] == '0x77'
        assert a[:-24] == '0x0011223344'
        assert a[-1000:-24] == '0x0011223344'

    def test_interesting_slice_step(self):
        a = Bits('0b0011000111')
        assert a[7:3:-1] == '0b1000'
        assert a[9:2:-1] == '0b1110001'
        assert a[8:2:-2] == '0b100'
        assert a[100:-20:-3] == '0b1010'
        assert a[100:-20:-1] == '0b1110001100'
        assert a[10:2:-1] == '0b1110001'
        assert a[100:2:-1] == '0b1110001'

    def test_overwrite_order_and_bitpos(self):
        a = Bits('0xff')
        a = a.overwrite('0xa', 0)
        assert a == '0xaf'
        a = a.overwrite('0xb', 4)
        assert a == '0xab'
        a = a.overwrite('0xa', 4)
        assert a == '0xaa'
        a = a.overwrite(a, 0)
        assert a == '0xaa'

    def test_reverse_with_slice(self):
        a = Bits('0x0012ff')
        a = a.reverse()
        assert a == '0xff4800'
        a = a.reverse(8, 16)
        assert a == '0xff1200'

    def test_reverse_with_slice_errors(self):
        a = Bits('0x123')
        with pytest.raises(ValueError):
            _ = a.reverse(-1, 4)
        with pytest.raises(ValueError):
            _ = a.reverse(10, 9)
        with pytest.raises(ValueError):
            _ = a.reverse(1, 10000)

    def test_cut(self):
        a = Bits('0x00112233445')
        b = list(a.cut(8))
        assert b == ['0x00', '0x11', '0x22', '0x33', '0x44', '0x5']
        b = list(a.cut(4, 8, 16))
        assert b == ['0x1', '0x1']
        b = list(a.cut(4, 0, 44, 4))
        assert b == ['0x0', '0x0', '0x1', '0x1']
        a = Bits()
        b = list(a.cut(10))
        assert not b

    def test_cut_errors(self):
        a = Bits('0b1')
        b = a.cut(1, 1, 2)
        with pytest.raises(ValueError):
            _ = next(b)
        b = a.cut(1, -2, 1)
        with pytest.raises(ValueError):
            _ = next(b)
        b = a.cut(0)
        with pytest.raises(ValueError):
            _ = next(b)
        b = a.cut(1, count=-1)
        with pytest.raises(ValueError):
            _ = next(b)

    def test_cut_problem(self):
        s = Bits('0x1234')
        for n in list(s.cut(4)):
            s = s.prepend(n)
        assert s == '0x43211234'

    def test_join_functions(self):
        a = Bits.join(['0xa', '0xb', '0b1111'])
        assert a == '0xabf'

    def test_difficult_prepends(self):
        a = Bits('0b1101011')
        b = Bits()
        for i in range(10):
            b = b.prepend(a)
        assert b == a * 10

    def test_token_parser(self):
        tp = bitformat.utils.tokenparser
        assert tp('hex') == (True, [('hex', None, None)])
        assert tp('hex=14') == (True, [('hex', None, '14')])
        assert tp('0xef') == (False, [('0x', None, 'ef')])
        assert tp('uint:12') == (False, [('uint', 12, None)])
        assert tp('int:30=-1') == (False, [('int', 30, '-1')])
        assert tp('bits10') == (False, [('bits', 10, None)])
        assert tp('bits:10') == (False, [('bits', 10, None)])
        assert tp('123') == (False, [('bits', 123, None)])
        assert tp('123') == (False, [('bits', 123, None)])
        assert tp('hex12', ('hex12',)) == (False, [('hex12', None, None)])
        assert tp('2*bits:6') == (False, [('bits', 6, None), ('bits', 6, None)])

    def test_reverse_bytes(self):
        a = Bits('0x123456')
        a = a.byteswap()
        assert a == '0x563412'
        b = a + '0b1'
        b = b.byteswap()
        assert '0x123456, 0b1' == b
        a = Bits('0x54')
        a = a.byteswap()
        assert a == '0x54'
        a = Bits()
        a = a.byteswap()
        assert not a

    def test_reverse_bytes2(self):
        a = Bits()
        a = a.byteswap()
        assert a == Bits()
        a = Bits('0x00112233')
        a = a.byteswap(0, 0, 16)
        assert a == '0x11002233'
        a = a.byteswap(0, 4, 28)
        assert a == '0x12302103'
        a = a.byteswap(start=0, end=18)
        assert a == '0x30122103'
        with pytest.raises(ValueError):
            _ = a.byteswap(0, 10, 2)
        with pytest.raises(ValueError):
            _ = a.byteswap(0, -4, 4)
        with pytest.raises(ValueError):
            _ = a.byteswap(0, 24, 48)
        a = a.byteswap(0, 24)
        assert a == '0x30122103'
        a = a.byteswap(0, 11, 11)
        assert a == '0x30122103'

    def test_startswith(self):
        a = Bits()
        assert a.starts_with(Bits())
        assert not a.starts_with('0b0')
        a = Bits('0x12ff')
        assert a.starts_with('0x1')
        assert a.starts_with('0b0001001')
        assert a.starts_with('0x12ff')
        assert not a.starts_with('0x12ff, 0b1')
        assert not a.starts_with('0x2')

    def test_startswith_start_end(self):
        s = Bits('0x123456')
        assert s.starts_with('0x234', 4)
        assert not s.starts_with('0x123', end=11)
        assert s.starts_with('0x123', end=12)
        assert s.starts_with('0x34', 8, 16)
        assert not s.starts_with('0x34', 7, 16)
        assert not s.starts_with('0x34', 9, 16)
        assert not s.starts_with('0x34', 8, 15)

    def test_endswith(self):
        a = Bits()
        assert a.ends_with('')
        assert not a.ends_with(Bits('0b1'))
        a = Bits('0xf2341')
        assert a.ends_with('0x41')
        assert a.ends_with('0b001')
        assert a.ends_with('0xf2341')
        assert not a.ends_with('0x1f2341')
        assert not a.ends_with('0o34')

    def test_endswith_start_end(self):
        s = Bits('0x123456')
        assert s.ends_with('0x234', end=16)
        assert not s.ends_with('0x456', start=13)
        assert s.ends_with('0x456', start=12)
        assert s.ends_with('0x34', 8, 16)
        assert s.ends_with('0x34', 7, 16)
        assert not s.ends_with('0x34', 9, 16)
        assert not s.ends_with('0x34', 8, 15)

    def test_const_bit_stream_set_creation(self):
        sl = [Bits.build('u7', i) for i in range(15)]
        s = set(sl)
        assert len(s) == 15
        s.add(Bits('0b0000011'))
        assert len(s) == 15

    def test_const_bit_stream_hashibility(self):
        a = Bits('0x1')
        b = Bits('0x2')
        c = Bits('0x1')
        s = {a, b, c}
        assert len(s) == 2
        assert hash(a) == hash(c)

    def test_const_hashability_again(self):
        a = Bits.build('u10000', 1 << 300)
        b = Bits.build('u10000', 2 << 300)
        c = Bits.build('u10000', 3 << 300)
        s = {a, b, c}
        assert len(s) == 3

    def test_hash_edge_cases(self):
        a = Bits('0xabcd')
        b = Bits('0xabcd')
        c = b[1:]
        assert hash(a) == hash(b)
        assert hash(a) != hash(c)

    def test_const_bits_copy(self):
        a = Bits('0xabc')
        b = copy.copy(a)
        assert id(a._bitstore) == id(b._bitstore)


class TestSet:
    def test_set(self):
        a = Bits.zeros(16)
        a = a.set(True, 0)
        assert a == '0b10000000 00000000'
        a = a.set(1, 15)
        assert a == '0b10000000 00000001'
        b = a[4:12]
        b = b.set(True, 1)
        assert b == '0b01000000'
        b = b.set(True, -1)
        assert b == '0b01000001'
        b = b.set(1, -8)
        assert b == '0b11000001'
        with pytest.raises(IndexError):
            _ = b.set(True, -9)
        with pytest.raises(IndexError):
            _ = b.set(True, 8)

    def test_set_negative_index(self):
        a = Bits.zeros(10)
        a = a.set(1, -1)
        assert a.bin == '0000000001'
        a = a.set(1, [-1, -10])
        assert a.bin == '1000000001'
        with pytest.raises(IndexError):
            _ = a.set(1, [-11])

    def test_set_list(self):
        a = Bits.zeros(18)
        a = a.set(True, range(18))
        assert a.int == -1
        a = a.set(False, range(18))
        assert a.int == 0

    def test_unset(self):
        a = Bits.ones(16)
        a = a.set(False, 0)
        assert ~a == '0b10000000 00000000'
        a = a.set(0, 15)
        assert ~a == '0b10000000 00000001'
        b = a[4:12]
        b = b.set(False, 1)
        assert ~b == '0b01000000'
        b = b.set(False, -1)
        assert ~b == '0b01000001'
        b = b.set(False, -8)
        assert ~b == '0b11000001'
        with pytest.raises(IndexError):
            _ = b.set(False, -9)
        with pytest.raises(IndexError):
            _ = b.set(False, 8)

    def test_set_whole_bit_stream(self):
        a = Bits.zeros(10000)
        a = a.set(1)
        assert a.all(1)
        a = a.set(0)
        assert a.all(0)


class TestInvert:
    def test_invert_bits(self):
        a = Bits('0b111000')
        a = a.invert(range(len(a)))
        assert a == '0b000111'
        a = a.invert([0, 1, -1])
        assert a == '0b110110'

    def test_invert_whole_bit_stream(self):
        a = Bits('0b11011')
        a = a.invert()
        assert a == '0b00100'

    def test_invert_single_bit(self):
        a = Bits('0b000001')
        a = a.invert(0)
        assert a.bin == '100001'
        a = a.invert(-1)
        assert a.bin == '100000'

    def test_invert_errors(self):
        a = Bits.zeros(10)
        with pytest.raises(IndexError):
            _ = a.invert(10)
        with pytest.raises(IndexError):
            _ = a.invert(-11)
        with pytest.raises(IndexError):
            _ = a.invert([1, 2, 10])

    def test_ior(self):
        a = Bits('0b1101001')
        a |= '0b1110000'
        assert a == '0b1111001'
        b = a[2:]
        c = a[1:-1]
        b |= c
        assert c == '0b11100'
        assert b == '0b11101'

    def test_iand(self):
        a = Bits('0b0101010101000')
        a &= '0b1111110000000'
        assert a == '0b0101010000000'

    def test_ixor(self):
        a = Bits('0b11001100110011')
        a ^= '0b11111100000010'
        assert a == '0b00110000110001'

    def test_logical_inplace_errors(self):
        a = Bits.zeros(4)
        with pytest.raises(ValueError):
            a |= '0b111'
        with pytest.raises(ValueError):
            a &= '0b111'
        with pytest.raises(ValueError):
            a ^= '0b111'


class TestAllAndAny:
    def test_all(self):
        a = Bits('0b0111')
        assert a.all(True, (1, 3))
        assert not a.all(True, (0, 1, 2))
        assert a.all(True, [-1])
        assert not a.all(True, [0])

    def test_any(self):
        a = Bits('0b10011011')
        assert a.any(True, (1, 2, 3, 5))
        assert not a.any(True, (1, 2, 5))
        assert a.any(True, (-1,))
        assert not a.any(True, (1,))

    def test_all_false(self):
        a = Bits('0b0010011101')
        assert a.all(False, (0, 1, 3, 4))
        assert not a.all(False, (0, 1, 2, 3, 4))

    def test_any_false(self):
        a = Bits('0b01001110110111111111111111111')
        assert a.any(False, (4, 5, 6, 2))
        assert not a.any(False, (1, 15, 20))

    def test_any_empty_bitstring(self):
        a = Bits()
        assert not a.any(True)
        assert not a.any(False)

    def test_all_empty_bit_stream(self):
        a = Bits()
        assert a.all(True)
        assert a.all(False)

    def test_any_whole_bitstring(self):
        a = Bits('0xfff')
        assert a.any(True)
        assert not a.any(False)

    def test_all_whole_bitstring(self):
        a = Bits('0xfff')
        assert a.all(True)
        assert not a.all(False)

    def test_errors(self):
        a = Bits('0xf')
        with pytest.raises(IndexError):
            a.all(True, [5])
        with pytest.raises(IndexError):
            a.all(True, [-5])
        with pytest.raises(IndexError):
            a.any(True, [5])
        with pytest.raises(IndexError):
            a.any(True, [-5])

    ###################


class TestMoreMisc:

    def test_float_init_strings(self):
        for s in ('5', '+0.0001', '-1e101', '4.', '.2', '-.65', '43.21E+32'):
            a = Bits.from_string(f'float64={s}')
            assert a.float == float(s)
        for s in ('5', '+0.5', '-1e2', '4.', '.25', '-.75'):
            a = Bits.build('f16', s)
            assert a.f == float(s)
    def test_ror(self):
        a = Bits('0b11001')
        a = a.ror(0)
        assert a == '0b11001'
        a = a.ror(1)
        assert a == '0b11100'
        a = a.ror(5)
        assert a == '0b11100'
        a = a.ror(101)
        assert a == '0b01110'
        a = Bits('0b1')
        a = a.ror(1000000)
        assert a == '0b1'

    def test_ror_errors(self):
        a = Bits()
        with pytest.raises(ValueError):
            _ = a.ror(0)
        a += '0b001'
        with pytest.raises(ValueError):
            _ = a.ror(-1)

    def test_rol(self):
        a = Bits('0b11001')
        a = a.rol(0)
        assert a == '0b11001'
        a = a.rol(1)
        assert a == '0b10011'
        a = a.rol(5)
        assert a == '0b10011'
        a = a.rol(101)
        assert a == '0b00111'
        a = Bits('0b1')
        a = a.rol(1000000)
        assert a == '0b1'

    def test_rol_errors(self):
        a = Bits()
        with pytest.raises(ValueError):
            a.rol(0)
        a += '0b001'
        with pytest.raises(ValueError):
            a.rol(-1)

    def test_init_with_zeros(self):
        a = Bits.zeros(0)
        assert not a
        a = Bits.zeros(1)
        assert a == '0b0'
        a = Bits.zeros(1007)
        assert a == Bits.from_string('u1007 = 0')
        with pytest.raises(bitformat.CreationError):
            _ = Bits.zeros(-1)
        with pytest.raises(TypeError):
            a += 10

    def test_add_verses_in_place_add(self):
        a1 = Bits('0xabc')
        b1 = a1
        a1 += '0xdef'
        assert a1 == '0xabcdef'
        assert b1 == '0xabc'

    def test_and_verses_in_place_and(self):
        a1 = Bits('0xabc')
        b1 = a1
        a1 &= '0xf0f'
        assert a1 == '0xa0c'
        assert b1 == '0xabc'

    def test_or_verses_in_place_or(self):
        a1 = Bits('0xabc')
        b1 = a1
        a1 |= '0xf0f'
        assert a1 == '0xfbf'
        assert b1 == '0xabc'

    def test_xor_verses_in_place_xor(self):
        a1 = Bits('0xabc')
        b1 = a1
        a1 ^= '0xf0f'
        assert a1 == '0x5b3'
        assert b1 == '0xabc'

    def test_mul_verses_in_place_mul(self):
        a1 = Bits('0xabc')
        b1 = a1
        a1 *= 3
        assert a1 == '0xabcabcabc'
        assert b1 == '0xabc'

    def test_lshift_verses_in_place_lshift(self):
        a1 = Bits('0xabc')
        b1 = a1
        a1 <<= 4
        assert a1 == '0xbc0'
        assert b1 == '0xabc'

    def test_rshift_verses_in_place_rshift(self):
        a1 = Bits('0xabc')
        b1 = a1
        a1 >>= 4
        assert a1 == '0x0ab'
        assert b1 == '0xabc'


class TestBugs:
    def test_bug_in_replace(self):
        s = Bits('0x00112233')
        s = s.replace('0x22', '0xffff', start=8, bytealigned=True)
        assert s == '0x0011ffff33'
        s = Bits('0x0123412341234')
        s = s.replace('0x23', '0xf', start=9, bytealigned=True)
        assert s == '0x012341f41f4'

    def test_function_negative_indices(self):
        # insert
        s = Bits('0b0111')
        s = s.insert('0b0', -1)
        assert s == '0b01101'
        with pytest.raises(ValueError):
            _ = s.insert('0b0', -1000)

        # reverse
        s = s.reverse(-2)
        assert s == '0b01110'
        t = Bits('0x778899abcdef')
        t = t.reverse(-12, -4)
        assert t == '0x778899abc7bf'

        # reversebytes
        t = t.byteswap(0, -40, -16)
        assert t == '0x77ab9988c7bf'

        # overwrite
        t = t.overwrite('0x666', -20)
        assert t == '0x77ab998666bf'

        # find
        found = t.find('0x998', bytealigned=True, start=-31)
        assert found is None
        found = t.find('0x998', bytealigned=True, start=-32)
        assert found == 16
        found = t.find('0x988', bytealigned=True, end=-21)
        assert found is None
        found = t.find('0x998', bytealigned=True, end=-20)
        assert found == 16

        # find_all
        s = Bits('0x1234151f')
        li = list(s.find_all('0x1', bytealigned=True, start=-15))
        assert li == [24]
        li = list(s.find_all('0x1', bytealigned=True, start=-16))
        assert li == [16, 24]
        li = list(s.find_all('0x1', bytealigned=True, end=-5))
        assert li == [0, 16]
        li = list(s.find_all('0x1', bytealigned=True, end=-4))
        assert li == [0, 16, 24]

        # rfind
        found = s.rfind('0x1f', end=-1)
        assert found is None
        found = s.rfind('0x12', start=-31)
        assert found is None

        # cut
        s = Bits('0x12345')
        li = list(s.cut(4, start=-12, end=-4))
        assert li == ['0x3', '0x4']

        # startswith
        s = Bits('0xfe0012fe1200fe')
        assert s.starts_with('0x00f', start=-16)
        assert s.starts_with('0xfe00', end=-40)
        assert not s.starts_with('0xfe00', end=-41)

        # endswith
        assert s.ends_with('0x00fe', start=-16)
        assert not s.ends_with('0x00fe', start=-15)
        assert not s.ends_with('0x00fe', end=-1)
        assert s.ends_with('0x00f', end=-4)

        # replace
        s = s.replace('0xfe', '', end=-1)
        assert s == '0x00121200fe'
        s = s.replace('0x00', '', start=-24)
        assert s == '0x001212fe'

    def test_rotate_start_and_end(self):
        a = Bits('0b110100001')
        a = a.rol(1, 3, 6)
        assert a == '0b110001001'
        a = a.ror(1, start=-4)
        assert a == '0b110001100'
        a = a.rol(202, end=-5)
        assert a == '0b001101100'
        a = a.ror(3, end=4)
        assert a == '0b011001100'
        with pytest.raises(ValueError):
            _ = a.rol(5, start=-4, end=-6)

    def test_byte_swap_int(self):
        s = Bits('0xf234567f')
        s = s.byteswap(1, start=4)
        assert s == '0xf234567f'
        s = s.byteswap(2, start=4)
        assert s == '0xf452367f'
        s = s.byteswap(2, start=4, end=-4)
        assert s == '0xf234567f'
        s = s.byteswap(3)
        assert s == '0x5634f27f'
        s = s.byteswap(2, repeat=False)
        assert s == '0x3456f27f'

    def test_byte_swap_pack_code(self):
        s = Bits('0x0011223344556677')
        s = s.byteswap(1)
        assert s == '0x0011223344556677'

    def test_byte_swap_iterable(self):
        s = Bits('0x0011223344556677')
        s = s.byteswap(range(1, 4), repeat=False)
        assert s == '0x0022115544336677'
        s = s.byteswap([2], start=8)
        assert s == '0x0011224455663377'
        s = s.byteswap([2, 3], start=4)
        assert s == '0x0120156452463377'

    def test_byte_swap_errors(self):
        s = Bits('0x0011223344556677')
        with pytest.raises(ValueError):
            s.byteswap('z')
        with pytest.raises(ValueError):
            s.byteswap(-1)
        with pytest.raises(ValueError):
            s.byteswap([-1])
        with pytest.raises(ValueError):
            s.byteswap([1, 'e'])
        with pytest.raises(ValueError):
            s.byteswap('!h')
        with pytest.raises(ValueError):
            s.byteswap(2, start=-1000)
        with pytest.raises(TypeError):
            s.byteswap(5.4)

    def test_unicode(self):
        a = Bits(u'uint:12=34')
        assert a.uint == 34
        a += u'0xfe'
        assert a == 'u12 = 34, 0xfe'


def test_bool_interpretation():
    a = Bits('0b1')
    assert a.bool is True
    b = Bits('0b0')
    assert b.bool is False


def test_count():
    a = Bits('0xf0f')
    assert a.count(True) == 8
    assert a.count(False) == 4

    b = Bits()
    assert b.count(True) == 0
    assert b.count(False) == 0

    a = Bits('0xff0120ff')
    b = a[1:-1]
    assert b.count(1) == 16
    assert b.count(0) == 14


def test_overwrite_with_self():
    s = Bits('0b1101')
    s = s.overwrite(s, 0)
    assert s == '0b1101'


def test_byte_swap():
    b = Bits.from_bytes(b'\x01\x02\x03\x04')
    b = b.byteswap()
    assert b == '0x04030201'
