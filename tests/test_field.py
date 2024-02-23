import pytest
from bitformat import Dtype, Bits, Field
from hypothesis import given, assume
import hypothesis.strategies as st


class TestCreation:
    def test_creation_from_dtype(self):
        ds = [Dtype('u9'), Dtype('i', 4), Dtype('e4m3float'), Dtype('bytes:3'), Dtype('sie'), Dtype('bits11')]
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
        f2 = Field.fromstring(f'u8 = {x}')
        assert f2.value == x


    def test_creation_from_bits(self):
        b = Bits('0xf, 0b1')
        f1 = Field.frombits(b)
        assert f1.bits() == b
        assert f1.const == True
        with pytest.raises(ValueError):
            _ = Field(Bits())
        f2 = Field.frombits(b'123')
        assert f2.value == b'123'
        b = f2.build()
        assert b.tobytes() == b'123'

    def test_creation_with_names(self):
        good = ['self', 'three3', '_why_', 'a_b_c', 'a1', 'a_1', 'a_1_2', 'a_1_2_3']
        bad = ['thi<s', '[hello]', 'a b', 'a-b', 'a.b', 'a b c']
        for name in good:
            f = Field('u8', name)
            assert f.name == name
            f2 = Field.fromstring(f'u8<{name}>')
            assert f2.name == name

        for name in bad:
            with pytest.raises(ValueError):
                _ = Field('u8', name)

        for n in good:
            with pytest.raises(ValueError):
                _ = Field(f'u8 <{n}>', n)

    def test_creation_from_strings(self):
        f = Field.fromstring('bool < flag_12 > ')
        assert f.dtype.name == 'bool'
        assert f.name == 'flag_12'
        assert f.value is None
        f = Field.fromstring('ue = 2')
        assert f.dtype.name == 'ue'
        assert f.value == 2
        assert f.bits() == '0b011'
        f = Field('bytes', name='hello', value=b'hello world!')
        assert f.value == b'hello world!'
        assert f.name == 'hello'
        assert f.dtype == Dtype('bytes')

    def test_string_creation_with_const(self):
        f1 = Field.fromstring('u1 <f1> : 1')
        f2 = Field.fromstring('u1 <f2> = 1')
        assert f1 == f2
        assert f2.const
        assert not f1.const
        f1.clear()
        f2.clear()
        assert f1.build([0]) == '0b0'
        assert f2.build([]) == '0b1'

class TestBuilding:

    @given(x=st.integers(0, 1023), name=st.text().filter(str.isidentifier))
    def test_building_with_keywords(self, x, name):
        assume('__' not in name)
        f = Field.fromstring(f'u10 <{name}>')
        b = f.build([], {name: x})
        assert b == Bits(f'u10={x}')

    def test_building_lots_of_types(self):
        f = Field('u4')
        b = f.build([15])
        assert b == '0xf'
        f = Field('i4')
        b = f.build([-8])
        assert b == '0x8'
        f = Field('e4m3float')
        b = f.build([0.5])
        assert b == '0x38'
        f = Field('bytes:3')
        b = f.build([b'abc'])
        assert b == '0x616263'
        f = Field('se')
        b = f.build([-5])
        assert b == '0b0001011'
        # f = Field('bits11')
        # with self.assertRaises(ValueError):
        #     _ = f.build([Bits('0x7ff')])
        # b = f.build([Bits('0b111, 0xff')])

    def test_building_with_const(self):
        f = Field.fromstring('u4 =8')
        b = f.build([])
        assert b == '0x8'
        f.clear()
        b = f.build([])
        assert b == '0x8'
        f.const = False
        assert f.value == 8
        f.clear()
        assert f.value is None
