import unittest
from bitformat import Dtype, Bits, Field


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
        f = Field(Dtype('u8'), value=3)
        self.assertEqual(f.value, 3)
        f2 = Field.fromstring('u8 = 3')
        self.assertEqual(f2.value, 3)


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
        good = ['self', 'three3', '_why_', 'a_b_c', 'a1', 'a_1', 'a_1_2', 'a_1_2_3']
        bad = ['thi<s', '[hello]', 'a b', 'a-b', 'a.b', 'a b c']
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

    def testBuildingLotsOfTypes(self):
        f = Field('u4')
        b = f.build([15])
        self.assertEqual(b, '0xf')
        f = Field('i4')
        b = f.build([-8])
        self.assertEqual(b, '0x8')
        f = Field('e4m3float')
        b = f.build([0.5])
        self.assertEqual(b, '0x38')
        f = Field('bytes:3')
        b = f.build([b'abc'])
        self.assertEqual(b, '0x616263')
        f = Field('se')
        b = f.build([-5])
        self.assertEqual(b, '0b0001011')
        # f = Field('bits11')
        # with self.assertRaises(ValueError):
        #     _ = f.build([Bits('0x7ff')])
        # b = f.build([Bits('0b111, 0xff')])

    def testBuildingWithConst(self):
        f = Field.fromstring('u4 = 8')
        b = f.build([])
        self.assertEqual(b, '0x8')
        f.clear()
        b = f.build([])
        self.assertEqual(b, '0x8')
        f.const = False
        self.assertEqual(f.value, 8)
        f.clear()
        self.assertEqual(f.value, None)
