#!/usr/bin/env python

import pytest
import bitformat
import copy
from bitformat import Bits


class TestFlexibleInitialisation:
    def test_flexible_initialisation(self):
        a = Bits("u 8=12")
        c = Bits(" u  8 =  12")
        assert a == c == Bits.from_dtype("u8", 12)
        assert a.u == 12
        a = Bits("     i2=  -1")
        b = Bits("i 2   = -1")
        c = Bits(" i  2  =-1  ")
        assert a == b == c == Bits.from_dtype("i2", -1)

    def test_flexible_initialisation2(self):
        h = Bits("hex=12")
        o = Bits("oct=33")
        b = Bits("bin=10")
        assert h == "0x12"
        assert o == "0o33"
        assert b == "0b10"

    def test_multiple_string_initialisation(self):
        a = Bits("0b1 , 0x1")
        assert a == "0b10001"
        b = Bits("u32 = 12, 0b11") + "i100=-100, 0o44"
        assert b[0:32].u == 12
        assert b[32:34].bin == "11"
        assert b[34:134].i == -100


class TestFind:
    def test_find1(self):
        s = Bits("0b0000110110000")
        assert s.find(Bits("0b11011")) == 4

    def test_find_with_offset(self):
        s = Bits("0x112233")[4:]
        assert s.find("0x23") == 8

    def test_find_corner_cases(self):
        s = Bits("0b000111000111")
        assert s.find("0b000") == 0
        assert s.find("0b0111000111") == 2
        assert s[2:].find("0b000") == 4

    def test_find_bytes(self):
        s = Bits.from_string("0x010203040102ff")
        assert s.find("0x05", byte_aligned=True) is None
        assert s.find("0x02", byte_aligned=True) == 8
        assert s[16:].find("0x02", byte_aligned=True) == 24
        assert s[1:].find("0x02", byte_aligned=True) == 0

    def test_find_bytes_aligned_corner_cases(self):
        s = Bits("0xff")
        assert s.find(s) is not None
        assert s.find(Bits("0x12")) is None
        assert s.find(Bits("0xffff")) is None

    def test_find_byte_aligned(self):
        s = Bits.from_dtype("hex", "0x12345678")
        assert s.find(Bits("0x56"), byte_aligned=True) == 16
        assert not s[16:].find(Bits("0x45"), byte_aligned=True)
        s = Bits("0x1234")
        assert s.find("0x1234") == 0

    def test_find_byte_aligned_with_offset(self):
        s = Bits("0x112233")[4:]
        assert s.find("0x23", byte_aligned=True) == 8

    def test_find_byte_aligned_errors(self):
        s = Bits("0xffff")
        with pytest.raises(ValueError):
            s.find("")
        with pytest.raises(ValueError):
            s.find(Bits())


class TestRfind:
    def test_rfind(self):
        a = Bits("0b001001001")
        b = a.rfind("0b001")
        assert b == 6
        big = Bits.from_zeros(100000) + "0x12" + Bits.from_zeros(10000)
        found = big.rfind("0x12", byte_aligned=True)
        assert found == 100000

    def test_rfind_byte_aligned(self):
        a = Bits("0x8888")
        b = a.rfind("0b1", byte_aligned=True)
        assert b == 8

    def test_rfind_startbit(self):
        a = Bits("0x0000ffffff")
        b = a[1:].rfind("0x0000", byte_aligned=True)
        assert b is None

    def test_rfind_endbit(self):
        a = Bits("0x000fff")
        b = a[0:14].rfind("0b011", byte_aligned=False)
        assert b is not None
        b = a[0:13].rfind("0b011", False)
        assert b is None

    def test_rfind_errors(self):
        a = Bits("0x43234234")
        with pytest.raises(ValueError):
            a.rfind("", byte_aligned=True)


class TestShift:
    def test_shift_left(self):
        s = Bits.from_string("0b1010")
        t = s << 1
        assert s.bin == "1010"
        assert t.bin == "0100"
        s = t << 0
        assert s == "0b0100"
        t = s << 100
        assert t.bin == "0000"

    def test_shift_left_errors(self):
        s = Bits()
        with pytest.raises(ValueError):
            _ = s << 1
        s = Bits("0xf")
        with pytest.raises(ValueError):
            _ = s << -1

    def test_shift_right(self):
        s = Bits("0b1010")
        t = s >> 1
        assert s.bin == "1010"
        assert t.bin == "0101"
        q = s >> 0
        assert q == "0b1010"
        t = s >> 100
        assert t.bin == "0000"

    def test_shift_right_errors(self):
        s = Bits()
        with pytest.raises(ValueError):
            _ = s >> 1
        s = Bits("0xf")
        with pytest.raises(ValueError):
            _ = s >> -1


