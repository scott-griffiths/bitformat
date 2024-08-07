# Configuration file for the Sphinx documentation builder.
#
import os
import time
import datetime
import sys

sys.path.insert(0, os.path.abspath('..'))

year = datetime.datetime.utcfromtimestamp(
    int(os.environ.get('SOURCE_DATE_EPOCH', time.time()))
).year

project = 'bitformat'
copyright = f'2024 - {year}, Scott Griffiths'
author = 'Scott Griffiths'
release = '0.1.0'

extensions = ['sphinx.ext.autodoc', 'autoapi.extension']
autoapi_dirs = ['../bitformat']
autoapi_options = ['members',
                   'undoc-members',
                   # 'show-inheritance',
                   'show-module-summary',
                   'special-members',
                   'imported-members',
                   ]
autoapi_own_page_level = 'class'
autoapi_add_toctree_entry = False

skipped = ['Bits.__gt__', 'Bits.__lt__', 'Bits.__ge__', 'Bits.__le__',
           '__slots__']

def skip_things(app, what, name, obj, skip, options):
    if 'slot' in name:
        print(name)
    if name in skipped:
        skip = True
    return skip

def setup(sphinx):
    sphinx.connect("autoapi-skip-member", skip_things)


add_module_names = False

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

root_doc = 'index'

add_function_parentheses = False

html_show_sphinx = False
html_static_path = ['_static']
html_css_files = ["custom.css"]

html_theme = 'piccolo_theme'

html_theme_options = {
    "banner_text": "bitformat is in a pre-alpha planning stage. This documentation is wildly inaccurate.",
    "banner_hiding": "permanent",
    "show_theme_credit": False,
    "globaltoc_maxdepth": 2,
    "source_url": 'https://github.com/scott-griffiths/bitformat/',
}

html_logo = './bitformat_logo_small_white.png'
