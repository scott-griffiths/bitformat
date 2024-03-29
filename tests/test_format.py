#!/usr/bin/env python

from bitformat import Format, Dtype, Bits, Field, Array, Repeat, Find, FieldArray
from hypothesis import given, assume
import hypothesis.strategies as st
import random


class TestCreation:

    def test_create_empty(self):
        f = Format()
        b = f.build([])
        assert len(b) == 0
        assert f.name == ''

    def test_create_from_dtype(self):
        d = Dtype('u12')
        f = Format([Field(d)], 'x')
        x = f.build([1000])
        assert f.name == 'x'
        assert x == 'uint:12=1000'
        assert len(x) == 12

    def test_create_from_bits_string(self):
        f = Format([Field('float16', 'foo', 12.5)], 'x')
        g = Format(['float16 <foo> =12.5'], 'y')
        assert f.tobits() == g.tobits()
        assert f.name == 'x'

    def test_create_from_dtype_string(self):
        f = Format(['float16'], 'x')
        assert f.fieldtypes[0].name == ''
        assert f.fieldtypes[0].dtype == Dtype('float', 16)

    @given(name=st.sampled_from(['float16', 'u12', 'bool', 'e4m3float', 'float64']))
    def test_building_field(self, name):
        f = Field(name)
        b = f.build([0])
        assert b == Bits(f'{name}=0')

    def test_create_from_bits(self):
        b = Bits('0xabc')
        f = Format([Field.frombits(b)])
        x = f.build([])
        assert f.name == ''
        assert x == '0xabc'
        assert isinstance(x, Bits)

    def test_create_from_bits_with_name(self):
        f = Format([Field.frombits('0xabc', 'some_bits')])
        x = f.build([])
        assert x, '0xabc'

    def test_create_from_list(self):
        f = Format(['0xabc', 'u5', 'u5'])
        x = f.build([3, 10])
        assert x == '0xabc, u5=3, u5=10'
        f.parse(x)
        assert isinstance(f, Format)

    def testComplicatedCreation(self):
        f = Format(['0x000001b3', 'u12', 'u12 <height> = 288', 'bool <flag> =True'], 'header')
        assert f.name == 'header'
        b = f.build([352])
        assert b == '0x000001b3, u12=352, u12=288, 0b1'
        f2 = Format([f, 'bytes5'], 'main')
        f3 = f2.build([352, b'12345'])
        assert f3 == Bits('0x000001b3, u12=352, u12=288, 0b1') + b'12345'

    def test_nested_formats(self):
        header = Format(['0x000001b3', 'u12<width>', 'u12<height>', 'bool<f1>', 'bool<f2>'], 'header')
        main = Format(['0b1', 'i7<v1>', 'i9<v2>'], 'main')
        f = Format([header, main, '0x47'], 'all')
        b = Bits('0x000001b3, u12=100, u12=200, 0b1, 0b0, 0b1, i7=5, i9=-99, 0x47')
        f.parse(b)
        t = f['header']
        assert t['width'].value == 100
        assert f['header']['width'].value == 100
        assert f['main']['v2'].value == -99

    def test_format_in_itself(self):
        f = Format(['u8 <x>'])
        f += f
        b = f.build([10, 20])
        f.clear()
        f.parse(b)
        assert f.value == [10, [20]]


class TestAddition:

    def test_adding_bits(self):
        f = Format()
        f += Field.frombits('0xff')
        assert f.tobytes() == b'\xff'
        f += Field.fromstring('i9<penguin> =-8')
        x = f['penguin']
        assert x.value == -8
        f['penguin'].value += 6
        assert f['penguin'].value == -2


