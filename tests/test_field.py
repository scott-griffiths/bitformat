import pytest
from bitformat import Dtype, Bits, Field
from hypothesis import given, assume
import hypothesis.strategies as st


class TestCreation:
    def test_creation_from_dtype(self):
        ds = [Dtype('u9'), Dtype('i', 4), Dtype('f32'), Dtype('bytes3'), Dtype('bits11')]
        for d in ds:
            f = Field(d)
            assert f.dtype == d
            f2 = Field(str(d))
            assert f2.dtype == f.dtype

        without_length = [Dtype('bytes'), Dtype('int')]
        for b in without_length:
            f = Field(b)
            assert f.dtype.length is None

    @given(st.integers(0, 255))
    def test_creation_from_dtype_with_value(self, x):
        f = Field(Dtype('u8'), value=x)
        assert f.value == x
        f2 = Field.fromstring(f'const u8 = {x}')
        assert f2.value == x


    def test_creation_from_bits(self):
        b = Bits('0xf, 0b1')
        f1 = Field.frombits(b)
        assert f1.tobits() == b
        assert f1.const == True
        with pytest.raises(ValueError):
            _ = Field(Bits())
        f2 = Field.frombits(b'123')
        assert f2.value == b'123'
        b = f2.build()
        assert b.tobytes() == b'123'

    @given(name=st.text())
    def test_creation_with_names(self, name):
        assume(name != '')
        if name.isidentifier() and '__' not in name:
            f = Field('u8', name)
            assert f.name == name
            f2 = Field.fromstring(f'{name}: u8')
            assert f2.name == name
            with pytest.raises(ValueError):
                _ = Field(f'{name}: u8', name=name)
        else:
            with pytest.raises(ValueError):
                _ = Field('u8', name)

    def test_creation_from_strings(self):
        f = Field.fromstring(' flag_12 : bool')
        assert f.dtype.name == 'bool'
        assert f.name == 'flag_12'
        assert f.value is None
        f = Field.fromstring('const u3 = 3')
        assert f.dtype.name == 'u'
        assert f.value == 3
        assert f.name == ''
        assert f.tobits() == '0b011'

    @given(st.binary())
    def test_creation_from_bytes(self, b):
        f = Field('bytes', name='hello', value=b)
        assert f.value == b
        assert f.name == 'hello'
        assert f.dtype == Dtype('bytes')

        f = Field.frombytes(b, name='hello')
        assert f.value == b
        assert f.name == 'hello'
        assert f.dtype == Dtype('bytes')


    @given(st.binary())
    def test_creation_from_bits(self, b):
        f = Field.frombits(b, 'hello')
        assert f.value == b
        assert f.name == 'hello'
        assert f.dtype == Dtype('bits')

    def test_string_creation_with_const(self):
        f1 = Field.fromstring('f1: u1 = 1')
        f2 = Field.fromstring('f2: const u1 = 1')
        assert f1 == f2
        assert f2.const
        assert not f1.const
        f1.clear()
        f2.clear()
        temp = f1.build([0])
        assert temp == '0b0'
        assert f2.build([]) == '0b1'


class TestBuilding:

    @given(x=st.integers(0, 1023), name=st.text().filter(str.isidentifier))
    def test_building_with_keywords(self, x, name):
        assume('__' not in name)
        f = Field.fromstring(f'{name} :u10')
        b = f.build([], **{name: x})
        assert b == Bits.fromstring(f'u10={x}')

    def test_building_lots_of_types(self):
        f = Field('u4')
        b = f.build([15])
        assert b == '0xf'
        f = Field('i4')
        b = f.build([-8])
        assert b == '0x8'
        f = Field('bytes:3')
        b = f.build([b'abc'])
        assert b == '0x616263'
        f = Field('bits11')
        with pytest.raises(ValueError):
            _ = f.build([Bits.fromstring('0x7ff')])
        b = f.build([Bits.fromstring('0b111, 0xff')])
        assert b == '0b11111111111'

    def test_building_with_const(self):
        f = Field.fromstring('  const  u4 =8')
        b = f.build([])
        assert b == '0x8'
        f.clear()
        b = f.build([])
        assert b == '0x8'
        f.const = False
        assert f.value == 8
        f.clear()
        assert f.value is None


def test_field_str():
    f = Field('u8', name='x')
    assert str(f) == 'x: u8'
    f = Field('u8')
    assert str(f) == 'u8'
    f = Field('uint8', value=8)
    assert str(f) == 'u8 = 8'
    f = Field('u8', value=8, name='x')
    assert str(f) == 'x: u8 = 8'
