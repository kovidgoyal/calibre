
.. include:: global.rst

.. _templatelangcalibre:

The |app| template language
=======================================================

The |app| template language is used in various places. It is used to control the folder structure and file name when saving files from the |app| library to the disk or eBook reader.
It is also used to define "virtual" columns that contain data from other columns and so on.

The basic template language is very simple, but has very powerful advanced features. The basic idea is that a template consists of names in curly brackets that are then replaced by the corresponding metadata from the book being processed. So, for example, the default template used for saving books to device in |app| is::

    {author_sort}/{title}/{title} - {authors}

For the book "The Foundation" by "Isaac Asimov" it will become::

    Asimov, Isaac/The Foundation/The Foundation - Isaac Asimov

You can use all the various metadata fields available in calibre in a template, including any custom columns you have created yourself. To find out the template name for a column simply hover your mouse over the column header. Names for custom fields (columns you have created yourself) always have a # as the first character. For series type custom fields, there is always an additional field named ``#seriesname_index`` that becomes the series index for that series. So if you have a custom series field named ``#myseries``, there will also be a field named ``#myseries_index``.

In addition to the column based fields, you also can use::

    {formats} - A list of formats available in the calibre library for a book
    {isbn}    - The ISBN number of the book

If a particular book does not have a particular piece of metadata, the field in the template is automatically removed for that book. Consider, for example::

    {author_sort}/{series}/{title} {series_index}

If a book has a series, the template will produce::

    {Asimov, Isaac}/Foundation/Second Foundation - 3

and if a book does not have a series::

    {Asimov, Isaac}/Second Foundation

(|app| automatically removes multiple slashes and leading or trailing spaces).


Advanced formatting
----------------------

You can do more than just simple substitution with the templates. You can also conditionally include text and control how the substituted data is formatted.

First, conditionally including text. There are cases where you might want to have text appear in the output only if a field is not empty. A common case is ``series`` and ``series_index``, where you want either nothing or the two values with a hyphen between them. Calibre handles this case using a special field syntax.

For example, assume you want to use the template::

        {series} - {series_index} - {title}

If the book has no series, the answer will be ``- - title``. Many people would rather the result be simply ``title``, without the hyphens. To do this, use the extended syntax ``{field:|prefix_text|suffix_text}``. When you use this syntax, if field has the value SERIES then the result will be ``prefix_textSERIESsuffix_text``. If field has no value, then the result will be the empty string (nothing); the prefix and suffix are ignored. The prefix and suffix can contain blanks.

Using this syntax, we can solve the above series problem with the template::

        {series}{series_index:| - | - }{title}

The hyphens will be included only if the book has a series index, which it will have only if it has a series.

Notes: you must include the : character if you want to use a prefix or a suffix. You must either use no \| characters or both of them; using one, as in ``{field:| - }``, is not allowed. It is OK not to provide any text for one side or the other, such as in ``{series:|| - }``. Using ``{title:||}`` is the same as using ``{title}``.

Second: formatting. Suppose you wanted to ensure that the series_index is always formatted as three digits with leading zeros. This would do the trick::

    {series_index:0>3s} - Three digits with leading zeros

If instead of leading zeros you want leading spaces, use::

   {series_index:>3s} - Three digits with leading spaces

For trailing zeros, use::

   {series_index:0<3s} - Three digits with trailing zeros


If you want only the first two letters of the data, use::

   {author_sort:.2} - Only the first two letter of the author sort name

The |app| template language comes from python and for more details on the syntax of these advanced formatting operations, look at the `Python documentation <http://docs.python.org/library/string.html#format-string-syntax>`_.

Advanced features
------------------

Using templates in custom columns
----------------------------------

