#!/usr/bin/env python

from bitformat import Format, Dtype, Bits, Field, Array
from hypothesis import given
import pytest
import hypothesis.strategies as st
import random


class TestCreation:

    def test_create_empty(self):
        f = Format()
        b = f.build([])
        assert len(b) == 0
        assert f.name == ''

    def test_create_from_dtype(self):
        d = Dtype.from_string('u12')
        f = Format([Field.from_parameters(d)], 'x')
        x = f.build([1000])
        assert f.name == 'x'
        assert x == 'u12=1000'
        assert len(x) == 12

    def test_create_from_bits_string(self):
        f = Format([Field.from_parameters('float16', 'foo', 12.5)], 'x')
        g = Format(['foo: float16=12.5'], 'y')
        assert f.to_bits() == g.to_bits()
        assert f.name == 'x'

    def test_create_from_dtype_string(self):
        f = Format(['float16'], 'x')
        assert f.fieldtypes[0].name == ''
        assert f.fieldtypes[0].dtype == Dtype.from_parameters('float', 16)

    @given(name=st.sampled_from(['float16', 'u12', 'bool', 'float64']))
    def test_building_field(self, name):
        f = Field(name)
        b = f.build(0)
        assert b == Bits.from_string(f'{name}=0')

    def test_create_from_bits(self):
        b = Bits.from_string('0xabc')
        f = Format([Field.from_bits(b)])
        x = f.build([])
        assert f.name == ''
        assert x == '0xabc'
        assert isinstance(x, Bits)

    def test_create_from_bits_with_name(self):
        f = Format([Field.from_bits('0xabc', 'some_bits')])
        x = f.build([])
        assert x, '0xabc'

    def test_create_from_list(self):
        f = Format(['const bits = 0xabc', 'u5', 'u5'])
        x = f.build([3, 10])
        assert x == 'bits = 0xabc, u5=3, u5=10'
        f.parse(x)
        assert isinstance(f, Format)

    def testComplicatedCreation(self):
        f = Format(['const bits = 0x000001b3', 'u12', 'height:const u12  = 288', 'flag: const bool  =True'], 'header')
        assert f.name == 'header'
        b = f.build([352])
        assert b == '0x000001b3, u12=352, u12=288, 0b1'
        f2 = Format([f, 'bytes5'], 'main')
        f3 = f2.build([[352], b'12345'])
        assert f3 == Bits.from_string('0x000001b3, u12=352, u12=288, 0b1') + b'12345'

    def test_nested_formats(self):
        header = Format(['bits = 0x000001b3', 'width:u12', 'height:u12', 'f1:bool', 'f2:bool'], 'header')
        main = Format(['bits = 0b1', 'v1:i7', 'v2:i9'], 'main')
        f = Format([header, main, 'bits = 0x47'], 'all')
        b = Bits.from_string('bits = 0x000001b3, u12=100, u12=200, bits = 0b1, bits = 0b0, bits = 0b1, i7=5, i9=-99, bits = 0x47')
        f.parse(b)
        t = f['header']
        assert t['width'].value == 100
        assert f['header']['width'].value == 100
        assert f['main']['v2'].value == -99

    # def test_format_in_itself(self):
    #     f = Format(['x:u8'])
    #     g = Format(['y:u8'])
    #     f += g
    #     b = f.build([10, 20])
    #     # b = f.build(Bits('0x1234'))
    #     f.clear()
    #     f.parse(b)
    #     assert f.value == [10, [20]]

@pytest.mark.skip
def test_building():
    f1 = Field('u8')
    f1.build(9)
    assert f1.value == 9

    f2 = Field('[u8; 3]')
    f2.build([1, 2, 3])
    assert f2.value == (1, 2, 3)

    f3 = Format(['u8'])
    f3.build([4])
    assert f3.value == [4]

    f4 = Format(['[u8; 3]'])
    f4.build([[1, 2, 3]])
    assert f4.value == [(1, 2, 3)]

    f5 = Format(['u8', '[u8; 3]'])
    f5.build([4, [1, 2, 3]])
    assert f5.value == [4, (1, 2, 3)]

    f6 = Format(['u8', '[u8; 3]', 'u8'])
    f6.build([4, [1, 2, 3], 5])
    assert f6.value == [4, (1, 2, 3), 5]

    f7 = Format([f1, f2])
    f7.build([6, [4, 5, 6]])
    assert f7.value == [6, (4, 5, 6)]

    f8 = Format([f1, f7])
    f8.build([7, [8, [9, 10, 11]]])
    assert f8.value == [7, (8, (9, 10, 11))]