class TestReplace:
    def test_replace1(self):
        a = Bits("0b1")
        a = a.replace("0b1", "0b0", byte_aligned=True)
        assert a.bin == "0"
        a = a.replace("0b1", "0b0", byte_aligned=True)
        assert a.bin == "0"

    def test_replace2(self):
        a = Bits("0b00001111111")
        a = a.replace("0b1", "0b0", byte_aligned=True)
        assert a.bin == "00001111011"
        a = a.replace("0b1", "0b0", byte_aligned=False)
        assert a.bin == "00000000000"

    def test_replace3(self):
        a = Bits("0b0")
        a = a.replace("0b0", "0b110011111", byte_aligned=True)
        assert a.bin == "110011111"
        a = a.replace("0b11", "", byte_aligned=False)
        assert a.bin == "001"

    def test_replace4(self):
        a = Bits("0x00114723ef4732344700")
        a = a.replace("0x47", "0x00", byte_aligned=True)
        assert a.hex == "00110023ef0032340000"
        a = a.replace("0x00", "", byte_aligned=True)
        assert a.hex == "1123ef3234"
        a = a.replace("0x11", "", start=1, byte_aligned=True)
        assert a.hex == "1123ef3234"
        a = a.replace("0x11", "0xfff", start=7, byte_aligned=True)
        assert a.hex == "1123ef3234"
        a = a.replace("0x11", "0xfff", start=0, byte_aligned=True)
        assert a.hex == "fff23ef3234"

    def test_replace5(self):
        a = Bits.from_string("0xab")
        b = Bits.from_string("0xcd")
        c = Bits.from_string("0xabef")
        c = c.replace(a, b)
        assert c == "0xcdef"
        assert a == "0xab"
        assert b == "0xcd"
        a = Bits("0x0011223344").replace("0x11", "0xfff", byte_aligned=True)
        assert a == "0x00fff223344"

    def test_replace_with_self(self):
        a = Bits("0b11")
        a = a.replace("0b1", a)
        assert a == "0xf"
        a = a.replace(a, a)
        assert a == "0xf"

    def test_replace_count(self):
        a = Bits("0x223344223344223344")
        a = a.replace("0x2", "0x0", count=0, byte_aligned=True)
        assert a.hex == "223344223344223344"
        a = a.replace("0x2", "0x0", count=1, byte_aligned=True)
        assert a.hex == "023344223344223344"
        a = a.replace("0x33", "", count=2, byte_aligned=True)
        assert a.hex == "02442244223344"
        a = a.replace("0x44", "0x4444", count=1435, byte_aligned=True)
        assert a.hex == "02444422444422334444"

    def test_replace_errors(self):
        a = Bits("0o123415")
        with pytest.raises(ValueError):
            a.replace("", Bits("0o7"), byte_aligned=True)


class TestSimpleConversions:
    def test_convert_to_uint(self):
        assert Bits("0x10").u == 16
        assert Bits("0b000111").u == 7

    def test_convert_to_int(self):
        assert Bits("0x10").i == 16
        assert Bits("0b11110").i == -2

    def test_convert_to_hex(self):
        assert Bits.from_bytes(b"\x00\x12\x23\xff").hex == "001223ff"
        s = Bits("0b11111")
        with pytest.raises(ValueError):
            _ = s.hex


def test_empty_bitstring():
    s = Bits()
    assert s.bin == ""
    assert s.hex == ""
    with pytest.raises(ValueError):
        _ = s.i
    with pytest.raises(ValueError):
        _ = s.u
    assert not s


class TestAppend:
    def test_append(self):
        s1 = Bits("0b00000")
        s1 = s1 + Bits.from_dtype("bool", True)
        assert s1.bin == "000001"
        assert (Bits("0x0102") + Bits("0x0304")).hex == "01020304"

    def test_append_same_bitstring(self):
        s1 = Bits("0xf0")[:6]
        s1 = s1 + s1
        assert s1.bin == "111100111100"


def test_insert():
    s = Bits("0x0011")
    s = s.insert(8, Bits("0x22"))
    assert s.hex == "002211"
    s = Bits.from_ones(0)
    s = s.insert(0, "0b101")
    assert s.bin == "101"


class TestSlice:
    def test_byte_aligned_slice(self):
        s = Bits("0x123456")
        assert s[8:16].hex == "34"
        s = s[8:24]
        assert len(s) == 16
        assert s.hex == "3456"
        s = s[0:8]
        assert s.hex == "34"

    def test_slice(self):
        s = Bits("0b000001111100000")
        s1 = s[0:5]
        s2 = s[5:10]
        s3 = s[10:15]
        assert s1.bin == "00000"
        assert s2.bin == "11111"
        assert s3.bin == "00000"


class TestInsert:
    def test_insert(self):
        s1 = Bits("0x123456")
        s2 = Bits("0xff")
        s1 = s1.insert(8, s2)
        assert s1.hex == "12ff3456"
        s1 = s1.insert(24, "0xee")
        assert s1.hex == "12ff34ee56"
        with pytest.raises(ValueError):
            _ = s1.insert(-1000, "0b1")
        with pytest.raises(ValueError):
            _ = s1.insert(1000, "0b1")

    def test_insert_null(self):
        s = Bits("0x123")
        s = s.insert(3, Bits())
        assert s.hex == "123"

    def test_insert_bits(self):
        one = Bits("0b1")
        zero = Bits("0b0")
        s = Bits("0b00").insert(0, one)
        assert s.bin == "100"
        s = s.insert(0, zero)
        assert s.bin == "0100"
        s = s.insert(len(s), one)
        assert s.bin == "01001"
        s = s.insert(2, s)
        assert s.bin == "0101001001"


