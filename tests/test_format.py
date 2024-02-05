#!/usr/bin/env python
import unittest
from bitformat import Format, Dtype, Bits, Field, Array, Repeat, Find
import bitformat

def setUpModule():
    bitformat.format.colour = bitformat.format.Colour(False)

class Creation(unittest.TestCase):

    def testCreateEmpty(self):
        f = Format()
        b = f.build([])
        self.assertEqual(len(b), 0)
        self.assertEqual(f.name, '')

    def testCreateFromDtype(self):
        d = Dtype('u12')
        f = Format([Field(d)], 'x')
        x = f.build([1000])
        self.assertEqual(f.name, 'x')
        self.assertEqual(x, 'uint:12=1000')
        self.assertEqual(len(x), 12)

    def testCreateFromBitsString(self):
        f = Format([Field('float16', 'foo', 12.5)], 'x')
        g = Format(['float16 <foo> =12.5'], 'y')
        self.assertEqual(f.bits(), g.bits())
        self.assertEqual(f.name, 'x')

    def testCreateFromDtypeString(self):
        f = Format(['float16'], 'x')
        self.assertEqual(f.fieldtypes[0].name, '')
        self.assertEqual(f.fieldtypes[0].dtype, Dtype('float', 16))

    def testBuildingField(self):
        f = Field('float16')
        b = f.build([0.0])
        self.assertEqual(b, '0x0000')

    def testCreateFromBits(self):
        b = Bits('0xabc')
        f = Format([Field(b)])
        x = f.build([])
        self.assertEqual(f.name, '')
        self.assertEqual(x, '0xabc')
        self.assertTrue(isinstance(x, Bits))

    def testCreateFromBitsWithName(self):
        f = Format([Field('0xabc', 'some_bits')])
        x = f.build([])
        self.assertTrue(x, '0xabc')

    def testCreateFromList(self):
        f = Format([Bits('0xabc'), Dtype('u5'), Dtype('u5')])
        x = f.build([3, 10])
        self.assertEqual(x, '0xabc, u5=3, u5=10')
        f.parse(x)
        self.assertTrue(isinstance(f, Format))

    def testComplicatedCreation(self):
        f = Format(['0x000001b3', 'u12', 'u12 <height> = 288', 'bool <flag> =True'], 'header')
        self.assertEqual(f.name, 'header')
        b = f.build([352])
        self.assertEqual(b, '0x000001b3, u12=352, u12=288, 0b1')
        f2 = Format([f, 'bytes5'], 'main')
        f3 = f2.build([b'12345'])
        self.assertEqual(f3, Bits('0x000001b3, u12=352, u12=288, 0b1') + b'12345')

    def testNestedFormats(self):
        header = Format(['0x000001b3', 'u12<width>', 'u12<height>', 'bool<f1>', 'bool<f2>'], 'header')
        main = Format(['0b1', 'i7<v1>', 'i9<v2>'], 'main')
        f = Format([header, main, '0x47'], 'all')
        b = Bits('0x000001b3, u12=100, u12=200, 0b1, 0b0, 0b1, i7=5, i9=-99, 0x47')
        f.parse(b)
        t = f['header']
        self.assertEqual(t['width'].value, 100)
        self.assertEqual(f['header']['width'].value, 100)
        self.assertEqual(f['main']['v2'].value, -99)

class Addition(unittest.TestCase):

    def testAddingBits(self):
        f = Format()
        f += '0xff'
        self.assertEqual(f.bytes(), b'\xff')
        f += 'i9<penguin> =-8'
        x = f['penguin']
        self.assertEqual(x.value, -8)
        f['penguin'].value += 6
        self.assertEqual(f['penguin'].value, -2)


class ArrayTests(unittest.TestCase):

    def testSimpleArray(self):
        array_field = Field('u8', 'my_array', items=20)
        f = Format([array_field], 'a')
        self.assertEqual(f.fieldtypes[0].items, 20)
        a = f.build([*range(20)])

        f2 = Format(['u8*20 <new_array>'], 'b')
        self.assertEqual(f2.fieldtypes[0].items, 20)
        self.assertEqual(f2.fieldtypes[0].value, None)
        f2['new_array'] = a
        self.assertEqual(a, f2.bits())


    # def testExampleWithArray(self):
    #     f = Format('construct_example', [
    #                Field('bytes', 'signature', b'BMP'),
    #                'i8 <width>',
    #                'i8 <height>',
    #                'u8 * {width * height} <pixels>',
    #                ])
    #     b = f.build(3, 2, [7, 8, 9, 11, 12, 13])
    #     v = b'BMP\x03\x02\x07\x08\t\x0b\x0c\r'
    #     self.assertEqual(b.tobytes(), v)
    #     f.parse(Bits(v))
    #     self.assertEqual(f['width'], 3)
    #     self.assertEqual(f['height'], 2)
    #     self.assertEqual(f['pixels'],[7, 8, 9, 11, 12, 13])
    #     # self.assertEqual(type(f['pixels']), list)


class Methods(unittest.TestCase):

    def testClear(self):
        f = Format(['0x000001b3', 'u12', 'u12 <height>', 'bool <flag>'], 'header')
        f['height'].value = 288
        f.clear()
        g = Format(['0x000001b3', 'u12', 'u12', 'bool'], 'empty_header')
        self.assertEqual(f, g)

    def testGetItem(self):
        f = Format(['float16=7', 'bool', 'bytes5', 'u100 <pop> = 144'])
        self.assertEqual(f[0].value, 7)
        self.assertEqual(f[1].value, None)
        self.assertEqual(f['pop'].value, 144)

    def testSetItem(self):
        f = Format(['float16=7', 'bool', 'bytes5', 'u100 <pop> = 144'])
        f[0] = 2
        self.assertEqual(f[0].value, 2)
        f[0] = None
        self.assertEqual(f[0].value, None)
        f['pop'] = 999999
        self.assertEqual(f['pop'].value, 999999)


class Repeater(unittest.TestCase):

    def testRepeatingField(self):
        f = Format([
                Repeat(5, 'u8')
        ])
        f.parse(Array('u8', [1, 5, 9, 7, 6]).data)
        self.assertEqual(f.value, [[1, 5, 9, 7, 6]])


class Finder(unittest.TestCase):

    def testFindField(self):
        b = Bits('0x1234000001b3160120')
        f = Format([
                Find('0x000001'),
                'hex32 <start_code> = 000001b3',
                'u12 <width>',
                'u12 <height>'
            ])
        f.parse(b)
        self.assertEqual(f['width'].value, 352)
        f.clear()
        self.assertEqual(f['width'].value, None)
        f.build([352, 288])