#!/usr/bin/env python

from bitformat import Format, Dtype, Bits, Field, Array, FieldType, Repeat
from hypothesis import given
import pytest
import hypothesis.strategies as st
import random


class TestCreation:
    def test_create_empty(self):
        f = Format()
        f.pack([])
        b = f.to_bits()
        assert len(b) == 0
        assert f.name == ""
        assert len(f) == 0

    def test_create_from_dtype(self):
        d = Dtype.from_string("u12")
        f = Format.from_params([Field.from_params(d)], "x")
        f.pack([1000])
        x = f.to_bits()
        assert f.name == "x"
        assert x == "u12=1000"
        assert len(x) == 12
        assert len(f) == 1

    def test_create_from_bits_string(self):
        f = Format.from_params([Field.from_params("f16", "foo", 12.5)], "x")
        g = Format.from_params(["foo: f16=12.5"], "y")
        assert f.to_bits() == g.to_bits()
        assert f.name == "x"

    def test_create_from_dtype_string(self):
        with pytest.raises(ValueError):
            _ = Format("(x: f16)")  # No comma
        f = Format("(x: f16,)")
        assert f.fields[0].name == "x"
        assert f.fields[0].dtype == Dtype.from_params("f", 16)

    @given(name=st.sampled_from(["f16", "u12", "bool", "f64"]))
    def test_building_field(self, name):
        f = Field(name)
        f.pack(0)
        b = f.to_bits()
        assert b == Bits.from_string(f"{name}=0")

    def test_create_from_bits(self):
        b = Bits.from_string("0xabc")
        f = Format.from_params([Field.from_bits(b)])
        f.pack([])
        x = f.to_bits()
        assert f.name == ""
        assert x == "0xabc"
        assert isinstance(x, Bits)

    def test_create_from_bits_with_name(self):
        f = Format.from_params([Field.from_bits("0xabc", "some_bits")])
        f.pack([])
        assert f.to_bits() == "0xabc"

    def test_create_from_list(self):
        f = Format.from_params(["const bits = 0xabc", "u5", "u5"])
        f.pack([3, 10])
        x = f.to_bits()
        assert x == "bits = 0xabc, u5=3, u5=10"
        f.parse(x)
        assert isinstance(f, Format)

    def testComplicatedCreation(self):
        f = Format.from_params(
            (
                "const bits = 0x000001b3",
                "u12",
                "height:const u12  = 288",
                "flag: const bool  =True",
            ),
            "header",
        )
        g = Format(
            "header= (const bits = 0x000001b3, u12, height: const u12 = 288, flag: const bool = True)"
        )
        assert f == g
        assert f.name == "header"
        f.pack([352])
        assert f.to_bits() == "0x000001b3, u12=352, u12=288, 0b1"
        f2 = Format.from_params([f, "bytes5"], "main")
        # f3 = f2.pack([[[352]], b'12345'])
        # assert f3 == Bits.from_string('0x000001b3, u12=352, u12=288, 0b1') + b'12345'

    def test_nested_formats(self):
        header = Format.from_params(
            ["bits = 0x000001b3", "width:u12", "height:u12", "f1:bool", "f2:bool"],
            "header",
        )
        main = Format.from_params(["bits = 0b1", "v1:i7", "v2:i9"], "main")
        f = Format.from_params([header, main, "bits = 0x47"], "all")
        b = Bits.from_string(
            "bits = 0x000001b3, u12=100, u12=200, bits = 0b1, bits = 0b0, bits = 0b1, i7=5, i9=-99, bits = 0x47"
        )
        f.parse(b)
        t = f["header"]
        assert t["width"].value == 100
        assert f["header"]["width"].value == 100
        assert f["main"]["v2"].value == -99


