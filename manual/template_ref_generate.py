#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict

PREAMBLE = '''\
.. include:: global.rst

.. _templaterefcalibre:

Reference for all built-in template language functions
========================================================

Here, we document all the built-in functions available in the |app| template language. Every function is implemented as a class in python and you can click the source links to see the source code, in case the documentation is insufficient. The functions are arranged in logical groups by type.

.. contents::
    :depth: 2
    :local:

.. module:: calibre.utils.formatter_functions

'''

CATEGORY_TEMPLATE = '''\
{category}
{dashes}

'''

FUNCTION_TEMPLATE = '''\
{fs}
{hats}

.. autoclass:: {cn}

'''

POSTAMBLE = '''\

API of the Metadata objects
----------------------------

The python implementation of the template functions is passed in a Metadata object. Knowing it's API is useful if you want to define your own template functions.

.. module:: calibre.ebooks.metadata.book.base

.. autoclass:: Metadata
   :members:
   :member-order: bysource

.. data:: STANDARD_METADATA_FIELDS

    The set of standard metadata fields.

.. literalinclude:: ../src/calibre/ebooks/metadata/book/__init__.py
   :lines: 7-
'''


def generate_template_language_help():
    from calibre.utils.formatter_functions import formatter_functions

    funcs = defaultdict(dict)

    for func in formatter_functions().get_builtins().values():
        class_name = func.__class__.__name__
        func_sig = getattr(func, 'doc')
        x = func_sig.find(' -- ')
        if x < 0:
            print 'No sig for ', class_name
            continue
        func_sig = func_sig[:x]
        func_cat = getattr(func, 'category')
        funcs[func_cat][func_sig] = class_name

    output = PREAMBLE
    cats = sorted(funcs.keys())
    for cat in cats:
        output += CATEGORY_TEMPLATE.format(category=cat, dashes='-'*len(cat))
        entries = [k for k in sorted(funcs[cat].keys())]
        for entry in entries:
            output += FUNCTION_TEMPLATE.format(fs = entry, cn=funcs[cat][entry],
                                               hats='^'*len(entry))

    output += POSTAMBLE
    return output

if __name__ == '__main__':
    generate_template_language_help()
