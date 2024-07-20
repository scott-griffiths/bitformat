
import pytest
import sys
from bitformat import Dtype, Bits
from bitformat._dtypes import DtypeDefinition, dtype_register

sys.path.insert(0, '..')


class TestBasicFunctionality:

    def test_setting_bool(self):
        b = Dtype('bool')
        assert str(b) == 'bool'
        assert b.name == 'bool'
        assert b.length == 1

        b2 = Dtype.from_string('bool1')
        assert b == b2
        # self.assertTrue(b is b2)

    def test_setting_with_length(self):
        d = Dtype('uint', 12)
        assert str(d) == 'u12'
        assert d.length == 12
        assert d.name == 'u'

    def test_build_errors(self):
        dtype = Dtype.from_string('uint8')
        value = 'not_an_integer'
        with pytest.raises(ValueError):
            dtype.pack(value)

    def test_pack(self):
        dtype = Dtype.from_string('i88')
        x = dtype.pack(10001)
        assert x.i == 10001

    def test_unpack(self):
        dtype = Dtype.from_string('u12')
        x = dtype.unpack('0x3ff')
        assert x == 1023

    def test_immutability(self):
        d = Dtype.from_string('f32')
        with pytest.raises(AttributeError):
            d.length = 8
        with pytest.raises(AttributeError):
            d.name = 'uint8'

    def test_building_bits(self):
        d = Dtype.from_string('bits3')
        a = d.pack('0b101')
        assert a == '0b101'
        with pytest.raises(ValueError):
            d.pack('0b1010')

    def test_building_bin(self):
        d = Dtype.from_string('bin9')
        a = d.pack('0b000111000')
        assert a == '0b000111000'
        with pytest.raises(ValueError):
            d.pack('0b0001110000')

    def test_building_ints(self):
        d = Dtype.from_string('i3')
        a = d.pack(-3)
        assert a == '0b101'
        with pytest.raises(ValueError):
            d.pack(4)


class TestChangingTheRegister:

    def test_retrieving_meta_dtype(self):
        r = dtype_register
        u = r['uint']
        u2 = r['u']
        assert u == u2
        with pytest.raises(KeyError):
            i = r['integer']

    # def test_removing_type(self):
    #     del dtype_register['bool']
    #     with pytest.raises(KeyError):
    #         i = dtype_register['bool']
    #     with pytest.raises(KeyError):
    #         del dtype_register['penguin']


class TestCreatingNewDtypes:

    def test_new_alias(self):
        dtype_register.add_dtype_alias('bin', 'cat')
        a = Bits.from_string('0b110110')
        assert a.cat == '110110'
        a = Bits.pack('cat', '11110000')
        assert a.cat == '11110000'

    def test_new_type(self):
        md = DtypeDefinition('uint_r', Bits._setuint, Bits._getuint)
        dtype_register.add_dtype(md)
        a = Bits.from_string('0xf')
        assert a.uint_r == 15
        a = Bits.pack('uint_r4',  1)
        assert a == '0x1'
        a += 'uint_r100=0'
        assert a == '0x1, 0b' + '0'*100

    def test_new_type_with_getter(self):
        def get_fn(bs):
            return bs.count(1)
        md = DtypeDefinition('counter', None, get_fn)
        dtype_register.add_dtype(md)
        a = Bits.from_string('0x010f')
        assert a.counter == 5
        with pytest.raises(AttributeError):
            a.counter = 4

    def test_invalid_dtypes(self):
        with pytest.raises(TypeError):
            _ = Dtype()
        with pytest.raises(ValueError):
            _ = Dtype('float17')