@pytest.mark.skip
def test_building():
    f1 = Field("u8")
    f1.pack(9)
    assert f1.value == 9

    f2 = Field("[u8; 3]")
    f2.pack([1, 2, 3])
    assert f2.value == (1, 2, 3)

    f3 = Format.from_params(["u8"])
    f3.pack([4])
    assert f3.value == [4]

    f4 = Format.from_params(["[u8; 3]"])
    f4.pack([[1, 2, 3]])
    assert f4.value == [(1, 2, 3)]

    f5 = Format.from_params(["u8", "[u8; 3]"])
    f5.pack([4, [1, 2, 3]])
    assert f5.value == [4, (1, 2, 3)]

    f6 = Format.from_params(["u8", "[u8; 3]", "u8"])
    f6.pack([4, [1, 2, 3], 5])
    assert f6.value == [4, (1, 2, 3), 5]

    f7 = Format.from_params([f1, f2])
    f7.pack([6, [4, 5, 6]])
    assert f7.value == [6, (4, 5, 6)]

    f8 = Format.from_params([f1, f7])
    f8.pack([7, [8, (9, 10, 11)]])
    assert f8.value == [7, (8, (9, 10, 11))]


@pytest.mark.skip
def test_packing_bug():
    f = Format("bug = [u8, [u8, u8]]")
    f.pack([10, [20, 30]])
    assert f.value == [10, [20, 30]]


class TestAddition:
    def test_adding_bits(self):
        f = Format()
        f += Field.from_bits("0xff")
        assert f.to_bytes() == b"\xff"
        assert f.fields[0].to_bytes() == b"\xff"
        assert len(f) == 1
        f += Field.from_string("penguin:i9 =-8")
        assert len(f) == 2
        x = f["penguin"]
        assert x.value == -8
        f["penguin"].value += 6
        assert f["penguin"].value == -2


class TestArray:
    def test_simple_array(self):
        array_field = Field.from_params("[u8; 20]", "my_array")
        f = Format.from_params([array_field], "a")
        assert f.fields[0].dtype.items == 20
        f.pack([list(range(20))])

        f2 = Format.from_params(["new_array: [u8;20]"], "b")
        assert f2.fields[0].dtype.items == 20
        assert f2.fields[0].value is None
        with pytest.raises(ValueError):
            f2["new_array"].value = f.to_bits()[2:]
        f2["new_array"].value = f.to_bits()
        assert f.to_bits() == f2.to_bits()

    @pytest.mark.skip
    @given(w=st.integers(1, 5), h=st.integers(1, 5))
    def test_example_with_array(self, w, h):
        f = Format(
            [
                Field("bytes", "signature", b"BMP", const=True),
                "width: i8",
                "height: i8",
                "pixels: [u8 ; {width * height}]",
            ],
            "construct_example",
        )
        p = [random.randint(0, 255) for _ in range(w * h)]
        b = f.pack([w, h, p])
        f.clear()
        f.parse(b)
        assert f["width"].value == w
        assert f["height"].value == h
        assert f["pixels"].value == p


@pytest.mark.skip
def test_example_from_docs():
    f = Format(["x: u8", "y: u{x}"])
    b = Bits.from_string("u8=10, u10=987")
    f.parse(b)
    assert f["y"].value == 987

    f = Format(
        [
            "sync_byte: const hex8 = 0xff",
            "items: u16",
            "flags: [bool ; {items + 1} ] ",
            Repeat(
                "{items + 1}", ["byte_cluster_size: u4", "bytes{byte_cluster_size}"]
            ),
            "u8",
        ]
    )
    f.pack([1, b"1", 2, b"22", 3, b"333", 12], items=2, flags=[True, False, True])


@pytest.mark.skip
def test_creating_with_keyword_value():
    f = Format.from_params(["x: u10", "u10={2*x}"])
    b = f.pack([6])
    assert b == "u10=6, u10=12"


@pytest.mark.skip
def test_items():
    f = Format.from_params(["q:i5", "[u3; {q + 1}]"])
    b = Bits.from_string("i5=1, u3=2, u3=0")
    f.parse(b)
    assert f[0].value == 1
    assert f[1].value == [2, 0]
    f.clear()
    b2 = f.pack([1, [2, 0]])
    assert b2 == b
    f.clear()
    b3 = f.pack([3, [1, 2, 3, 4]])
    assert b3 == Bits.from_string("i5=3, u3=1, u3=2, u3=3, u3=4")


