# Release Notes

### September 2024: version 0.1.0

#### First working version

This release is quite fully featured in terms of the bit manipulation and creation capabilities.
There are over 400 unit tests and the documentation is slowly getting there.

The binary format features that make this library distict from others such as bitstring and bitarray are still quite limited, but the features that are present should be quite usuable.

The API has gone through many iterations already, and is now settling down. There will still be changes though, and no guarantees are made about backwards compatibility at this stage.

Things included:

* `Bits` -- An immutable container for storing binary data.
* `Dtype` -- A data type used to interpret binary data.
* `Array` -- A mutable container for contiguously allocated objects with the same `Dtype`.
* `Field` -- Represents an optionally named, well-defined amount of binary data with a single data type.
* `Format` -- A sequence of `FieldType` objects, such as `Field` or other `Format` instances.

Things not included yet:

* **Streaming methods.** There is no concept of a bit position, or of reading through a `Bits`.
* **Field expressions.** Rather than hard coding everything in a field, some parts will be calculated during the parsing process. For example in the format `'[w: u16, h: u16, [u8; {w * h}]]'` the size of the `'u8'` array would depend on the values parsed just before it.
* **New field types.** Fields like `Repeat`, `Find` and `If` are planned which will allow more flexible formats to be written.
* **Exotic floating point types.** There are a number of extra floating point types such as `bfloat` and the MXFP 8, 6 and 4-bit variants that will be ported over from `bitstring`.
* **Performance improvements.** A primary focus on the design of `bitformat` is that it should be fast. Early versions won't be well optimized, but tests so far are quite promising, and the design philosophy should mean that it can be made even more performant later.
* **LSB0.** Currenlty all bit positions are done with the most significant bit being bit zero (MSB0). I plan to add support for least significant bit zero (LSB0) bit numbering as well.

### January 2024: version 0.0.1

#### Project start

The original version was really just a placeholder with very limited functionality. It's main job was to reserve the name on PyPI.