class TestOverwriting:
    def test_overwrite_bit(self):
        s = Bits("0b0")
        s = s.overwrite(0, "0b1")
        assert s.bin == "1"

    def test_overwrite_limits(self):
        s = Bits.from_dtype("bin", "0b11111")
        s = s.overwrite(0, "0b000")
        assert s.bin == "00011"
        s = s.overwrite(2, "0b000")
        assert s.bin == "00000"

    def test_overwrite_null(self):
        s = Bits("0x342563fedec")
        s2 = s[:]
        s = s.overwrite(23, Bits())
        assert s.bin == s2.bin

    def test_overwrite_position(self):
        s1 = Bits("0x0123456")
        s2 = Bits("0xff")
        s1 = s1.overwrite(8, s2)
        assert s1.hex == "01ff456"
        s1 = s1.overwrite(0, "0xff")
        assert s1.hex == "ffff456"

    def test_overwrite_with_self(self):
        s = Bits("0x123")
        s = s.overwrite(0, s)
        assert s == "0x123"


class TestAdding:
    def test_adding(self):
        s1 = Bits("0x0102")
        s2 = Bits("0x0304")
        s3 = s1 + s2
        assert s1.hex == "0102"
        assert s2.hex == "0304"
        assert s3.hex == "01020304"
        s3 += s1
        assert s3.hex == "010203040102"
        assert s2[9:16].bin == "0000100"
        assert s1[0:9].bin == "000000010"
        s4 = Bits.from_dtype("bin", "000000010") + Bits("0b0000100")
        assert s4.bin == "0000000100000100"
        s5 = s1[0:9] + s2[9:16]
        assert s5.bin == "0000000100000100"

    def test_more_adding(self):
        s = Bits("0b00") + Bits() + Bits("0b11")
        assert s.bin == "0011"
        s = "0b01"
        s += Bits("0b11")
        assert s.bin == "0111"
        s = Bits("0x00")
        t = Bits("0x11")
        s += t
        assert s.hex == "0011"
        assert t.hex == "11"
        s += s
        assert s.hex == "00110011"

    def test_radd(self):
        s = "0xff" + Bits("0xee")
        assert s.hex == "ffee"

    def test_overwrite_errors(self):
        s = Bits("0b11111")
        with pytest.raises(ValueError):
            _ = s.overwrite(-10, Bits("0b1"))
        with pytest.raises(ValueError):
            _ = s.overwrite(6, Bits("0b1"))
        s = s.overwrite(5, "bin=0")
        assert s.bin == "111110"
        s = s.overwrite(1, Bits("0x00"))
        assert s.bin == "100000000"

    def test_get_item_with_positive_position(self):
        s = Bits("0b1011")
        assert s[0] == True
        assert s[1] == False
        assert s[2] == True
        assert s[3] == True
        with pytest.raises(IndexError):
            _ = s[4]

    def test_get_item_with_negative_position(self):
        s = Bits("0b1011")
        assert s[-1] == True
        assert s[-2] == True
        assert s[-3] == False
        assert s[-4] == True
        with pytest.raises(IndexError):
            _ = s[-5]

    def test_slicing(self):
        s = Bits("0x0123456789")
        assert s[0:8].hex == "01"
        assert not s[0:0]
        assert not s[23:20]
        assert s[8:12].bin == "0010"
        assert s[32:80] == "0x89"

    def test_negative_slicing(self):
        s = Bits("0x012345678")
        assert s[:-8].hex == "0123456"
        assert s[-16:-8].hex == "56"
        assert s[-24:].hex == "345678"
        assert s[-1000:-24] == "0x012"

    def test_len(self):
        s = Bits()
        assert len(s) == 0
        s = s + "0b001"
        assert len(s) == 3

    def test_join(self):
        s1 = Bits("0b0")
        s2 = Bits("0b1")
        s3 = Bits("0b000")
        s4 = Bits("0b111")
        strings = [s1, s2, s1, s3, s4]
        s = Bits.from_joined(strings)
        assert s.bin == "010000111"

    def test_join2(self):
        s1 = Bits("0x00f1")
        assert s1[4:12].hex == "0f"
        bsl = [s1[0:16], s1[4:12]]
        s = Bits.from_joined(bsl)
        assert s.hex == "00f10f"

        s1 = Bits("0x00112233445566778899aabbccddeeff")
        s2 = Bits("0b000011")
        bsl = [s1[0:32], s1[4:12], s2, s2, s2, s2]
        s = Bits.from_joined(bsl)
        assert s.hex == "00112233010c30c3"

        bsl = [Bits.from_dtype("u12", j) for j in range(10) for _ in range(10)]
        s = Bits.from_joined(bsl)
        assert len(s) == 1200

    def test_join_with_ints(self):
        with pytest.raises(TypeError):
            _ = Bits.from_joined([1, 2])

    def test_various_things2(self):
        s1 = Bits("0x1f08")[:13]
        assert s1.bin == "0001111100001"
        s2 = Bits("0b0101")
        assert s2.bin == "0101"
        s1 += s2
        assert len(s1) == 17
        assert s1.bin == "00011111000010101"
        s1 = s1[3:8]
        assert s1.bin == "11111"

    def test_various_things3(self):
        s1 = Bits("0x012480ff")[2:27]
        s2 = s1 + s1
        assert len(s2) == 50
        s3 = s2[0:25]
        s4 = s2[25:50]
        assert s3.bin == s4.bin

    def test_insert_using_auto(self):
        s = Bits("0xff")
        s = s.insert(4, "0x00")
        assert s.hex == "f00f"

    def test_overwrite_using_auto(self):
        s = Bits("0x0110")
        s = s.overwrite(0, "0b1")
        assert s.hex == "8110"
        s = s.overwrite(0, "")
        assert s.hex == "8110"

    def test_find_using_auto(self):
        s = Bits("0b000000010100011000")
        assert s.find("0b101") == 7

    def test_findbyte_aligned_using_auto(self):
        s = Bits("0x00004700")
        assert s.find("0b01000111", byte_aligned=True) == 16

    def test_append_using_auto(self):
        s = Bits("0b000")
        s = s + "0b111"
        assert s.bin == "000111"
        s = s + "0b0"
        assert s.bin == "0001110"

    def test_prepend(self):
        s = Bits("0b000")
        s = "0b11" + s
        assert s.bin == "11000"
        s = s + s
        assert s.bin == "1100011000"
        s = "" + s
        assert s.bin == "1100011000"

    def test_null_slice(self):
        s = Bits("0x111")
        t = s[1:1]
        assert len(t) == 0

    def test_multiple_autos(self):
        s = Bits("0xa")
        s = "0xf" + s
        s = s + "0xb"
        assert s == "0xfab"
        s = s + s
        s = s + "0x100"
        s = s.overwrite(4, "0x5")
        assert s == "0xf5bfab100"

    def test_reverse(self):
        s = Bits("0b0011")
        s = s.reverse()
        assert s.bin == "1100"
        s = Bits("0b10")
        s = s.reverse()
        assert s.bin == "01"
        s = Bits()
        s = s.reverse()
        assert s.bin == ""

    def test_init_with_concatenated_strings(self):
        s = Bits("0xff, 0xee,0xd ,0xcc")
        assert s.hex == "ffeedcc"
        s = Bits("0b0 ,0b111 ,0b001")
        assert s.bin == "0111001"
        s = Bits("0xffee")
        assert s.hex == "ffee"
        s = Bits("  0o123 ,0o7 ,0o1")
        assert s.oct == "12371"
        s += "  0o 332"
        assert s.oct == "12371332"

    def test_equals(self):
        s1 = Bits("0b01010101")
        s2 = Bits("0b01010101")
        assert s1 == s2
        s3 = Bits()
        s4 = Bits()
        assert s3 == s4
        assert not s3 != s4

    def test_large_equals(self):
        s1 = Bits.from_zeros(1000000)
        s2 = Bits.from_zeros(1000000)
        s1 = s1.set(True, [-1, 55, 53214, 534211, 999999])
        s2 = s2.set(True, [-1, 55, 53214, 534211, 999999])
        assert s1 == s2
        s1 = s1.set(True, 800000)
        assert s1 != s2

    def test_not_equals(self):
        s1 = Bits("0b0")
        s2 = Bits("0b1")
        assert s1 != s2
        assert not s1 != Bits("0b0")

    def test_equality_with_auto_initialised(self):
        a = Bits("0b00110111")
        assert a == "0b00110111"
        assert a == "0x37"
        assert "0b0011 0111" == a
        assert "0x37" == a
        assert not a == "0b11001000"
        assert not "0x3737" == a

    def test_invert_special_method(self):
        s = Bits("0b00011001")
        assert (~s).bin == "11100110"
        assert (~Bits("0b0")).bin == "1"
        assert (~Bits("0b1")).bin == "0"
        assert ~~s == s

    def test_invert_special_method_errors(self):
        s = Bits()
        with pytest.raises(ValueError):
            _ = ~s

    def test_join_with_auto(self):
        s = Bits.from_joined(["0xf", "0b00", Bits.from_dtype("bin", "11")])
        assert s == "0b11110011"


