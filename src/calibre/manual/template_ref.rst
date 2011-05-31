.. include:: global.rst

.. _templaterefcalibre:

Reference for all builtin template language functions
========================================================

Here, we document all the builtin functions available in the |app| template language. Every function is implemented as a class in python and you can click the source links to see the source code, in case the documentation is insufficient. The functions are arranged in logical groups by type.

.. contents::
    :depth: 2
    :local:

.. module:: calibre.utils.formatter_functions

Get values from metadata
--------------------------

field(name)
^^^^^^^^^^^^^^

.. autoclass:: BuiltinField

raw_field(name)
^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinRaw_field

booksize()
^^^^^^^^^^^^

.. autoclass:: BuiltinBooksize

format_date(val, format_string)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinFormat_date

ondevice()
^^^^^^^^^^^

.. autoclass:: BuiltinOndevice

Arithmetic
-------------

add(x, y)
^^^^^^^^^^^^^
.. autoclass:: BuiltinAdd

subtract(x, y)
^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinSubtract

multiply(x, y)
^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinMultiply

divide(x, y)
^^^^^^^^^^^^^^^

.. autoclass:: BuiltinDivide

Boolean
------------

and(value1, value2, ...)
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinAnd

or(value1, value2, ...)
^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinOr

not(value)
^^^^^^^^^^^^^

.. autoclass:: BuiltinNot

If-then-else
-----------------

contains(val, pattern, text if match, text if not match)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinContains

test(val, text if not empty, text if empty)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinTest

ifempty(val, text if empty)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinIfempty

Iterating over values
------------------------

first_non_empty(value, value, ...)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinFirstNonEmpty

lookup(val, pattern, field, pattern, field, ..., else_field)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinLookup

switch(val, pattern, value, pattern, value, ..., else_value)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinSwitch

List Lookup
---------------

in_list(val, separator, pattern, found_val, not_found_val)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinInList

str_in_list(val, separator, string, found_val, not_found_val)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinStrInList

list_item(val, index, separator)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinListitem

select(val, key)
^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinSelect


List Manipulation
-------------------

count(val, separator)
^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinCount

merge_lists(list1, list2, separator)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinMergeLists

sublist(val, start_index, end_index, separator)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinSublist

subitems(val, start_index, end_index)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinSubitems

Recursion
-------------

eval(template)
^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinEval

template(x)
^^^^^^^^^^^^

.. autoclass:: BuiltinTemplate

Relational
-----------

cmp(x, y, lt, eq, gt)
^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinCmp

strcmp(x, y, lt, eq, gt)
^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinStrcmp

String case changes
---------------------

lowercase(val)
^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinLowercase

uppercase(val)
^^^^^^^^^^^^^^^

.. autoclass:: BuiltinUppercase

titlecase(val)
^^^^^^^^^^^^^^^

.. autoclass:: BuiltinTitlecase

capitalize(val)
^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinCapitalize

String Manipulation
---------------------

re(val, pattern, replacement)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinRe

shorten(val, left chars, middle text, right chars)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinShorten

substr(str, start, end)
^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinSubstr


Other
--------

assign(id, val)
^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinAssign

print(a, b, ...)
^^^^^^^^^^^^^^^^^

.. autoclass:: BuiltinPrint


API of the Metadata objects
----------------------------

The python implementation of the template functions is passed in a Metadata object. Knowing it's API is useful if you want to define your own template functions.

.. module:: calibre.ebooks.metadata.book.base

.. autoclass:: Metadata
   :members:
   :member-order: bysource

.. data:: STANDARD_METADATA_FIELDS

    The set of standard metadata fields.

.. literalinclude:: ../ebooks/metadata/book/__init__.py
   :lines: 7-

