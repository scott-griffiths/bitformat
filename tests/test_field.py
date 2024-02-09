import unittest
from bitformat import Dtype, Bits, Field
import bitformat


def setUpModule():
    bitformat.common.colour = bitformat.common.Colour(False)

class Creation(unittest.TestCase):
    def testCreationFromDtype(self):
        ds = [Dtype('u9'), Dtype('i', 4), Dtype('e4m3float'), Dtype('bytes:3'), Dtype('sie'), Dtype('bits11')]
        for d in ds:
            f = Field(d)
            self.assertEqual(f.dtype, d)
            f2 = Field(str(d))
            self.assertEqual(f2.dtype, f.dtype)

        without_length = [Dtype('bytes'), Dtype('int')]
        for b in without_length:
            f = Field(b)
            self.assertTrue(f.dtype.length is None)

    def testCreationFromDtypeWithValue(self):
        pass

    def testCreationFromBits(self):
        b = Bits('0xf, 0b1')
        f1 = Field.frombits(b)
        self.assertEqual(f1.bits(), b)
        self.assertEqual(f1.const, True)
        with self.assertRaises(ValueError):
            _ = Field(Bits())
        f2 = Field.frombits(b'123')
        self.assertEqual(f2.value, b'123')
        b = f2.build()
        self.assertEqual(b.tobytes(), b'123')

    def testCreationWithNames(self):
        good = ['self', 'three3', '_why_']
        bad = ['thi<s', '[hello]']
        for name in good:
            f = Field('u8', name)
            self.assertEqual(f.name, name)
            f2 = Field.fromstring(f'u8<{name}>')
            self.assertEqual(f2.name, name)

        for name in bad:
            with self.assertRaises(ValueError):
                _ = Field('u8', name)

        for n in good:
            with self.assertRaises(ValueError):
                _ = Field(f'u8 <{n}>', n)

    def testCreationFromStrings(self):
        f = Field.fromstring('bool < flag_12 > ')
        self.assertEqual(f.dtype.name, 'bool')
        self.assertEqual(f.name, 'flag_12')
        self.assertTrue(f.value is None)
        f = Field.fromstring('ue = 2')
        self.assertEqual(f.dtype.name, 'ue')
        self.assertEqual(f.value, 2)
        self.assertEqual(f.bits(), '0b011')
        f = Field('bytes', name='hello', value=b'hello world!')
        self.assertEqual(f.value, b'hello world!')
        self.assertEqual(f.name, 'hello')
        self.assertEqual(f.dtype, Dtype('bytes'))

    def testStringCreationWithConst(self):
        f1 = Field.fromstring('u1 <f1> : 1')
        f2 = Field.fromstring('u1 <f2> = 1')
        self.assertEqual(f1, f2)
        self.assertTrue(f2.const)
        self.assertFalse(f1.const)
        f1.clear()
        f2.clear()
        self.assertEqual(f1.build([0]), '0b0')
        self.assertEqual(f2.build([]), '0b1')

class Building(unittest.TestCase):

    def testBuildingWithKeywords(self):
        f = Field.fromstring('u10 <piggy>')
        b = f.build([], {'piggy': 17})
        self.assertEqual(b, Bits('u10=17'))