class TestMultiplication:
    def test_multiplication(self):
        a = Bits("0xff")
        b = a * 8
        assert b == "0xffffffffffffffff"
        b = 4 * a
        assert b == "0xffffffff"
        assert 1 * a == a * 1 == a
        c = a * 0
        assert not c
        a *= 3
        assert a == "0xffffff"
        a *= 0
        assert not a
        one = Bits("0b1")
        zero = Bits("0b0")
        mix = one * 2 + 3 * zero + 2 * one * 2
        assert mix == "0b110001111"
        q = Bits()
        q *= 143
        assert not q
        q += Bits.from_bools([True, True, False])
        q *= 0
        assert not q

    def test_multiplication_errors(self):
        a = Bits("0b1")
        b = Bits("0b0")
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
        a = Bits("0b01101")
        b = Bits("0b00110")
        assert (a & b).bin == "00100"
        assert (a & "0b11111") == a
        with pytest.raises(ValueError):
            _ = a & "0b1"
        with pytest.raises(ValueError):
            _ = b & "0b110111111"
        c = Bits("0b0011011")
        d = c & "0b1111000"
        assert d.bin == "0011000"
        d = "0b1111000" & c
        assert d.bin == "0011000"

    def test_bitwise_or(self):
        a = Bits("0b111001001")
        b = Bits("0b011100011")
        c = a | b
        assert c.bin == "111101011"
        assert (a | "0b000000000") == a
        with pytest.raises(ValueError):
            _ = a | "0b0000"
        with pytest.raises(ValueError):
            _ = b | (a + "0b1")
        a = "0xff00" | Bits("0x00f0")
        assert a.hex == "fff0"

    def test_bitwise_xor(self):
        a = Bits("0b111001001")
        b = Bits("0b011100011")
        c = a ^ b
        assert c.bin == "100101010"
        assert (a ^ "0b111100000").bin == "000101001"
        with pytest.raises(ValueError):
            _ = a ^ "0b0000"
        with pytest.raises(ValueError):
            _ = b ^ (a + "0b1")
        a = "0o707" ^ Bits("0o777")
        assert a.oct == "070"


