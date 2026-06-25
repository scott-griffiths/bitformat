import io

from bitformat import Dtype, Field, Tibs


def test_from_dtype_and_unpack_single_values():
    b = Tibs.from_dtype("u12", 104)
    assert b.unpack("u12") == 104
    assert b == Dtype("u12").pack(104)

    f = Tibs.from_dtype(Dtype("f64"), 13.75)
    assert f.unpack("f64") == 13.75


def test_from_dtype_and_unpack_composite_values():
    b = Tibs.from_dtype("[bool; 4]", [True, False, True, True])
    assert b.unpack("[bool; 4]") == (True, False, True, True)

    t = Tibs.from_dtype("(u4, bits3, bool)", [10, "0b101", False])
    assert t.unpack("(u4, bits3, bool)") == (10, Tibs("0b101"), False)


def test_unpack_with_range():
    b = Tibs.from_joined([Tibs.from_dtype("u12", 99), Tibs.from_dtype("bool", True), Tibs("0x4321")])
    assert b.unpack("u12", 0, 12) == 99
    assert b.unpack("bool", 12, 13) is True
    assert b.unpack("hex4", 13) == "4321"


def test_info_and_pp_methods_are_patched_on_tibs():
    b = Tibs.from_dtype("u8", 10)
    assert "unsigned int = 10" in b.info()

    stream = io.StringIO()
    b.pp("u4", "bin4", show_offset=False, stream=stream)
    assert "<Tibs, dtype1='u4', dtype2='bin4', length=8 bits>" in stream.getvalue()


def test_field_unpack_accepts_tibs():
    field = Field("value: u12")
    b = Tibs.from_dtype("u12", 100)
    assert field.unpack(b) == 100