class TestMethods:
    def test_clear(self):
        f = Format.from_params(
            ["const bits = 0x000001b3", "u12", "height:u12", "  flag : bool "], "header"
        )
        f["height"].value = 288
        f.clear()
        g = Format.from_string(
            "header = (const bits = 0x000001b3, u12, height:u12, flag:bool)"
        )
        assert f == g

    def test_get_item(self):
        f = Format.from_params(["f16=7", "bool", "bytes5", "pop :u100  = 144"])
        assert f.fields[0].value == 7
        assert f.fields[1].value is None
        assert f["pop"].value == 144

    def test_set_item(self):
        f = Format.from_params(["const f16=7", "bool", "bytes5", "pop : u100 = 144"])
        with pytest.raises(ValueError):
            f.fields[0].value = 2
        f.fields[0].const = False
        with pytest.raises(ValueError):
            f[0] = 2
        f.fields[0].value = 2
        f.fields[0].const = True
        assert f.fields[0].value == 2
        f["pop"].value = 999999
        assert f["pop"].value == 999999


@pytest.mark.skip
def test_repeating_field():
    f = Repeat(5, "u8")
    d = Array("u8", [1, 5, 9, 7, 6]).data
    f.unpack(d)
    assert f.value == [1, 5, 9, 7, 6]


@pytest.mark.skip
def test_find_field():
    b = Bits("0x1234000001b3160120")
    f = Format(
        [Find("0x000001"), "start_code: hex32 = 000001b3", "width: u12", "height: u12"]
    )
    f.parse(b)
    assert f["width"].value == 352
    f.clear()
    assert f["width"].value is None
    f.pack([352, 288])
    assert f.to_bits() == "0x000001b3160120"


@pytest.mark.skip
def test_format_repr_and_str():
    f = Format(
        [
            "u8 <s>",
            Repeat(
                "s + 1",
                Format(
                    [
                        "u12 <width>",
                        "u12 <height>",
                        Repeat("width * height", "u8", "data"),
                    ]
                ),
            ),
            "hex <eof> = 123",
        ],
        "my_format",
    )
    s = str(f)
    r = repr(f)
    assert "my_format" in s
    print(s)
    print(r)
    assert "my_format" in r


def test_format_get_and_set():
    f = Format("(u8, u8, u8)")
    for field in f.fields:
        field.value = 12
    assert f.value == [12, 12, 12]
    f.fields[0].value = 0
    assert f.value == [0, 12, 12]
    g = Format.from_params(f.fields)
    assert g.value == [0, 12, 12]
    f.fields[-1].value = 7
    assert g.fields[-1].value == 12


@pytest.mark.skip
def test_repeating_from_expression():
    f = Format(["x: u8", Repeat("{2*x}", "hex4")], "my_little_format")
    b = f.pack([2, ["a", "b", "c", "d"]])
    assert b.parse("hex") == "02abcd"


@pytest.mark.skip
def test_repeat_with_const_expression():
    f = Format(["the_size: i9", Repeat("{the_size}", ["const u5=0", "const bin3=111"])])
    f.pack([3])
    assert f.to_bits() == "i9=3, 0x070707"


@pytest.mark.skip
def test_repeat_with_bits():
    f = Repeat(3, "0xab")
    b = f.pack()
    assert b == "0xababab"
    f2 = Repeat(2, b)
    b2 = f2.pack()
    assert b2 == "0xabababababab"


@pytest.mark.skip
def test_repeat_with_dtype():
    f = Repeat(4, Dtype.from_string("i4"))
    b = f.pack([1, 2, 3, 4])
    f.unpack(b)
    assert f.value == [1, 2, 3, 4]

    f = Repeat(4, Dtype.from_string("i40"))
    b = f.pack([-400, 200, -200, 400])
    f.unpack(b)
    assert f.value == [-400, 200, -200, 400]


def test_field_array_str():
    f = Field.from_string("test   :  f32 = 0.25  ")
    assert str(f) == "test: f32 = 0.25"
    f = Field.from_string("test: [f32 ; 3]")
    assert str(f) == "test: [f32; 3]"