class TestManyDifferentThings:
    def test_find_byte_aligned_with_bits(self):
        a = Bits("0x00112233445566778899")
        x = a.find("0b0001", byte_aligned=True)
        assert x == 8

    def test_find_startbit_not_byte_aligned(self):
        a = Bits("0b0010000100")
        found = a[4:].find("0b1")
        assert found == 3
        found = a[2:].find("0b1")
        assert found == 0
        found = a[8:].find("0b1", byte_aligned=False)
        assert found is None

    def test_find_endbit_not_byte_aligned(self):
        a = Bits("0b0010010000")
        found = a[:2].find("0b1", byte_aligned=False)
        assert found is None
        found = a[:3].find("0b1")
        assert found == 2
        found = a[3:5].find("0b1", byte_aligned=False)
        assert found is None
        found = a[3:6].find("0b1")
        assert found == 2

    def test_find_startbit_byte_aligned(self):
        a = Bits("0xff001122ff0011ff")
        found = a[24:].find("0x22", byte_aligned=True)
        assert found == 0
        found = a[40:].find("0b111", byte_aligned=True)
        assert found == 16

    def test_find_endbit_byte_aligned(self):
        a = Bits("0xff001122ff0011ff")
        found = a[:31].find("0x22", byte_aligned=True)
        assert found is None
        found = a[:32].find("0x22", byte_aligned=True)
        assert found == 24

    def test_find_all(self):
        a = Bits("0b11111")
        p = a.find_all("0b1")
        assert list(p) == [0, 1, 2, 3, 4]
        p = a.find_all("0b11")
        assert list(p) == [0, 1, 2, 3]
        p = a.find_all("0b10")
        assert list(p) == []
        a = Bits("0x4733eeff66554747335832434547")
        p = a.find_all("0x47", byte_aligned=True)
        assert list(p) == [0, 6 * 8, 7 * 8, 13 * 8]
        p = a.find_all("0x4733", byte_aligned=True)
        assert list(p) == [0, 7 * 8]
        a = Bits("0b1001001001001001001")
        p = a.find_all("0b1001", byte_aligned=False)
        assert list(p) == [0, 3, 6, 9, 12, 15]

    def test_find_all_generator(self):
        a = Bits("0xff1ff4512345ff1234ff12ff")
        p = a.find_all("0xff", byte_aligned=True)
        assert next(p) == 0
        assert next(p) == 6 * 8
        assert next(p) == 9 * 8
        assert next(p) == 11 * 8
        with pytest.raises(StopIteration):
            _ = next(p)

    def test_find_all_count(self):
        s = Bits("0b1") * 100
        for i in [0, 1, 23]:
            assert len(list(s.find_all("0b1", count=i))) == i
        with pytest.raises(ValueError):
            _ = s.find_all("0b1", byte_aligned=True, count=-1)

    def test_contains(self):
        a = Bits("0b1") + "0x0001dead0001"
        assert "0xdead" in a
        assert not "0xfeed" in a

    def test_repr(self):
        bls = ["", "0b1", "0o5", "0x43412424f41", "0b00101001010101"]
        for bs in bls:
            a = Bits(bs)
            b = eval(a.__repr__())
            assert a == b
        a = Bits("0b1")
        assert repr(a).splitlines()[0] == "Bits('0b1')"
        a += "0b11"
        assert repr(a).splitlines()[0] == "Bits('0b111')"
        a += "0b1"
        assert repr(a).splitlines()[0] == "Bits('0xf')"

    def test_iter(self):
        a = Bits("0b001010")
        b = Bits()
        for bit in a:
            b = b + Bits.from_dtype("bool", bit)
        assert a == b

    def test_non_zero_bits_at_end(self):
        a = Bits.from_bytes(b"\xff")[:5]
        b = Bits("0b00")
        a += b
        assert a == "0b1111100"
        assert a.to_bytes() == b"\xf8"
        with pytest.raises(ValueError):
            _ = a.bytes

    def test_slice_step(self):
        a = Bits("0x3")
        b = a[::1]
        assert a == b
        assert a[2:4:1] == "0b11"
        assert a[0:2:1] == "0b00"
        assert a[:3] == "0o1"

        a = Bits("0x0011223344556677")
        assert a[-8:] == "0x77"
        assert a[:-24] == "0x0011223344"
        assert a[-1000:-24] == "0x0011223344"

    # TODO: Reinstate this test. It's correct, but perhaps a bit _too_ interesting.
    # def test_interesting_slice_step(self):
    #     a = Bits("0b0011000111")
    #     assert a[7:3:-1] == "0b1000"
    #     assert a[9:2:-1] == "0b1110001"
    #     assert a[8:2:-2] == "0b100"
    #     assert a[100:-20:-3] == "0b1010"
    #     assert a[100:-20:-1] == "0b1110001100"
    #     assert a[10:2:-1] == "0b1110001"
    #     assert a[100:2:-1] == "0b1110001"

    def test_overwrite_order_and_bitpos(self):
        a = Bits("0xff")
        a = a.overwrite(0, "0xa")
        assert a == "0xaf"
        a = a.overwrite(4, "0xb")
        assert a == "0xab"
        a = a.overwrite(4, "0xa")
        assert a == "0xaa"
        a = a.overwrite(0, a)
        assert a == "0xaa"

    def test_reverse_with_slice(self):
        a = Bits("0x0012ff")
        a = a.reverse()
        assert a == "0xff4800"
        a = a[8:16].reverse()
        assert a == "0x12"

    def test_cut(self):
        a = Bits("0x00112233445")
        b = list(a.chunks(8))
        assert b == ["0x00", "0x11", "0x22", "0x33", "0x44", "0x5"]
        b = list(a[8:16].chunks(4))
        assert b == ["0x1", "0x1"]
        b = list(a[0:44].chunks(4, 4))
        assert b == ["0x0", "0x0", "0x1", "0x1"]
        a = Bits()
        b = list(a.chunks(10))
        assert not b

    def test_cut_errors(self):
        a = Bits("0b1")
        b = a.chunks(0)
        with pytest.raises(ValueError):
            _ = next(b)
        b = a.chunks(1, count=-1)
        with pytest.raises(ValueError):
            _ = next(b)

    def test_cut_problem(self):
        s = Bits("0x1234")
        for n in list(s.chunks(4)):
            s = n + s
        assert s == "0x43211234"

    def test_join_functions(self):
        a = Bits.from_joined(["0xa", "0xb", "0b1111"])
        assert a == "0xabf"

    def test_difficult_prepends(self):
        a = Bits("0b1101011")
        b = Bits()
        for i in range(10):
            b = a + b
        assert b == a * 10

    def test_reverse_bytes(self):
        a = Bits("0x123456")
        a = a.byte_swap()
        assert a == "0x563412"
        b = a + "0b1"
        with pytest.raises(ValueError):
            _ = b.byte_swap()
        a = Bits("0x54")
        a = a.byte_swap()
        assert a == "0x54"
        a = Bits()
        a = a.byte_swap()
        assert not a

    def test_startswith(self):
        a = Bits()
        assert a.starts_with(Bits())
        assert not a.starts_with("0b0")
        a = Bits("0x12ff")
        assert a.starts_with("0x1")
        assert a.starts_with("0b0001001")
        assert a.starts_with("0x12ff")
        assert not a.starts_with("0x12ff, 0b1")
        assert not a.starts_with("0x2")

    def test_startswith_start_end(self):
        s = Bits("0x123456")
        assert s[4:].starts_with("0x234")
        assert not s[:11].starts_with("0x123")
        assert s[:12].starts_with("0x123")
        assert s[8:16].starts_with("0x34")
        assert not s[7:16].starts_with("0x34")
        assert not s[9:16].starts_with("0x34")
        assert not s[8:15].starts_with("0x34")

    def test_endswith(self):
        a = Bits()
        assert a.ends_with("")
        assert not a.ends_with(Bits("0b1"))
        a = Bits("0xf2341")
        assert a.ends_with("0x41")
        assert a.ends_with("0b001")
        assert a.ends_with("0xf2341")
        assert not a.ends_with("0x1f2341")
        assert not a.ends_with("0o34")

    def test_endswith_start_end(self):
        s = Bits("0x123456")
        assert s[:16].ends_with("0x234")
        assert not s[13:].ends_with("0x456")
        assert s[12:].ends_with("0x456")
        assert s[8:16].ends_with("0x34")
        assert s[7:16].ends_with("0x34")
        assert not s[9:16].ends_with("0x34")
        assert not s[8:15].ends_with("0x34")

    def test_const_bit_stream_set_creation(self):
        sl = [Bits.from_dtype("u7", i) for i in range(15)]
        s = set(sl)
        assert len(s) == 15
        s.add(Bits("0b0000011"))
        assert len(s) == 15

    def test_const_bit_stream_hashibility(self):
        a = Bits("0x1")
        b = Bits("0x2")
        c = Bits("0x1")
        s = {a, b, c}
        assert len(s) == 2
        assert hash(a) == hash(c)

    def test_const_hashability_again(self):
        a = Bits.from_dtype("u10000", 1 << 300)
        b = Bits.from_dtype("u10000", 2 << 300)
        c = Bits.from_dtype("u10000", 3 << 300)
        s = {a, b, c}
        assert len(s) == 3

    def test_hash_edge_cases(self):
        a = Bits("0xabcd")
        b = Bits("0xabcd")
        c = b[1:]
        assert hash(a) == hash(b)
        assert hash(a) != hash(c)

    def test_const_bits_copy(self):
        a = Bits("0xabc")
        b = copy.copy(a)
        assert id(a._bitstore) == id(b._bitstore)


