import unittest
from bitformat import Dtype, Bits, Field
import bitformat


def setUpModule():
    bitformat.format.colour = bitformat.format.Colour(False)

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
        f1 = Field(b)
        self.assertEqual(f1.bits(), b)
        with self.assertRaises(ValueError):
            _ = Field(Bits())

    def testCreationWithNames(self):
        good = ['self', 'three3', '_why_']
        bad = ['thi<s', '[hello]']
        for name in good:
            f = Field('u8', name)
            self.assertEqual(f.name, name)
            f2 = Field(f'u8<{name}>')
            self.assertEqual(f2.name, name)

        for name in bad:
            with self.assertRaises(ValueError):
                _ = Field('u8', name)

        for n in good:
            with self.assertRaises(ValueError):
                _ = Field(f'u8 <{n}>', n)

    def testCreationFromStrings(self):
        f = Field('bool < flag_12 > ')
        self.assertEqual(f.dtype.name, 'bool')
        self.assertEqual(f.name, 'flag_12')
        self.assertTrue(f.value() is None)
        f = Field('ue = 2')
        self.assertEqual(f.dtype.name, 'ue')
        self.assertEqual(f.value(), 2)
        self.assertEqual(f.bits(), '0b011')
        f = Field('bytes', name='hello', value=b'hello world!')
        self.assertEqual(f.value(), b'hello world!')
        self.assertEqual(f.name, 'hello')
        self.assertEqual(f.dtype, Dtype('bytes'))
