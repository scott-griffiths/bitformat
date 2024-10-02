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
                                If.from_parameters('{x > 50}', 'u8 = 0', 'u8 = 255')))
    assert len(f) == 16
    b = f.parse(Bits('0x37fe'))
    assert b == 16
