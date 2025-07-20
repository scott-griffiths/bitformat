"""Minimal lark stub to allow imports for testing"""

class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value

class Tree:
    def __init__(self, data, children=None):
        self.data = data
        self.children = children or []

class Lark:
    def __init__(self, grammar, parser='lalr', **kwargs):
        self.grammar = grammar
        
    def parse(self, text):
        # Minimal stub implementation
        return Tree('start', [])

class Transformer:
    pass

class v_args:
    def __init__(self, inline=False):
        self.inline = inline
    
    def __call__(self, f):
        return f

class UnexpectedInput(Exception):
    pass

class ParseError(Exception):
    pass