class TestSet:
    def test_set(self):
        a = Bits.from_zeros(16)
        a = a.set(True, 0)
        assert a == "0b10000000 00000000"
        a = a.set(1, 15)
        assert a == "0b10000000 00000001"
        b = a[4:12]
        b = b.set(True, 1)
        assert b == "0b01000000"
        b = b.set(True, -1)
        assert b == "0b01000001"
        b = b.set(1, -8)
        assert b == "0b11000001"
        with pytest.raises(IndexError):
            _ = b.set(True, -9)
        with pytest.raises(IndexError):
            _ = b.set(True, 8)

    def test_set_negative_index(self):
        a = Bits.from_string('0b0110000000')
        a = a.set(1, -1)
        assert a.bin == "0110000001"
        a = a.set(1, [-1, -10])
        assert a.bin == "1110000001"
        with pytest.raises(IndexError):
            _ = a.set(1, [-11])

    def test_set_list(self):
        a = Bits.from_zeros(18)
        a = a.set(True, range(18))
        assert a.i == -1
        a = a.set(False, range(18))
        assert a.i == 0

    def test_unset(self):
        a = Bits.from_ones(16)
        a = a.set(False, 0)
        assert ~a == "0b10000000 00000000"
        a = a.set(0, 15)
        assert ~a == "0b10000000 00000001"
        b = a[4:12]
        b = b.set(False, 1)
        assert ~b == "0b01000000"
        b = b.set(False, -1)
        assert ~b == "0b01000001"
        b = b.set(False, -8)
        assert ~b == "0b11000001"
        with pytest.raises(IndexError):
            _ = b.set(False, -9)
        with pytest.raises(IndexError):
            _ = b.set(False, 8)