There are sometimes cases where you want to display metadata that |app| does not normally display, or to display data in a way different from how |app| normally does. For example, you might want to display the ISBN, a field that |app| does not display. You can use custom columns for this by creating a column with the type 'column built from other columns' (hereafter called composite columns), and entering a template. Result: |app| will display a column showing the result of evaluating that template. To display the ISBN, create the column and enter ``{isbn}`` into the template box. To display a column containing the values of two series custom columns separated by a comma, use ``{#series1:||,}{#series2}``.

Composite columns can use any template option, including formatting.

You cannot change the data contained in a composite column. If you edit a composite column by double-clicking on any item, you will open the template for editing, not the underlying data. Editing the template on the GUI is a quick way of testing and changing composite columns.

Using functions in templates
-----------------------------

Suppose you want to display the value of a field in upper case, when that field is normally in title case. You can do this (and many more things) using the functions available for templates. For example, to display the title in upper case, use ``{title:uppercase()}``. To display it in title case, use ``{title:titlecase()}``.

Function references replace the formatting specification, going after the : and before the first ``|`` or the closing ``}``. Functions must always end with ``()``. Some functions take extra values (arguments), and these go inside the ``()``.

The syntax for using functions is ``{field:function(arguments)}``, or ``{field:function(arguments)|prefix|suffix}``. Argument values cannot contain a comma, because it is used to separate arguments. The last (or only) argument cannot contain a closing parenthesis ( ')' ). Functions return the value of the field used in the template, suitably modified.

The functions available are:

    * ``lowercase()``	-- return value of the field in lower case.
    * ``uppercase()``	-- return the value of the field in upper case.
    * ``titlecase()``	-- return the value of the field in title case.
    * ``capitalize()``	-- return the value as capitalized.
    * ``ifempty(text)``	-- if the field is not empty, return the value of the field. Otherwise return `text`.
    * ``test(text if not empty, text if empty)`` -- return `text if not empty` if the field is not empty, otherwise return `text if empty`.
    * ``contains(pattern, text if match, text if not match`` -- checks if field contains matches for the regular expression `pattern`. Returns `text if match` if matches are found, otherwise it returns `text if no match`.
    * ``shorten(left chars, middle text, right chars)`` -- Return a shortened version of the field, consisting of `left chars` characters from the beginning of the field, followed by `middle text`, followed by `right chars` characters from the end of the string. `Left chars` and `right chars` must be integers. For example, assume the title of the book is `Ancient English Laws in the Times of Ivanhoe`, and you want it to fit in a space of at most 15 characters. If you use ``{title:shorten(9,-,5)}``, the result will be `Ancient E-nhoe`. If the field's length is less than ``left chars`` + ``right chars`` + the length of ``middle text``, then the field will be used intact. For example, the title `The Dome` would not be changed.
    * ``lookup(field if not empty, field if empty)`` -- like test, except the arguments are field (metadata) names, not text. The value of the appropriate field will be fetched and used. Note that because composite columns are fields, you can use this function in one composite field to use the value of some other composite field. This is extremely useful when constructing variable save paths (more later).
    * ``re(pattern, replacement)`` -- return the field after applying the regular expression. All instances of `pattern` are replaced with `replacement`. As in all of |app|, these are python-compatible regular expressions.

Special notes for save/send templates
-------------------------------------

Special processing is applied when a template is used in a `save to disk` or `send to device` template. The values of the fields are cleaned, replacing characters that are special to file systems with underscores, including slashes. This means that field text cannot be used to create folders. However, slashes are not changed in prefix or suffix strings, so slashes in these strings will cause folders to be created. Because of this, you can create variable-depth folder structure.

For example, assume we want the folder structure `series/series_index - title`, with the caveat that if series does not exist, then the title should be in the top folder. The template to do this is::

    {series:||/}{series_index:|| - }{title}

The slash and the hyphen appear only if series is not empty.

The lookup function lets us do even fancier processing. For example, assume we want the following: if a book has a series, then we want the folder structure `series/series index - title.fmt`. If the book does not have a series, then we want the folder structure `genre/author_sort/title.fmt`. If the book has no genre, use 'Unknown'. We want two completely different paths, depending on the value of series.

To accomplish this, we:
    1. Create a composite field (call it AA) containing ``{series:||}/{series_index} - {title'}``. If the series is not empty, then this template will produce `series/series_index - title`.
    2. Create a composite field (call it BB) containing ``{#genre:ifempty(Unknown)}/{author_sort}/{title}``. This template produces `genre/author_sort/title`, where an empty genre is replaced wuth `Unknown`.
    3. Set the save template to ``{series:lookup(AA,BB)}``. This template chooses composite field AA if series is not empty, and composite field BB if series is empty. We therefore have two completely different save paths, depending on whether or not `series` is empty.


