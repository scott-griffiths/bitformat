from bitformat import Reader, Tibs


def test_tibs_literals_and_dtype_packing_are_joined_explicitly():
    b = Tibs.from_joined(["0b1", Tibs.from_dtype("u7", 5), Tibs.from_dtype("i9", -99), "0x47"])
    assert b.unpack("(bool, u7, i9, hex8)") == (True, 5, -99, "47")


def test_find_all_uses_tibs_native_list_semantics():
    b = Tibs("0b0010011")
    assert b.find_all("0b1") == [2, 5, 6]
    assert list(b.find_all_iter("0b1")) == [2, 5, 6]


def test_reader_accepts_tibs():
    r = Reader(Tibs.from_bytes(b"hello"))
    assert r.read("hex8") == "68"
    assert r.read("bytes16") == b"el"
    assert r.pos == 24


def test_large_integer_dtype_unpack_uses_bitformat_not_tibs_property_limits():
    b = Tibs.from_dtype("u1000", 1 << 300)
    assert b.unpack("u1000") == 1 << 300

    signed = Tibs.from_dtype("i1000", -(1 << 300))
    assert signed.unpack("i1000") == -(1 << 300)
