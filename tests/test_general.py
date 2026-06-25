
from bitformat import Format, If, Repeat, FieldType, Field, DtypeSingle, Dtype, DtypeTuple, DtypeArray, Tibs, Mutibs

from bitformat._bits import tibs_from_any

# import tomllib
#
#
# def test_version_number():
#     with open("../pyproject.toml") as f:
#         pyproject_data = tomllib.loads(f.read())
#         toml_version = pyproject_data["project"]["version"]
#         assert bitformat.__version__ == toml_version

def test_info_strings():
    # This just exercises the info methods. We don't check the values as they are not part of the interface.
    # We just check that they are strings and not empty.
    things_with_info = [
        DtypeSingle("u8"),
        DtypeSingle("bool"),
        DtypeSingle("bits8"),
        DtypeSingle("bytes32"),
        DtypeSingle("f32"),
        DtypeSingle("i"),
        DtypeSingle("u{x + 1}"),

        DtypeArray("[u8; 3]"),
        DtypeArray("[u8;]"),
        DtypeArray("[bool; 0]"),
        DtypeArray("[f{a}; {b}]"),

        DtypeTuple("(u8, f16, bool)"),
        DtypeTuple("([u8; 10], [bool; 0], i20)"),
        DtypeTuple("(i1)"),

        Field("u8"),
        Field("bool"),
        Field("name: bytes32"),
        Field("x: [f32; ]"),

        If("if {x > 0}: u8 else: i8"),

        Repeat("repeat {3}: [u8; 3]"),

        Format("my_format: (header: hex8 = 0x47, flag: bool, if {flag}: data: [u8; 6] else: data: bool, f32)"),
    ]
    for thing in things_with_info:
        info = thing.info()
        assert isinstance(info, str)
        assert '\n' not in info
        assert len(info) > 0
        # print(f"{thing!r} : {info}")


def test_tibs_creation_helpers():
    a = tibs_from_any("0xf")
    assert a == Tibs('0xf')
    b = tibs_from_any(b'123')
    assert b == Tibs.from_bytes(b'123')
    b = b.to_mutibs()
    c = tibs_from_any(b)
    assert c == Tibs.from_bytes(b'123')
    assert type(b) == Mutibs
