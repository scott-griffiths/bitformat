#!/usr/bin/env python
import unittest
from bitformat import Format, Dtype


class testCreation(unittest.TestCase):

    def testCreateEmpty(self):
        f1 = Format()

    def testCreateFromDtype(self):
        d = Dtype('u12')
        f1 = Format(d)
