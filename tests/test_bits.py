import pytest
from bitformat import Dtype, Bits


def test_build():
    a = Bits.build('u12', 104)
    assert a == 'u12 = 104'
    b = Bits.build('bool', False)
    assert len(b) == 1
    assert b[0] == 0
    c = Bits.build(Dtype('float', 64), 13.75)
    assert len(c) == 64
    assert c.parse('f64') == 13.75