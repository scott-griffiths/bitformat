# Configuration file for the Sphinx documentation builder.
#
import os
import time
import datetime
from inspect import Parameter, Signature

from bitformat import Mutibs as _Mutibs, Tibs as _Tibs
from bitformat._version import VERSION

year = datetime.datetime.utcfromtimestamp(
    int(os.environ.get("SOURCE_DATE_EPOCH", time.time()))
).year

project = "bitformat"
copyright = f"2024 - {year}, Scott Griffiths"
author = "Scott Griffiths"
release = VERSION

extensions = [
    "sphinx.ext.autodoc",
    "sphinxcontrib.mermaid",
    'enum_tools.autoenum',
    'sphinx_autodoc_typehints',
]
autoapi_dirs = ["../bitformat/"]
autoapi_add_toctree_entry = False
autodoc_mock_imports = ["lark"]

add_module_names = False

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

root_doc = "index"

add_function_parentheses = False

html_show_sphinx = False
html_static_path = ["_static"]
html_css_files = ["custom.css"]

html_theme = "piccolo_theme"

html_theme_options = {
    # "banner_text": "bitformat is currently in beta. This documentation may be inaccurate.",
    "banner_hiding": "permanent",
    "show_theme_credit": False,
    "globaltoc_collapse": False,
    "source_url": "https://github.com/scott-griffiths/bitformat/",
}

html_logo = "./bitformat_logo_small.png"
html_favicon = "./logo.png"

_from_dtype_docs_signature = Signature([
    Parameter("self", Parameter.POSITIONAL_ONLY),
    Parameter("cls", Parameter.POSITIONAL_ONLY),
    Parameter("dtype", Parameter.POSITIONAL_ONLY),
    Parameter("value", Parameter.POSITIONAL_ONLY),
])
for _cls in (_Tibs, _Mutibs):
    _cls.__dict__["from_dtype"].__func__.__signature__ = _from_dtype_docs_signature


def _process_signature(app, what, name, obj, options, signature, return_annotation):
    # These are patched onto tibs.Tibs/tibs.Mutibs as classmethods. Sphinx sees
    # them as already-bound methods and would otherwise drop the dtype argument.
    if name in {"bitformat.Tibs.from_dtype", "bitformat.Mutibs.from_dtype"}:
        return "(cls, dtype, value, /)", return_annotation
    return signature, return_annotation


def _process_docstring(app, what, name, obj, options, lines):
    # These methods are inherited directly from tibs. Their docstrings refer to
    # tibs.Endianness, while bitformat has its own dtype Endianness enum.
    if name in {
        "bitformat.Tibs.from_u",
        "bitformat.Tibs.from_i",
        "bitformat.Tibs.from_f",
        "bitformat.Tibs.view",
        "bitformat.Tibs.be",
        "bitformat.Tibs.le",
        "bitformat.Mutibs.from_u",
        "bitformat.Mutibs.from_i",
        "bitformat.Mutibs.from_f",
        "bitformat.Mutibs.view",
        "bitformat.Mutibs.be",
        "bitformat.Mutibs.le",
    }:
        for i, line in enumerate(lines):
            lines[i] = (
                line
                .replace(":param Endianness byte_order:", ":param tibs.Endianness byte_order:")
                .replace("Endianness.Unspecified", "tibs.Endianness.Unspecified")
                .replace("Endianness.Little", "tibs.Endianness.Little")
                .replace("Endianness.Big", "tibs.Endianness.Big")
            )


def setup(app):
    app.connect("autodoc-process-signature", _process_signature)
    app.connect("autodoc-process-docstring", _process_docstring)
