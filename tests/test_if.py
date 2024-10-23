import pytest
from bitformat import Format, If


def test_creation():
    i = If.from_params('{1 > 0}', 'u2', 'i2')
    assert i.bitlength == 2
    v = i.parse('0b11')
    assert v == 2
    assert i.value == 3

    assert(str(i) == 'if {1 > 0}:\n    u2 = 3\nelse:\n    i2')

def test_from_string():
    i = If.from_string('if {1 > 0}: u2 else: i2')
    assert i.bitlength == 2
    assert str(i) == 'if {1 > 0}:\n    u2\nelse:\n    i2'

    j = If('if {x < 5}: bool')
    with pytest.raises(ValueError):
        _ = j.bitlength

def test_simple_parse():
    f = Format.from_params(('x: u8',
                            If.from_params('{x > 50}', 'u8')))
    b = f.parse('0xabfe')
    assert b == 16
    assert f.fields[0].value == 0xab
    assert f.fields[1].value == 0xfe
    b = f.parse('0x0044')
    assert b == 8
    assert f.fields[0].value == 0

def test_explicit_pass():
    f = If.from_params('{x > 0}', '', 'bool = True')
    f.parse(x = 2)
    assert f.bitlength == 0
    f.parse('0b1', x = -1)
    assert f.bitlength == 1
    assert f.value is True
    f.parse(x = 4)
    assert f.bitlength == 0

# def test_slightly_more_complex_things():
#     f = Format("""my_format = (
#     header: hex2 = 0x47
#     flag: bool
#     if {flag}:
#         data: [u8; 6]
#     """)
#     b = f.pack([True, [5, 4, 3, 2, 1, 0]])
#     assert b == '0x47050403020100'