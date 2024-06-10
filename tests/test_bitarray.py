#!/usr/bin/env python

import pytest
import sys
import os
import bitarray
import bitformat
from bitformat import Bits, Dtype

sys.path.insert(0, '..')


class TestAll:
    def test_creation_from_uint(self):
        s = Bits.build('uint6', 15)
        assert s.bin == '001111'
        s = Bits.build('u1', 0)
        assert s.bin == '0'
        s = Bits.zeros(8)
        assert s.uint == 0

    def test_creation_from_oct(self):
        s = Bits.build(Dtype('oct'), '7')
        assert s.oct == '7'
        assert s.bin == '111'
        s += '0o1'
        assert s.bin == '111001'
        s = Bits() + '0o12345670'
        assert len(s) == 24
        assert s.bin == '001010011100101110111000'
        s = Bits.fromstring('0o123')
        assert s.oct == '123'

@pytest.mark.skip(reason='not implemented')
class TestNoPosAttribute:
    def test_replace(self):
        s = Bits.fromstring('0b01')
        s = s.replace('0b1', '0b11')
        assert s == '0b011'

    def test_insert(self):
        s = Bits.fromstring('0b00')
        s = s.insert('0xf', 1)
        assert s == '0b011110'

    def test_insert_self(self):
        b = Bits.fromstring('0b10')
        b = b.insert(b, 0)
        assert b == '0b1010'
        c = Bits.fromstring('0x00ff')
        c = c.insert(c, 8)
        assert c == '0x0000ffff'
        a = Bits.fromstring('0b11100')
        a = a.insert(a, 3)
        assert a == '0b1111110000'

    def test_overwrite(self):
        s = Bits.fromstring('0b01110')
        s = s.overwrite('0b000', 1)
        assert s == '0b00000'

    def test_prepend(self):
        s = Bits.zeros(1)
        t = s.prepend([1])
        assert s == [0]
        assert t == [1, 0]

    def test_rol(self):
        s = Bits.fromstring('0b0001')
        t = s.rol(1)
        assert s == '0b0001'
        assert t == '0b0010'

    def test_ror(self):
        s = Bits.fromstring('0b1000')
        t = s.ror(1)
        assert s == '0b1000'
        assert t == '0b0100'

@pytest.mark.skip(reason='not implemented')
class TestByteAligned:

    def test_not_byte_aligned(self):
        a = Bits.fromstring('0x00 ff 0f f')
        li = list(a.findall('0xff'))
        assert li == [8, 20]
        p = a.find('0x0f')[0]
        assert p == 4
        p = a.rfind('0xff')[0]
        assert p == 20
        a = a.replace('0xff', '')
        assert a == '0x000'

    def test_byte_aligned(self):
        bitformat.options.bytealigned = True
        a = Bits.fromstring('0x00 ff 0f f')
        li = list(a.findall('0xff'))
        assert li == [8]
        p = a.find('0x0f')[0]
        assert p == 16
        p = a.rfind('0xff')[0]
        assert p == 8
        a = a.replace('0xff', '')
        assert a == '0x000ff'
        bitformat.options.bytealigned = False



def test_copy_method():
    s = Bits.zeros(9)
    t = s.copy()
    assert s == t
    assert s is t


def test_adding():
    a = Bits.fromstring('0b0')
    b = Bits.fromstring('0b11')
    c = a + b
    assert c == '0b011'
    assert a == '0b0'
    assert b == '0b11'



class TestRepr:

    def test_standard_repr(self):
        a = Bits.fromstring('0o12345')
        assert repr(a) == "Bits('0b001010011100101')"


class TestNewProperties:


    def test_getter_length_errors(self):
        a = Bits.fromstring('0x123')
        with pytest.raises(bitformat.InterpretError):
            _ = a.f
        b = Bits()
        with pytest.raises(bitformat.InterpretError):
            _ = b.u

    @pytest.mark.skip(reason='not implemented')
    def test_unpack(self):
        a = Bits.fromstring('0xff160120')
        b = a.unpack('hex8, [u12; 2]')
        assert b == ['ff', [352, 288]]

    def test_bytes_properties(self):
        a = Bits.frombytes(b'hello')
        assert a.bytes == b'hello'

    def test_conversion_to_bytes(self):
        a = Bits.fromstring('0x41424344, 0b1')
        b = bytes(a)
        assert b == b'ABCD\x80'
        a = Bits()
        assert bytes(a) == b''