class TestInvert:
    def test_invert_bits(self):
        a = Bits("0b111000")
        a = a.invert(range(len(a)))
        assert a == "0b000111"
        a = a.invert([0, 1, -1])
        assert a == "0b110110"

    def test_invert_whole_bit_stream(self):
        a = Bits("0b11011")
        a = a.invert()
        assert a == "0b00100"

    def test_invert_single_bit(self):
        a = Bits("0b000001")
        a = a.invert(0)
        assert a.bin == "100001"
        a = a.invert(-1)
        assert a.bin == "100000"

    def test_invert_errors(self):
        a = Bits.from_zeros(10)
        with pytest.raises(IndexError):
            _ = a.invert(10)
        with pytest.raises(IndexError):
            _ = a.invert(-11)
        with pytest.raises(IndexError):
            _ = a.invert([1, 2, 10])

    def test_ior(self):
        a = Bits("0b1101001")
        a |= "0b1110000"
        assert a == "0b1111001"
        b = a[2:]
        c = a[1:-1]
        b |= c
        assert c == "0b11100"
        assert b == "0b11101"

    def test_iand(self):
        a = Bits("0b0101010101000")
        a &= "0b1111110000000"
        assert a == "0b0101010000000"

    def test_ixor(self):
        a = Bits("0b11001100110011")
        a ^= "0b11111100000010"
        assert a == "0b00110000110001"

    def test_logical_inplace_errors(self):
        a = Bits.from_zeros(4)
        with pytest.raises(ValueError):
            a |= "0b111"
        with pytest.raises(ValueError):
            a &= "0b111"
        with pytest.raises(ValueError):
            a ^= "0b111"


class TestAllAndAny:
    def test_all(self):
        a = Bits("0b111")
        assert a.all()

    def test_any(self):
        a = Bits("0b10011011")
        assert a.any()

    def test_all_false(self):
        a = Bits("0b0010011101")
        assert not a.all()

    def test_any_false(self):
        a = Bits("0b0000")
        assert not a.any()

    def test_any_empty_bitstring(self):
        a = Bits()
        assert not a.any()  # Python any function returns False for empty iterables.

    def test_all_empty_bit_stream(self):
        a = Bits()
        assert a.all()  # Python all function returns True for empty iterables.

    def test_any_whole_bitstring(self):
        a = Bits("0xfff")
        assert a.any()

    def test_all_whole_bitstring(self):
        a = Bits("0xfff")
        assert a.all()

    ###################


class TestMoreMisc:
    def test_float_init_strings(self):
        for s in ("5", "+0.0001", "-1e101", "4.", ".2", "-.65", "43.21E+32"):
            a = Bits.from_string(f"f64={s}")
            assert a.f == float(s)
        for s in ("5", "+0.5", "-1e2", "4.", ".25", "-.75"):
            a = Bits.from_dtype("f16", s)
            assert a.f == float(s)

    def test_ror(self):
        a = Bits("0b11001")
        a = a.ror(0)
        assert a == "0b11001"
        a = a.ror(1)
        assert a == "0b11100"
        a = a.ror(5)
        assert a == "0b11100"
        a = a.ror(101)
        assert a == "0b01110"
        a = Bits("0b1")
        a = a.ror(1000000)
        assert a == "0b1"

    def test_ror_errors(self):
        a = Bits()
        with pytest.raises(ValueError):
            _ = a.ror(0)
        a += "0b001"
        with pytest.raises(ValueError):
            _ = a.ror(-1)

    def test_rol(self):
        a = Bits("0b11001")
        a = a.rol(0)
        assert a == "0b11001"
        a = a.rol(1)
        assert a == "0b10011"
        a = a.rol(5)
        assert a == "0b10011"
        a = a.rol(101)
        assert a == "0b00111"
        a = Bits("0b1")
        a = a.rol(1000000)
        assert a == "0b1"

    def test_rol_errors(self):
        a = Bits()
        with pytest.raises(ValueError):
            a.rol(0)
        a += "0b001"
        with pytest.raises(ValueError):
            a.rol(-1)

    def test_init_with_zeros(self):
        a = Bits.from_zeros(0)
        assert not a
        a = Bits.from_zeros(1)
        assert a == "0b0"
        a = Bits.from_zeros(1007)
        assert a == Bits.from_string("u1007 = 0")
        with pytest.raises(ValueError):
            _ = Bits.from_zeros(-1)
        with pytest.raises(TypeError):
            a += 10

    def test_add_verses_in_place_add(self):
        a1 = Bits("0xabc")
        b1 = a1
        a1 += "0xdef"
        assert a1 == "0xabcdef"
        assert b1 == "0xabc"

    def test_and_verses_in_place_and(self):
        a1 = Bits("0xabc")
        b1 = a1
        a1 &= "0xf0f"
        assert a1 == "0xa0c"
        assert b1 == "0xabc"

    def test_or_verses_in_place_or(self):
        a1 = Bits("0xabc")
        b1 = a1
        a1 |= "0xf0f"
        assert a1 == "0xfbf"
        assert b1 == "0xabc"

    def test_xor_verses_in_place_xor(self):
        a1 = Bits("0xabc")
        b1 = a1
        a1 ^= "0xf0f"
        assert a1 == "0x5b3"
        assert b1 == "0xabc"

    def test_mul_verses_in_place_mul(self):
        a1 = Bits("0xabc")
        b1 = a1
        a1 *= 3
        assert a1 == "0xabcabcabc"
        assert b1 == "0xabc"

    def test_lshift_verses_in_place_lshift(self):
        a1 = Bits("0xabc")
        b1 = a1
        a1 <<= 4
        assert a1 == "0xbc0"
        assert b1 == "0xabc"

    def test_rshift_verses_in_place_rshift(self):
        a1 = Bits("0xabc")
        b1 = a1
        a1 >>= 4
        assert a1 == "0x0ab"
        assert b1 == "0xabc"


