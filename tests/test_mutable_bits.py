from bitformat import Mutibs, Tibs


def test_mutibs_from_dtype_and_properties():
    m = Mutibs.from_dtype("bits4", "0b1010")
    assert isinstance(m, Mutibs)
    assert m.bits == Tibs("0b1010")

    m.bool = True
    assert m == "0b1"
    assert m.bool is True


def test_mutibs_extend_and_extend_left_are_tibs_native_names():
    m = Mutibs("0x0f")
    assert m.extend("0x0a") is None
    assert m == "0x0f0a"

    assert m.extend_left("0b11") is None
    assert m == "0b110000111100001010"


def test_mutibs_replace_returns_count():
    m = Mutibs("0b0101")
    count = m.replace("0b1", "0b11")
    assert count == 2
    assert m == "0b011011"


def test_mutibs_insert_rotate_reverse_and_byte_swap_return_none():
    m = Mutibs("0b1001")
    assert m.insert(2, "0b11") is None
    assert m == "0b101101"

    assert m.rotate_left(2) is None
    assert m == "0b110110"

    assert m.rotate_right(2) is None
    assert m == "0b101101"

    assert m.reverse() is None
    assert m == "0b101101"

    b = Mutibs("0x1234")
    assert b.byte_swap() is None
    assert b == "0x3412"


def test_mutibs_set_unset_and_invert():
    m = Mutibs("0b0000")
    assert m.set(1) is None
    assert m == "0b0100"

    assert m.unset(1) is None
    assert m == "0b0000"

    assert m.invert() is None
    assert m == "0b1111"
