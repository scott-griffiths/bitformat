import pytest
from bitformat import Dtype, Bits, Field
from hypothesis import given, assume
import hypothesis.strategies as st


class TestCreation:
    def test_creation_from_dtype(self):
        ds = [Dtype.from_string(x) for x in ['u9', 'i4', 'f32', 'bytes3', 'bits11']]
        for d in ds:
            f = Field.from_parameters(d)
            assert f.dtype == d
            f2 = Field(str(d))
            assert f2.dtype == f.dtype

    @given(st.integers(0, 255))
    def test_creation_from_dtype_with_value(self, x):
        f = Field.from_parameters(Dtype.from_string('u8'), value=x)
        assert f.value == x
        f2 = Field(f'const u8 = {x}')
        assert f2.value == x


    def test_creation_from_bits(self):
        b = Bits('0xf, 0b1')
        f1 = Field.from_bits(b)
        assert f1.to_bits() == b
        assert f1.const is True
        with pytest.raises(ValueError):
            _ = Field(Bits())
        f2 = Field.from_bits(b'123')
        assert f2.value == b'123'
        b = f2.pack()
        assert b.to_bytes() == b'123'

    @given(name=st.text())
    def test_creation_with_names(self, name):
        assume(name != '')
        if name.isidentifier() and '__' not in name:
            f = Field.from_parameters('u8', name)
            assert f.name == name
            f2 = Field.from_string(f'{name}: u8')
            assert f2.name == name
            with pytest.raises(ValueError):
                _ = Field.from_parameters(f'{name}: u8', name=name)
        else:
            with pytest.raises(ValueError):
                _ = Field.from_parameters('u8', name)

    def test_creation_from_strings(self):
        f = Field.from_string(' flag_12 : bool')
        assert f.dtype.name == 'bool'
        assert f.name == 'flag_12'
        assert f.value is None
        f = Field.from_string('const u3 = 3')
        assert f.dtype.name == 'u'
        assert f.value == 3
        assert f.name == ''
        assert f.to_bits() == '0b011'

    @given(st.binary())
    def test_creation_from_bytes(self, b):
        f = Field.from_parameters('bytes', name='hello', value=b)
        assert f.value == b
        assert f.name == 'hello'
        assert f.dtype == Dtype('bytes')

        f = Field.from_bytes(b, name='hello')
        assert f.value == b
        assert f.name == 'hello'
        assert f.dtype == Dtype('bytes')


    @given(st.binary())
    def test_creation_from_bits(self, b):
        f = Field.from_bits(b, 'hello')
        assert f.value == b
        assert f.name == 'hello'
        assert f.dtype == Dtype('bits')

    def test_string_creation_with_const(self):
        f1 = Field.from_string('f1: u1 = 1')
        f2 = Field.from_string('f2: const u1 = 1')
        assert f1 == f2
        assert f2.const
        assert not f1.const
        f1.clear()
        f2.clear()
        temp = f1.build(0)
        assert temp == '0b0'
        assert f2.build() == '0b1'


class TestBuilding:

    @given(x=st.integers(0, 1023), name=st.text().filter(str.isidentifier))
    def test_building_with_keywords(self, x, name):
        assume('__' not in name)
        f = Field.from_string(f'{name} :u10')
        b = f.build([], **{name: x})
        assert b == Bits.from_string(f'u10={x}')

    def test_building_lots_of_types(self):
        f = Field('u4')
        b = f.build(15)
        assert b == '0xf'
        f = Field('i4')
        b = f.build(-8)
        assert b == '0x8'
        f = Field('bytes3')
        b = f.build(b'abc')
        assert b == '0x616263'
        f = Field('bits11')
        with pytest.raises(ValueError):
            _ = f.build(Bits.from_string('0x7ff'))
        b = f.build(Bits.from_string('0b111, 0xff'))
        assert b == '0b11111111111'

    def test_building_with_const(self):
        f = Field.from_string('  const  u4 =8')
        b = f.build()
        assert b == '0x8'
        f.clear()
        b = f.build()
        assert b == '0x8'
        f.const = False
        assert f.value == 8
        f.clear()
        assert f.value is None

def test_field_str():
    f = Field.from_parameters('u8', name='x')
    assert str(f) == 'x: u8'
    f = Field('u8')
    assert str(f) == 'u8'
    f = Field.from_parameters('uint8', value=8)
    assert str(f) == 'u8 = 8'
    f = Field.from_parameters('u8', value=8, name='x')
    assert str(f) == 'x: u8 = 8'


def test_field_array():
    f = Field.from_string('[u8; 3]')
    assert f.dtype == Dtype.from_string('[u8; 3]')
    assert f.dtype.items == 3
    b = f.build([1, 2, 3])
    assert b == '0x010203'
    assert type(b) is Bits
    f.clear()
    assert f.value is None
    v = f.parse(b)
    assert f.value == (1, 2, 3)
    assert v == 24


def test_field_array_issues():
    with pytest.raises(ValueError):
        _ = Field.from_string('[u; 3]')
    with pytest.raises(ValueError):
        _ = Field('f')
    f = Field.from_string('[bool; 10]')
    assert len(f) == 10


def test_setting_dtype():
    f = Field.from_bits('0x0102')
    f.dtype = '[u8; 2]'
    assert f.value == (1, 2)


def test_creation():
    f = Field('u8 = 12')
    assert f.value == 12
    assert f.const is False
    f2 = Field('const u8 = 12')
    assert f2.const is True
