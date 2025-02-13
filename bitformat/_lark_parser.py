from lark import Lark, Transformer
from bitformat import Format, Field, DtypeName, DtypeSingle, Dtype, DtypeArray, Pass, Repeat, Expression
from typing import List, Union, Any


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

    def expression(self, items):
        x = Expression('{' + items[0] + '}')
        return x

    def repeat(self, items):
        expr = items[0]
        count = expr.evaluate()
        return Repeat.from_params(count, items[1])

    def pass_(self, items):
        return Pass()

    def if_(self, items):
        pass

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
        return DtypeArray.from_params(dtype.name, dtype.size, items_count, dtype.endianness)

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
#
# def parse_format(format_string: str) -> Format:
#     """
#     Parse a format string and return a Format object.
#
#     Args:
#         format_string: The format string to parse
#
#     Returns:
#         A Format object representing the parsed format
#
#     """
#     parser = Lark(GRAMMAR, start='format', parser='earley')
#     transformer = FormatTransformer()
#     tree = parser.parse(format_string)
#     return transformer.transform(tree)
