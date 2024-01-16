#!/usr/bin/env python
import unittest
from bitformat import Format, Dtype, Bits


class testCreation(unittest.TestCase):

    def testCreateEmpty(self):
        f1 = Format()

    def testCreateFromDtype(self):
        d = Dtype('u12')
        f1 = Format(d)

    def testCreateFromBits(self):
        b = Bits('0xabc')
        f = Format(b)
        x = f.pack()
        self.assertEqual(x, '0xabc')
        self.assertTrue(isinstance(x, Bits))
    def testCreateFromList(self):
        f = Format([Bits('0xabc'), Dtype('u5'), Dtype('u5')])
        x = f.pack(3, 10)
        self.assertEqual(x, '0xabc, u5=3, u5=10')