import pytest
from bitformat import Bits, Format, If


def test_creation():
    i = If.from_parameters('{1 > 0}', 'u2', 'i2')
    assert len(i) == 2
    v = i.parse('0b11')
    assert v == 2
    assert i.value == 3

    assert(str(i) == 'if {1 > 0}:\n    u2 = 3\nelse:\n    i2')

def test_from_string():
    i = If.from_string('if {1 > 0}: u2 else: i2')
    assert len(i) == 2
    assert str(i) == 'if {1 > 0}:\n    u2\nelse:\n    i2'

    j = If('if {x < 5}: bool')
    with pytest.raises(ValueError):
        _ = len(j)

def test_simple_parse():
    f = Format.from_parameters(('x: u8',
                                If.from_parameters('{x > 50}', 'u8')))
    b = f.parse('0xabfe')
    assert b == 16
    assert f[0].value == 0xab
    assert f[1].value == 0xfe
    b = f.parse('0x0044')
    assert b == 8
    assert f[0].value == 0

def test_explicit_pass():
    f = If.from_parameters('{x > 0}', '', 'bool = True')
    f.parse(x = 2)
    assert len(f) == 0
    f.parse('0b1', x = -1)
    assert len(f) == 1
    assert f.value is True
