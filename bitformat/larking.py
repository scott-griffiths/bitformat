from lark import Lark, Transformer
from bitformat import Format, Field, DtypeName, DtypeSingle, Dtype
from typing import List, Union, Any

# Load the grammar from the .lark file
with open("format_parser.lark") as f:
    GRAMMAR = f.read()

class FormatTransformer(Transformer):
    def format(self, items):
        # Remove None values (from optional elements)
        items = [item for item in items if item is not None]

        # First item might be format name
        if len(items) >= 2 and isinstance(items[0], str):
            name = items[0]
            fields = items[1:]
        else:
            name = ''
            fields = items

        # Create Format from the field definitions
        return Format.from_params(fields, name)

    def field_name(self, items):
        return str(items[0])

    def format_name(self, items):
        return str(items[0])

    def dtype_name(self, items):
        return str(items[0])

    def dtype_size(self, items):
        return int(items[0])

    def dtype_single(self, items):
        name = items[0]
        size = items[1] if len(items) > 1 else None
        size_str = f"{size}" if size is not None else ""
        return Dtype.from_string(f"{name}{size_str}")

    def items(self, items):
        return int(items[0])

    def dtype_array(self, items):
        dtype = items[0]
        items_count = items[1] if len(items) > 1 else None
        return f"[{dtype}; {items_count if items_count is not None else ''}]"

    def const_field(self, items):
        # Remove None values
        items = [item for item in items if item is not None]
        # Final value is the value itself
        value = items[-1]
        # Penultimate value is the dtype
        dtype = items[-2]
        # Name is the first value if it exists
        name = items[0] if len(items) > 2 else ''
        return Field.from_params(dtype, name, value, const=True)

    def mutable_field(self, items):
        # Remove None values
        items = [item for item in items if item is not None]

        if len(items) >= 2:  # name and dtype
            name = items[0]
            dtype = items[1]
            if len(items) > 2:  # has default value
                raise ValueError  # TODO
            return Field.from_params(dtype, name)
        else:  # just dtype
            dtype = items[0]
            return Field.from_params(dtype)

    def simple_value(self, items):
        return str(items[0])

    def list_of_values(self, items):
        return str(items[0])

    # Add other transformer methods as needed...

def parse_format(format_string: str) -> Format:
    """
    Parse a format string and return a Format object.

    Args:
        format_string: The format string to parse

    Returns:
        A Format object representing the parsed format

    """
    parser = Lark(GRAMMAR, start='format', parser='earley')
    transformer = FormatTransformer()
    tree = parser.parse(format_string)
    return transformer.transform(tree)

def main():
    # Simple format with basic fields
    format1 = parse_format("[u8, flag: bool]")
    print(format1)

    # Format with a name and constant field
    format2 = parse_format("header = [const bits = 0x000001b3, width: u12, height: u12]")
    print(format2)

    # Format with array fields
    format3 = parse_format("packet = [type: u8, [u8; 4], checksum: u16]")
    print(format3)

    # More complex format with nested structures
    format4 = parse_format("""
    main = [
        header = [const u16 = 0xFFFF, version: u8],
        payload: [u8; 16],
        checksum: u32
    ]
    """)
    print(format4)



if __name__ == "__main__":
    main()