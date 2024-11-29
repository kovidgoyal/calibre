#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict

PREAMBLE = '''\
.. _templaterefcalibre-{}:

Reference for all built-in template language functions
========================================================

Here, we document all the built-in functions available in the calibre template
language. Every function is implemented as a class in python and you can click
the source links to see the source code, in case the documentation is
insufficient. The functions are arranged in logical groups by type.

.. contents::
    :depth: 2
    :local:

.. module:: calibre.utils.formatter_functions

'''

POSTAMBLE = '''\

API of the Metadata objects
----------------------------

The python implementation of the template functions is passed in a Metadata
object. Knowing it's API is useful if you want to define your own template
functions.

.. module:: calibre.ebooks.metadata.book.base

.. autoclass:: Metadata
   :members:
   :member-order: bysource

.. data:: STANDARD_METADATA_FIELDS

    The set of standard metadata fields.

.. literalinclude:: ../../../src/calibre/ebooks/metadata/book/__init__.py
   :lines: 7-
'''


def generate_template_language_help(language, log):
    from tempfile import TemporaryDirectory

    from calibre.db.legacy import LibraryDatabase
    from calibre.utils.ffml_processor import FFMLProcessor
    from calibre.utils.formatter_functions import formatter_functions

    output = [PREAMBLE.format(language)]
    a = output.append

    with TemporaryDirectory() as tdir:
        db = LibraryDatabase(tdir) # needed to load formatter_funcs
        ffml = FFMLProcessor()
        all_funcs = formatter_functions().get_builtins()
        categories = defaultdict(dict)
        for name, func in all_funcs.items():
            category = func.category
            categories[category][name] = func
        for cat_name in sorted(categories):
            a(cat_name + '\n')
            a(('-' * (4*len(cat_name))) + '\n\n')
            for name in sorted(categories[cat_name]):
                func = categories[cat_name][name]
                a(f"\n\n.. _ff_{name}:\n\n{name}\n{'^'*len(name)}\n\n")
                a(f'.. class:: {func.__class__.__name__}\n\n')
                try:
                    a(ffml.document_to_rst(func.doc, name))
                except Exception as e:
                    if language in ('en', 'eng'):
                        raise
                    log.warn(f'Failed to process template language docs for {name} in the {language} language with error: {e}')
                    a('  TRANSLATION INVALID')
            a('\n\n')
        db.close()
        del db

    a(POSTAMBLE)
    return ''.join(output)

if __name__ == '__main__':
    generate_template_language_help()