class TestArray:

    def test_simple_array(self):
        array_field = FieldArray('u8', 20, 'my_array')
        f = Format([array_field], 'a')
        assert f.fieldtypes[0].items == 20
        a = f.build([[*range(20)]])

        f2 = Format(['u8*20 <new_array>'], 'b')
        assert f2.fieldtypes[0].items == 20
        assert f2.fieldtypes[0].value is None
        f2['new_array'] = a
        assert a == f2.tobits()

    @given(w=st.integers(1, 5), h=st.integers(1, 5))
    def test_example_with_array(self, w, h):
        f = Format([
                   Field('bytes', 'signature', b'BMP'),
                   'i8 <width>',
                   'i8 <height>',
                   'u8 * {width * height} <pixels>',
                   ], 'construct_example')
        # TODO: This should be chosen by hypothesis to make it repeatable.
        p = [random.randint(0, 255) for _ in range(w * h)]
        b = f.build([w, h, p])
        f.parse(b)
        assert f['width'].value == w
        assert f['height'].value == h
        assert f['pixels'].value == p
        # self.assertEqual(type(f['pixels'].value), list)


class TestExpressions:

    def test_example_from_docs(self):

        f = Format(['u8 <x>', 'u{x} <y>'])
        b = Bits('u8=10, u10=987')
        f.parse(b)
        assert f['y'].value == 987

        f = Format(['hex8 <sync_byte> = 0xff',
                    'u16 <items>',
                    'bool * {items + 1} <flags>',
                    Repeat('{items + 1}', Format([
                        'u4 <byte_cluster_size>',
                        'bytes{byte_cluster_size}'
                    ]), 'clusters'),
                    'u8 = {clusters[0][0] << 4}'
                    ])
        # b = Bits('0xff, u16=2, 0b111, u4=1, 0x01, u4=2, 0x0203, u4=5, 0x0405060708, u8=16')
        # f.parse(b)
        # self.assertEqual(f['items'].value, 2)
        # self.assertEqual(f['flags'].value, [1, 1, 1])


    def test_creating_with_keyword_value(self):
        f = Format(['u10 <x>', 'u10={2*x}'])
        b = f.build([6])
        assert b == 'u10=6, u10=12'


    def test_items(self):
        f = Format(['i5 <q>', 'u3 * {q + 1}'])
        b = Bits('i5=1, u3=2, u3=0')
        f.parse(b)
        assert f[0].value == 1
        assert f[1].value == [2, 0]
        f.clear()
        b2 = f.build([1, [2, 0]])
        assert b2 == b
        f.clear()
        b3 = f.build([3, [1, 2, 3, 4]])
        assert b3 == Bits('i5=3, u3=1, u3=2, u3=3, u3=4')


class TestMethods:

    def test_clear(self):
        f = Format(['0x000001b3', 'u12', 'u12 <height>', 'bool <flag>'], 'header')
        f['height'].value = 288
        f.clear()
        g = Format(['0x000001b3', 'u12', 'u12', 'bool'], 'empty_header')
        assert f == g

    def test_get_item(self):
        f = Format(['float16=7', 'bool', 'bytes5', 'u100 <pop> = 144'])
        assert f[0].value == 7
        assert f[1].value is None
        assert f['pop'].value == 144

    def test_set_item(self):
        f = Format(['float16=7', 'bool', 'bytes5', 'u100 <pop> = 144'])
        f[0] = 2
        assert f[0].value == 2
        f[0] = None
        assert f[0].value is None
        f['pop'] = 999999
        assert f['pop'].value == 999999


class TestRepeater:

    def test_repeating_field(self):
        f = Format([
                Repeat(5, 'u8')
        ])
        f.parse(Array('u8', [1, 5, 9, 7, 6]).data)
        assert f.value == [[1, 5, 9, 7, 6]]


class TestFinder:

    def test_find_field(self):
        b = Bits('0x1234000001b3160120')
        f = Format([
                Find('0x000001'),
                'hex32 <start_code> = 000001b3',
                'u12 <width>',
                'u12 <height>'
            ])
        f.parse(b)
        assert f['width'].value == 352
        f.clear()
        assert f['width'].value is None
        f.build([352, 288])
        assert f.tobits() == '0x000001b3160120'