class TestAddition:

    def test_adding_bits(self):
        f = Format()
        f += Field.from_bits('0xff')
        assert f.to_bytes() == b'\xff'
        f += Field.from_string('penguin:i9 =-8')
        x = f['penguin']
        assert x.value == -8
        f['penguin'].value += 6
        assert f['penguin'].value == -2


class TestArray:

    def test_simple_array(self):
        array_field = Field.from_parameters('[u8; 20]', 'my_array')
        f = Format([array_field], 'a')
        assert f.fieldtypes[0].dtype.items == 20
        a = f.build([list(range(20))])

        f2 = Format(['new_array: [u8;20]'], 'b')
        assert f2.fieldtypes[0].dtype.items == 20
        assert f2.fieldtypes[0].value is None
        f2['new_array'] = a
        assert a == f2.to_bits()

    @pytest.mark.skip
    @given(w=st.integers(1, 5), h=st.integers(1, 5))
    def test_example_with_array(self, w, h):
        f = Format([
                   Field('bytes', 'signature', b'BMP', const=True),
                   'width: i8',
                   'height: i8',
                   'pixels: [u8 ; {width * height}]',
                   ], 'construct_example')
        # TODO: This should be chosen by hypothesis to make it repeatable.
        p = [random.randint(0, 255) for _ in range(w * h)]
        b = f.build([w, h, p])
        f.clear()
        f.parse(b)
        assert f['width'].value == w
        assert f['height'].value == h
        assert f['pixels'].value == p

@pytest.mark.skip
def test_example_from_docs():
    f = Format(['x: u8', 'y: u{x}'])
    b = Bits.from_string('u8=10, u10=987')
    f.parse(b)
    assert f['y'].value == 987

    f = Format(['sync_byte: const hex8 = 0xff',
                'items: u16',
                'flags: [bool ; {items + 1} ] ',
                Repeat('{items + 1}', [
                    'byte_cluster_size: u4',
                    'bytes{byte_cluster_size}'
                ]),
                'u8'
                ])
    f.build([1, b'1', 2, b'22', 3, b'333', 12], items=2, flags=[True, False, True])

@pytest.mark.skip
def test_creating_with_keyword_value():
    f = Format(['x: u10', 'u10={2*x}'])
    b = f.build([6])
    assert b == 'u10=6, u10=12'

@pytest.mark.skip
def test_items():
    f = Format(['q:i5', '[u3; {q + 1}]'])
    b = Bits.from_string('i5=1, u3=2, u3=0')
    f.parse(b)
    assert f[0].value == 1
    assert f[1].value == [2, 0]
    f.clear()
    b2 = f.build([1, [2, 0]])
    assert b2 == b
    f.clear()
    b3 = f.build([3, [1, 2, 3, 4]])
    assert b3 == Bits.from_string('i5=3, u3=1, u3=2, u3=3, u3=4')


class TestMethods:

    def test_clear(self):
        f = Format(['const bits = 0x000001b3', 'u12', 'height:u12', '  flag : bool '], 'header')
        f['height'].value = 288
        f.clear()
        g = Format(['bits = 0x000001b3', 'u12', 'u12', 'bool'], 'empty_header')
        assert f == g

    def test_get_item(self):
        f = Format(['float16=7', 'bool', 'bytes5', 'pop :u100  = 144'])
        assert f[0].value == 7
        assert f[1].value is None
        assert f['pop'].value == 144

    def test_set_item(self):
        f = Format(['const f16=7', 'bool', 'bytes5', 'pop : u100 = 144'])
        f[0] = 2  # TODO: Should this be allowed?
        assert f[0].value == 2
        f[0] = None
        assert f[0].value is None
        f['pop'] = 999999
        assert f['pop'].value == 999999