class TestBFloats:

    @pytest.mark.skip
    def test_creation(self):
        a = BitArray('bfloat=100.5')
        assert a.unpack('bfloat')[0] == 100.5
        b = BitArray(bfloat=20.25)
        assert b.bfloat == 20.25
        b.bfloat = -30.5
        assert b.bfloat == -30.5
        assert len(b) == 16
        fs = [0.0, -6.1, 1.52e35, 0.000001]
        a = bitstring.pack('4*bfloat', *fs)
        fsp = a.unpack('4*bfloat')
        assert len(a) == len(fs)*16
        for f, fp in zip(fs, fsp):
            assert f == pytest.approx(fp, abs=abs(f/100))
        a = BitArray(bfloat=13)
        assert a.bfloat == 13
        c = BitArray()
        with pytest.raises(ValueError):
            _ = c.bfloat

    @pytest.mark.skip
    def test_creation_errors(self):
        a = BitArray(bfloat=-0.25, length=16)
        assert len(a) == 16
        with pytest.raises(bitstring.CreationError):
            _ = BitArray(bfloat=10, length=15)
        with pytest.raises(bitstring.CreationError):
            _ = BitArray('bfloat:1=0.5')

    @pytest.mark.skip
    def test_little_endian(self):
        a = BitArray.fromstring('f32=1000')
        b = BitArray(bfloat=a.f)
        assert a[0:16] == b[0:16]

        a = BitArray('floatle:32=1000')
        b = BitArray(bfloatle=1000)
        assert a[16:32] == b
        assert b.bfloatle == 1000.0
        b.byteswap()
        assert b.bfloat == 1000.0
        assert b.bfloatbe == 1000.0

        with pytest.raises(bitstring.CreationError):
            _ = BitArray(bfloatle=-5, length=15)
        c = BitArray()
        with pytest.raises(bitstring.InterpretError):
            _ = c.bfloatle
        with pytest.raises(bitstring.InterpretError):
            _ = c.bfloatne

    @pytest.mark.skip
    def test_more_creation(self):
        a = BitArray('bfloat:16=1.0, bfloat16=2.0, bfloat=3.0')
        x, y, z = a.unpack('3*bfloat16')
        assert (x, y, z) == (1.0, 2.0, 3.0)

    def test_interpret_bug(self):
        a = Bits.ones(100)
        with pytest.raises(bitformat.InterpretError):
            _ = a.float

    def test_overflows(self):
        inf16 = Bits.build('f16', float('inf'))
        inf32 = Bits.fromstring('f32 = inf')
        inf64 = Dtype('f64').build(float('inf'))

        s = Bits.fromstring('f64 = 1e400')
        assert s == inf64
        s = Bits.fromstring('f32 = 1e60')
        assert s == inf32
        s = Bits.fromstring('f16 = 100000')
        assert s == inf16

        ninf16 = Dtype('f16').build(float('-inf'))
        ninf32 = Dtype('f32').build(float('-inf'))
        ninf64 = Dtype('f64').build(float('-inf'))

        assert ninf64 == Bits.fromstring('f64 = -1e400')
        assert ninf32 == Bits.fromstring('f32 = -1e60')
        assert ninf16 == Bits.fromstring('f16 = -100000')

    @pytest.mark.skip
    def test_big_endian_string_initialisers(self):
        a = BitArray('bfloatbe=4.5')
        b = BitArray('bfloatbe:16=-2.25')
        assert a.bfloatbe == 4.5
        assert b.bfloatbe == -2.25

    @pytest.mark.skip
    def test_litte_endian_string_initialisers(self):
        a = BitArray('bfloatle=4.5')
        b = BitArray('bfloatle:16=-2.25')
        assert a.bfloatle == 4.5
        assert b.bfloatle == -2.25

    @pytest.mark.skip
    def test_native_endian_string_initialisers(self):
        a = BitArray('bfloatne=4.5')
        b = BitArray('bfloatne:16=-2.25')
        assert a.bfloatne == 4.5
        assert b.bfloatne == -2.25


try:
    import numpy as np
    numpy_installed = True
except ImportError:
    numpy_installed = False


class TestNumpy:

    @pytest.mark.skipif(not numpy_installed, reason="numpy not installed.")
    def test_getting(self):
        a = BitArray('0b110')
        p = np.int_(1)
        assert a[p] is True
        p = np.short(0)
        assert a[p] is True

    @pytest.mark.skipif(not numpy_installed, reason="numpy not installed.")
    def test_setting(self):
        a = BitArray('0b110')
        p = np.int_(1)
        a[p] = '0b1111'
        assert a == '0b111110'

    @pytest.mark.skipif(not numpy_installed, reason="numpy not installed.")
    def test_creation(self):
        a = BitArray(np.longlong(12))
        assert a.hex == '000'


def test_bytes_from_list():
    s = Bits.build('bytes', [1, 2])
    assert s == '0x0102'
    s = Bits.frombytes(bytearray([1, 2]))
    assert s == '0x0102'
