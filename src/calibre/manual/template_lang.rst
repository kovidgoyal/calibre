
.. include:: global.rst

.. _templatelangcalibre:

The |app| template language
=======================================================

The |app| template language is used in various places. It is used to control the folder structure and file name when saving files from the |app| library to the disk or eBook reader.
It is used to define "virtual" columns that contain data from other columns and so on.

In essence, the template language is very simple. The basic idea is that a template consists of names in curly brackets that are then replaced by the corresponding metadata from the book being processed. So, for example, the default template used for saving books to device in |app| is::

    {author_sort}/{title}/{title} - {authors}

For the book "The Foundation" by "Isaac Asimov" it will become::

    Asimov, Isaac/The Foundation/The Foundation - Isaac Asimov

You can use all the various metadata fields available in calibre in a template, including the custom columns you have created yourself. To find out the template name for a column sinply hover your mouse over the column header. Names for custom fields (columns you have created yourself) are always prefixed by an #. For series type fields, there is always an additional field named ``series_index`` that becomes the series index for that series. So if you have a custom series field named #myseries, there will also be a field named #myseries_index. In addition to the column based fields, you also can use::

    {formats} - A list of formats available in the |app| library for a book
    {isbn}    - The ISBN number of the book

If a particular book does not have a particular piece of metadata, the field in the template is automatically removed for that book. So for example::

    {author_sort}/{series}/{title} {series_index}

will become::

    {Asimov, Isaac}/Foundation/Second Foundation - 3

and if a book does not have a series::

    {Asimov, Isaac}/Second Foundation

(|app| automatically removes multiple slashes and leading or trailing spaces).


Advanced formatting
----------------------

You can do more than just simple substitution with the templates. You can also control how the substituted data is formatted. For instance, suppose you wanted to ensure that the series_index is always formatted as three digits with leading zeros. This would do the trick::

    {series_index:0>3s} - Three digits with leading zeros

If instead of leading zeros you want leading spaces, use::

   {series_index:>3s} - Thre digits with leading spaces

For trailing zeros, use::

   {series_index:0<3s} - Three digits with trailing zeros


If you want only the first two letters of the data to be rendered, use::

   {author_sort:.2} - Only the first two letter of the author sort name

The |app| template language comes from python and for more details on the syntax of these advanced formatting operations, look at the `Python documentation <http://docs.python.org/library/string.html#format-string-syntax>`_.