def test_format_repr_string():
    f = Format.from_params(["x:const u8 = 12", "u:bool = False", "[u3;44]"], "dave")
    r = repr(f)
    assert (
        r
        == "Format.from_params(['x: const u8 = 12', 'u: bool = False', '[u3; 44]'], 'dave')"
    )


def test_to_bits():
    f = Format.from_params(["u8", "u8", "u8"])
    f.pack([1, 2, 3])
    b = f.to_bits()
    assert b == "u8=1, u8=2, u8=3"
    f.fields[1].clear()
    assert f.fields[0].value == 1
    assert f.fields[1].value is None
    assert f.fields[2].value == 3
    with pytest.raises(ValueError):
        _ = f.value
    assert f.fields[0].to_bits() == "u8=1"
    with pytest.raises(ValueError):
        _ = f.fields[1].to_bits()
    with pytest.raises(ValueError):
        _ = f.to_bits()


def test_partial_parse():
    f = Format.from_params(["bool", "[f16;3]"])
    b = Bits.from_string("0b1, f16=1.0, f16=2.0, f16=3.0")
    f.parse(b)
    assert f.fields[0].value == True
    assert f.fields[1].value == (1.0, 2.0, 3.0)
    f.clear()
    with pytest.raises(ValueError):
        _ = f.parse(b[:-16])


def test_from_string():
    s = "header = (u8,u4, bool)"
    f = Format.from_string(s)
    assert f.name == "header"
    assert f.fields[0].dtype == Dtype.from_string("u8")
    assert str(f) == str(Format(str(f)))


def test_recursive_from_string():
    s = "header = (u8, u4, bool,body=(u8=23, [u4; 3], bool))"
    f = FieldType.from_string(s)
    assert f.name == "header"
    assert f.fields[3].fields[0].value == 23
    b = f["body"]
    assert b.fields[0].value == 23
    assert str(f) == str(Format(str(s)))
    assert str(b) == str(Format("body = (u8=23, [u4; 3], bool)"))

    fp = eval(repr(f))
    assert fp == f


def test_recursive_error_message():
    try:
        f = Format("(u1, (u1, (u1, (u1, (u1, (u1, penguin))))))")
    except ValueError as e:
        assert len(e.__notes__) == 3
    else:
        assert False


def test_interesting_types_from_string():
    s = "  (const f32= -3.75e2 , _fred : bytes4 = b'abc\x04',) "
    f = Format.from_string(s)
    assert f.fields[0].value == -375
    assert f["_fred"].value == b"abc\x04"


# def test_expression_dtypes():
#     a = Field.from_string('u{testing}')
#     assert str(a) == 'u{testing}'
#     d = Field.from_string('my_name: [f{4*e}; {a + b}]')
#     assert str(d) == 'my_name: [f{4*e}; {a+b}]'
#     f = Format.from_string('[x: u8, [u{x}; {x + 1}]]')
#     b = Bits('u8=3, u3=1, u3=2, u3=3, u3=4')
#     f.parse(b)
#     assert f['x'].value == 3
#     assert f[1].value == [1, 2, 3, 4]
#     assert f.value == [3, [1, 2, 3, 4]]


def test_unpack():
    f = Format.from_string("header = (u8, u4, bool)")
    b = Bits.from_string("u8=1, u4=2, 0b1")
    assert f.unpack(b) == [1, 2, True]
    f.fields[1].clear()
    with pytest.raises(ValueError):
        _ = f.unpack()


def test_construction_by_appending():
    f = Format()
    f += "u8"
    f += "i4"
    f += Field("const f16 = 0.25")
    g = Format()
    g.append("u8")
    g.append("i4")
    g += Field("const f16 = 0.25")
    h = Format()
    h.extend(["u8", "i4", "const f16=0.25"])
    i = Format() + "u8"
    i = i + "i4" + "const f16=0.25"
    assert f == g == h == i