@pytest.mark.skip
def test_repeating_field():
    f = Repeat(5, 'u8')
    d = Array('u8', [1, 5, 9, 7, 6]).data
    f.unpack(d)
    assert f.value == [1, 5, 9, 7, 6]

@pytest.mark.skip
def test_find_field():
    b = Bits('0x1234000001b3160120')
    f = Format([
            Find('0x000001'),
            'start_code: hex32 = 000001b3',
            'width: u12',
            'height: u12'
        ])
    f.parse(b)
    assert f['width'].value == 352
    f.clear()
    assert f['width'].value is None
    f.build([352, 288])
    assert f.to_bits() == '0x000001b3160120'

@pytest.mark.skip
def test_format_repr_and_str():
    f = Format(['u8 <s>', Repeat('s + 1', Format(['u12 <width>', 'u12 <height>', Repeat('width * height', 'u8', 'data')])), 'hex <eof> = 123'], 'my_format')
    s = str(f)
    r = repr(f)
    assert 'my_format' in s
    print(s)
    print(r)
    assert 'my_format' in r

def test_format_get_and_set():
    f = Format(['u8', 'u8', 'u8'])
    for field in f:
        field.value = 12
    assert f.value == [12, 12, 12]
    f[0].value = 0
    assert f.value == [0, 12, 12]
    g = f[:]
    assert g.value == [0, 12, 12]
    f[-1].value = 7
    assert g[-1].value == 12

@pytest.mark.skip

def test_repeating_from_expression():
    f = Format([
        'x: u8',
        Repeat('{2*x}', 'hex4')
    ], 'my_little_format')
    b = f.build([2, ['a', 'b', 'c', 'd']])
    assert b.parse('hex') == '02abcd'

@pytest.mark.skip

def test_repeat_with_const_expression():
    f = Format(['the_size: i9',
                Repeat('{the_size}', [
                    'const u5=0',
                    'const bin3=111'
                ])])
    f.build([3])
    assert f.to_bits() == 'i9=3, 0x070707'

@pytest.mark.skip

def test_repeat_with_bits():
    f = Repeat(3, '0xab')
    b = f.pack()
    assert b == '0xababab'
    f2 = Repeat(2, b)
    b2 = f2.pack()
    assert b2 == '0xabababababab'

@pytest.mark.skip
def test_repeat_with_dtype():
    f = Repeat(4, Dtype.from_string('i4'))
    b = f.pack([1, 2, 3, 4])
    f.unpack(b)
    assert f.value == [1, 2, 3, 4]

    f = Repeat(4, Dtype.from_string('i40'))
    b = f.pack([-400, 200, -200, 400])
    f.unpack(b)
    assert f.value == [-400, 200, -200, 400]

def test_field_array_str():
    f = Field.from_string('test   :  f32 = 0.25  ')
    assert str(f) == 'test: f32 = 0.25'
    f = Field.from_string('test: [f32 ; 3]')
    assert str(f) == 'test: [f32; 3]'

def test_format_repr_string():
    f = Format(['x:const u8 = 12', 'u:bool = False', '[u3;44]'], 'dave')
    r = repr(f)
    assert r == "Format([\n    'x: const u8 = 12',\n    'u: bool = False',\n    '[u3; 44]'\n], 'dave')"

def test_to_bits():
    f = Format(['u8', 'u8', 'u8'])
    f.build([1, 2, 3])
    b = f.to_bits()
    assert b == 'u8=1, u8=2, u8=3'
    f[1].clear()
    assert f[0].value == 1
    assert f[1].value is None
    assert f[2].value == 3
    assert f.value == [1, None, 3]
    assert f[0].to_bits() == 'u8=1'
    with pytest.raises(ValueError):
        _ = f[1].to_bits()
    with pytest.raises(ValueError):
        _ = f.to_bits()

def test_partial_parse():
    f = Format(['bool',
                '[f16;3]'])
    b = Bits.from_string('0b1, f16=1.0, f16=2.0, f16=3.0')
    f.parse(b)
    assert f[0].value == True
    assert f[1].value == (1.0, 2.0, 3.0)
    f.clear()
    with pytest.raises(ValueError):
        _ = f.parse(b[:-16])