class TestBugs:
    def test_bug_in_replace(self):
        s = Bits("0x00112233")
        s = s.replace("0x22", "0xffff", start=8, byte_aligned=True)
        assert s == "0x0011ffff33"
        s = Bits("0x0123412341234")
        s = s.replace("0x23", "0xf", start=9, byte_aligned=True)
        assert s == "0x012341f41f4"

    def test_function_negative_indices(self):
        # insert
        s = Bits("0b0111")
        s = s.insert(-1, "0b0")
        assert s == "0b01101"
        with pytest.raises(ValueError):
            _ = s.insert(-1000, "0b0")

        # overwrite
        t = Bits("0x77ab9988c7bf")
        t = t.overwrite(-20, "0x666")
        assert t == "0x77ab998666bf"

        # find
        found = t[-32:].find("0x998", byte_aligned=True)
        assert found == 0
        found = t[:-21].find("0x988", byte_aligned=True)
        assert found is None
        found = t[:-20].find("0x998", byte_aligned=True)
        assert found == 16

        # find_all
        s = Bits("0x1234151f")
        li = list(s[-15:].find_all("0x1"))
        assert li == [7]
        li = list(s[-16:].find_all("0x1", byte_aligned=True))
        assert li == [0, 8]
        li = list(s[:-5].find_all("0x1", byte_aligned=True))
        assert li == [0, 16]
        li = list(s[:-4].find_all("0x1", byte_aligned=True))
        assert li == [0, 16, 24]

        # rfind
        found = s[:-1].rfind("0x1f")
        assert found is None
        found = s[-31:].rfind("0x12")
        assert found is None

        # chunks
        s = Bits("0x12345")
        li = list(s[-12:-4].chunks(4))
        assert li == ["0x3", "0x4"]

        # startswith
        s = Bits("0xfe0012fe1200fe")
        assert s[-16:].starts_with("0x00f")
        assert s[:-40].starts_with("0xfe00")
        assert not s[:-41].starts_with("0xfe00")

        # endswith
        assert s[-16:].ends_with("0x00fe")
        assert not s[-15:].ends_with("0x00fe")
        assert not s[-1:].ends_with("0x00fe")
        assert s[:-4].ends_with("0x00f")

        # replace
        s = s.replace("0xfe", "", end=-1)
        assert s == "0x00121200fe"
        s = s.replace("0x00", "", start=-24)
        assert s == "0x001212fe"

    def test_rotate_start_and_end(self):
        a = Bits("0b110100001")
        a = a.rol(1, 3, 6)
        assert a == "0b110001001"
        a = a.ror(1, start=-4)
        assert a == "0b110001100"
        a = a.rol(202, end=-5)
        assert a == "0b001101100"
        a = a.ror(3, end=4)
        assert a == "0b011001100"
        with pytest.raises(ValueError):
            _ = a.rol(5, start=-4, end=-6)

    def test_byte_swap_int(self):
        s = Bits("0xf234567f")
        s = s.byte_swap(1)
        assert s == "0xf234567f"
        s = s.byte_swap(2)
        assert s == "0x34f27f56"
        s = s.byte_swap(2)
        assert s == "0xf234567f"
        with pytest.raises(ValueError):
            _ = s.byte_swap(3)

    def test_byte_swap_errors(self):
        s = Bits("0x0011223344556677")
        with pytest.raises(TypeError):
            s.byte_swap("z")
        with pytest.raises(ValueError):
            s.byte_swap(-1)
        with pytest.raises(TypeError):
            s.byte_swap([-1])
        with pytest.raises(ValueError):
            s.byte_swap(5.4)

    def test_unicode(self):
        a = Bits("u12=34")
        assert a.u == 34
        a += "0xfe"
        assert a == "u12 = 34, 0xfe"


def test_bool_interpretation():
    a = Bits("0b1")
    assert a.bool is True
    b = Bits("0b0")
    assert b.bool is False


def test_count():
    a = Bits("0xf0f")
    assert a.count(True) == 8
    assert a.count(False) == 4

    b = Bits()
    assert b.count(True) == 0
    assert b.count(False) == 0

    a = Bits("0xff0120ff")
    b = a[1:-1]
    assert b.count(1) == 16
    assert b.count(0) == 14


def test_overwrite_with_self():
    s = Bits("0b1101")
    s = s.overwrite(0, s)
    assert s == "0b1101"


def test_byte_swap():
    b = Bits.from_bytes(b"\x01\x02\x03\x04")
    b = b.byte_swap()
    assert b == "0x04030201"