f_str = """
sequence_header = (
    sequence_header_code: const hex8 = 0x000001b3
    horizontal_size_value: u12
    vertical_size_value: u12
    aspect_ratio_information: u4
    frame_rate_code: u4
    bit_rate_value: u18
    marker_bit: bool
    vbv_buffer_size_value: u10,
    constrained_parameters_flag: bool
    load_intra_quantiser_matrix: u1
)
"""


def test_example_format():
    f = Format(f_str)


def test_format_str_equivalences():
    f1 = Format("  abc = ( f16, u5, [bool; 4])")
    f2 = Format("abc=(f16,u5,[  bool  ;4]  )  ")
    f3 = Format("""
    
    abc = 
    (
    f16,
    u5
    
    [bool;4],)
    """)
    assert f1 == f2 == f3
    print(f1, f2, f3)
    assert str(f1) == str(f2) == str(f3)
    assert repr(f1) == repr(f2) == repr(f3)
    f4 = eval(repr(f1))
    assert f4 == f1


def test_stretchy_field():
    f = Format("(u8, u)")
    f.unpack("0xff1")
    assert f.value == [255, 1]

    with pytest.raises(ValueError):
        _ = Format("(u, u8)")

    g = Format("(u5, bytes)")
    g.parse(b"hello_world")
    assert g.fields[0].value == 13
    with pytest.raises(ValueError):
        _ = g.fields[1].value


def test_repeated_field_copy():
    i = Field("hex4 = abcd")
    f = Format.from_params([i, i])
    assert f.fields[0].value == "abcd"
    assert f.fields[1].value == "abcd"
    f.fields[0].value = "0xdead"
    assert f.fields[0].value == "dead"
    assert f.fields[1].value == "abcd"


def test_format_copy():
    f = Format("(x: u8 = 10, y: u8 = 20)")
    g = Format.from_params([f, f])
    assert g.fields[0].value == [10, 20]
    f.fields[0].value = 5
    assert f.fields[0].value == 5
    assert g.fields[0].value == [10, 20]
    g.fields[0].fields[0].value = 7
    assert g.fields[0].value == [7, 20]
    assert g.fields[1].value == [10, 20]
    assert f.fields[0].value == 5


s = """
header = (
    x: u8,
    y: u8,
    z: u8,
    data: [u8; 3],
    Repeat{2}: (
        a: u8,
        b: u8
    )
    bool
)
"""


def test_format_with_repeat():
    f = Format(s)
    b = Bits.from_bytes(b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d")
    f.parse(b)
    assert f["x"].value == 1
    assert f["y"].value == 2
    assert f["z"].value == 3
    assert f["data"].value == (4, 5, 6)
    assert f.fields[4].value == [[7, 8], [9, 10]]
    # assert f['a'].value == [7, 9]


s2 = """
x = ( i5,
q: u8,
(u3, 
u4
)
u5
)
"""


def test_format_inside_format_from_string():
    test = Format("x = ((u8, u8),)")
    test.pack([[1, 2]])
    assert test.value == [[1, 2]]
    f = Format(s2)
    assert f.bit_length == 25
    assert len(f.fields) == 4
    f.pack([1, 2, [3, 4], 5])
    assert f.value == [1, 2, [3, 4], 5]

# def test_repr_eval_with_repeat():
#     f = Format(s)
#     r = repr(f)
#     f2 = eval(r)
#     assert f == f2


def test_eq():
    f = Format("(u8, u8)")
    assert f == Format("(u8, u8)")
    assert f != Format("(u8, u8, u8)")
    assert f != Format("(u8, const u8 = 10)")
    assert f != Format("(u8, x: u8)")
    assert Format("(u8 = 3,)") == Format("(u8 = 3,)")
    assert Format("(u8 = 3,)") != Format("(u8 = 4,)")

def test_wrong_arguments():
    f = Format("(bool, bool, (i3, q: i3), [f64; 1])")
    f.pack([True, False, [2, -2], [4.5]])
    assert f.value == [True, False, [2, -2], (4.5,)]
    f.clear()
    with pytest.raises(TypeError):
        f.pack(1)
    f.pack([1])
