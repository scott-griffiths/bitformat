#!/usr/bin/env python
import unittest
from bitformat import Format, Dtype, Bits, Field, Array
import bitformat

def setUpModule():
    bitformat.format.colour = bitformat.format.Colour(False)

class Creation(unittest.TestCase):

    def testCreateEmpty(self):
        f = Format()
        b = f.build().tobits()
        self.assertEqual(len(b), 0)
        self.assertTrue(f.name is None)

    def testCreateFromDtype(self):
        d = Dtype('u12')
        f = Format('x', [Field(d)])
        x = f.build(1000)
        self.assertEqual(f.name, 'x')
        self.assertEqual(x.tobits(), 'uint:12=1000')
        self.assertEqual(len(x.tobits()), 12)

    def testCreateFromBitsString(self):
        f = Format('x', [Field('float16', 'foo', 12.5)])
        g = Format('y', ['float16 <foo> =12.5'])
        self.assertEqual(f.tobits(), g.tobits())
        self.assertEqual(f.name, 'x')

    def testCreateFromDtypeString(self):
        f = Format('x', ['float16'])
        self.assertTrue(f.fields[0].name is None)
        self.assertEqual(f.fields[0].dtype, Dtype('float', 16))


    def testCreateFromBits(self):
        b = Bits('0xabc')
        f = Format('', [Field(b)])
        x = f.build()
        self.assertTrue(f.name is None)
        self.assertEqual(x.tobits(), '0xabc')
        self.assertTrue(isinstance(x, Format))

    def testCreateFromBitsWithName(self):
        f = Format('x', [Field('0xabc', 'some_bits')])
        x = f.build()
        self.assertTrue(x, '0xabc')

    def testCreateFromList(self):
        f = Format('header', [Bits('0xabc'), Dtype('u5'), Dtype('u5')])
        x = f.build(3, 10)
        self.assertEqual(x.tobits(), '0xabc, u5=3, u5=10')
        f2 = f.parse(x.tobits())
        self.assertTrue(isinstance(f2, Format))
        # self.assertEqual(list(f2.values()), [3, 10])

    def testComplicatedCreation(self):
        f = Format('header', ['0x000001b3', 'u12', 'u12 <height> = 288', 'bool <flag> =True'])
        self.assertEqual(f.name, 'header')
        b = f.build(352).tobits()
        self.assertEqual(b, '0x000001b3, u12=352, u12=288, 0b1')
        f2 = Format('main', [f, 'bytes5'])
        f3 = f2.build(100, b'12345')
        self.assertEqual(f3.tobits(), Bits('0x000001b3, u12=100, u12=288, 0b1') + b'12345')

    def testNestedFormats(self):
        header = Format('header', ['0x000001b3', 'u12<width>', 'u12<height>', 'bool<f1>', 'bool<f2>'])
        main = Format('main', ['0b1', 'i7<v1>', 'i9<v2>'])
        f = Format('all', [header, main, '0x47'])
        b = Bits('0x000001b3, u12=100, u12=200, 0b1, 0b0, 0b1, i7=5, i9=-99, 0x47')
        f2 = f.parse(b)
        t = f2['header']
        self.assertEqual(t['width'], 100)
        self.assertEqual(f2['header']['width'], 100)
        self.assertEqual(f2['main']['v2'], -99)

class Addition(unittest.TestCase):

    def testAddingBits(self):
        f = Format('x')
        f += '0xff'
        self.assertEqual(f.tobytes(), b'\xff')
        f += 'i9<penguin> =-8'
        x = f['penguin']
        self.assertEqual(x, -8)
        f['penguin'] += 6
        self.assertEqual(f['penguin'], -2)


class ArrayTests(unittest.TestCase):

    def testSimpleArray(self):
        array_field = Field('u8', 'my_array', items=20)
        f = Format('a', [array_field])
        self.assertEqual(f.fields[0].items, 20)
        fp = f.build([*range(20)])
        a = fp.tobits()

        f2 = Format('b', ['u8*20 <new_array>'])
        self.assertEqual(f2.fields[0].items, 20)
        self.assertEqual(f2.fields[0].value, None)
        f2['new_array'] = a
        self.assertEqual(fp, f2)


    def testExampleWithArray(self):
        f = Format('construct_example', [
                   Field('bytes', 'signature', b'BMP'),
                   'i8 <width>',
                   'i8 <height>',
                   'u8 * {width * height} <pixels>',
                   ])
        b = f.build(3, 2, [7, 8, 9, 11, 12, 13])
        v = b'BMP\x03\x02\x07\x08\t\x0b\x0c\r'
        self.assertEqual(b.tobytes(), v)
        p = f.parse(Bits(v))
        self.assertEqual(p['width'], 3)
        self.assertEqual(p['height'], 2)
        self.assertEqual(p['pixels'],[7, 8, 9, 11, 12, 13])
        self.assertTrue(type(p['pixels']) == list)


class Methods(unittest.TestCase):

    def testClear(self):
        f = Format('header', ['0x000001b3', 'u12', 'u12 <height> = 288', 'bool <flag> =True'])
        f.clear()
        g = Format('empty_header', ['0x000001b3', 'u12', 'u12', 'bool'])
        self.assertEqual(f, g)

    def testGetItem(self):
        f = Format('q', ['float16=7', 'bool', 'bytes5', 'u100 <pop> = 144'])
        self.assertEqual(f[0], 7)
        self.assertEqual(f[1], None)
        self.assertEqual(f['pop'], 144)

    def testSetItem(self):
        f = Format('q', ['float16=7', 'bool', 'bytes5', 'u100 <pop> = 144'])
        f[0] = 2
        self.assertEqual(f[0], 2)
        f[0] = None
        self.assertEqual(f[0], None)
        f['pop'] = 999999
        self.assertEqual(f['pop'], 999999)
