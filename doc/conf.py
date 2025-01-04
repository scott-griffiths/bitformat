# Configuration file for the Sphinx documentation builder.
#
import os
import time
import datetime
import sys

sys.path.insert(0, os.path.abspath(".."))

year = datetime.datetime.utcfromtimestamp(
    int(os.environ.get("SOURCE_DATE_EPOCH", time.time()))
).year

project = "bitformat"
copyright = f"2024 - {year}, Scott Griffiths"
author = "Scott Griffiths"
release = "0.2.0"

extensions = ["sphinx.ext.autodoc"]
autoapi_dirs = ["../bitformat/"]
autoapi_add_toctree_entry = False
autodoc_mock_imports = ["bit_rust", "lark"]

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
    "banner_text": "bitformat is currently in alpha. This documentation may be inaccurate.",
    "banner_hiding": "permanent",
    "show_theme_credit": False,
    "globaltoc_maxdepth": 3,
    "source_url": "https://github.com/scott-griffiths/bitformat/",
}

html_logo = "./bitformat_logo_small_white.png"
