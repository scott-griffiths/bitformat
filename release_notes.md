# Release Notes

### June 2025: version 0.5.

* Added the `MutableBits` class. The 'mutating' methods from `Bits` (which previously returned a new object) have been moved to the new class and now mutate it. The new class was needed as some performance targets were just impossible to hit without it.

* Mutating methods in `Array` now return self so they can be chained.

* `Array.data` has been renamed to `Array.bits` as it's now just a `MutableBits` (`BitsProxy` has been removed as it's no longer needed).

* Significant performance improvements. Most tests now run as fast or faster than competing libraries - there are still some outliers to be worked on though.

### April 2025: version 0.4.

* Changing status from alpha to beta as the API is now much more stable.

* New `info()` methods on many types to give human readable descriptions of dtypes, fields, etc.

* Better coverage of platforms for wheels on PyPI.

* Numerous smaller fixes and improvements.

* A new logo!

### April 2025: version 0.3.

* Big reworking for Dtypes. `Dtype` is now an abstract base class that can create `DtypeSingle`, `DtypeArray` and `DtypeTuple` instances.
This gives extra flexibility throughout the library.

* Moved fully over to using a Lark grammar for parsing. This makes changes and experimentation much easier.

* More complete expressions, as well as the repeat and if/else field types.

* Numerous changes to the string representation of objects inside formats. Hopefully this is settling down now.


### January 2025: version 0.2.

This release replaces the core bit manipulation code with a version written in Rust. This should allow some great optimisations in the future, but this version is more a proof of concept to get the interface and the build systems working.

Some other changes are still a bit half-baked. There is code to switch from my hand-rolled format parsing to using the lark library. There are additions for new fields such as `Repeat`, `If` and `Pass`, and some work has been done on expressions. All of this is rather unfinished and planned for the 0.3 release, while this release concentrates on the move to use a Rust backend.

Other additions:

* `Reader` -- A new class that wraps a `Bits` to provide a bit position and read / parse functionality.

### September 2024: version 0.1.0

#### First working version

This release is quite fully featured in terms of the bit manipulation and creation capabilities.
There are over 400 unit tests and the documentation is slowly getting there.

The binary format features that make this library distinct from others such as bitstring and bitarray are still quite limited, but the features that are present should be quite useable.

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

The original version was really just a placeholder with very limited functionality. Its main job was to reserve the name on PyPI.

