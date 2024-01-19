#!/usr/bin/env python
import unittest
from bitformat import Format, Dtype, Bits, Field


class Creation(unittest.TestCase):

    def testCreateEmpty(self):
        f = Format()
        b = f.build().tobits()
        self.assertEqual(len(b), 0)
        self.assertTrue(f.name is None)

    def testCreateFromDtype(self):
        d = Dtype('u12')
        f = Format('x', [Field('', d)])
        self.assertEqual(f.empty_fields, 1)
        x = f.build(1000)
        self.assertEqual(f.name, 'x')
        self.assertEqual(x.tobits(), 'uint:12=1000')
        self.assertEqual(len(x.tobits()), 12)

    def testCreateFromBitsTuple(self):
        f = Format('x', [('foo', 'float16', 12.5)])
        g = Format('y', [('foo', 'float16=12.5')])
        self.assertEqual(f.empty_fields, 0)
        self.assertEqual(f.tobits(), g.tobits())
        self.assertEqual(f.name, 'x')

    def testCreateFromDtypeTuple(self):
        f = Format('x', [('', 'float16')])
        self.assertEqual(f.empty_fields, 1)
        self.assertTrue(f.fields[0].name is None)
        self.assertEqual(f.fields[0].dtype, Dtype('float', 16))


    def testCreateFromBits(self):
        b = Bits('0xabc')
        f = Format('', [Field('', b)])
        x = f.build()
        self.assertTrue(f.name is None)
        self.assertEqual(x.tobits(), '0xabc')
        self.assertTrue(isinstance(x, Format))

    def testCreateFromBitsWithName(self):
        f = Format('x', [Field('some_bits', '0xabc')])
        x = f.build()
        self.assertTrue(x, '0xabc')

    # def testCreateFromList(self):
    #     f = Format('header', [Bits('0xabc'), Dtype('u5'), Dtype('u5')])
    #     x = f.build(3, 10)
    #     self.assertEqual(x, '0xabc, u5=3, u5=10')
    #     f2 = f.parse(x)
    #     self.assertTrue(isinstance(f2, Format))
    #     # self.assertEqual(list(f2.values()), [3, 10])

    def testComplicatedCreation(self):
        f = Format('header', ['0x000001b3', 'u12', ('height', 'u12', 288), ('flag', 'bool', True)])
        self.assertEqual(f.name, 'header')
        b = f.build(352).tobits()
        self.assertEqual(b, '0x000001b3, u12=352, u12=288, 0b1')
        self.assertEqual(f.empty_fields, 1)
        f2 = Format('main', [f, 'bytes5'])
        self.assertEqual(f2.empty_fields, 2)
        f3 = f2.build(100, b'12345')
        self.assertEqual(f2.empty_fields, 2)
        self.assertEqual(f3.empty_fields, 0)
        self.assertEqual(f3.tobits(), Bits('0x000001b3, u12=100, u12=288, 0b1') + b'12345')

    # def testCreationFromComplexString(self):
    #     f = Format('', '<width>u12, <height>u12=288, <flag>bool, 0xf, 0b1, u12=352, u12=288')

class Addition(unittest.TestCase):

    def testAddingBits(self):
        f = Format('x')
        f += '0xff'
        self.assertEqual(f.tobytes(), b'\xff')