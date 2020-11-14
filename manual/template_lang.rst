.. _templatelangcalibre:

The calibre template language
=======================================================

The calibre template language is used in various places. It is used to control the folder structure and file name when saving files from the calibre library to the disk or e-book reader.
It is also used to define "virtual" columns that contain data from other columns and so on.

The basic template language is simple but has  powerful advanced features. A template consists of text and names in curly brackets that are then replaced by the corresponding metadata from the book being processed. For example, the default template used for saving books to device in calibre is::

    {author_sort}/{title}/{title} - {authors}

For the book "The Foundation" by "Isaac Asimov" it will become::

    Asimov, Isaac/The Foundation/The Foundation - Isaac Asimov

The slashes are text, which is put into the template where it appears. For example, if your template is::

    {author_sort} Some Important Text {title}/{title} - {authors}

For the book "The Foundation" by "Isaac Asimov" it will become::

    Asimov, Isaac Some Important Text The Foundation/The Foundation - Isaac Asimov

You can use all the metadata fields available in calibre in a template, including any custom columns you have created, by using its 'lookup name'. To find the lookup name for a column (field) hover your mouse over the column header. Names for custom columns (columns you have created yourself) always have a # as the first character. For series type custom columns there is always an additional field named ``#seriesname_index`` that is the series index for that series. So if you have a custom series field named ``#myseries``, there will also be a field named ``#myseries_index``.

In addition to the column based fields, you also can use::

    {formats} - A list of formats available in the calibre library for a book
    {identifiers:select(isbn)} - The ISBN of the book

If a book does not have a particular piece of metadata, the field in the template is replaced by the empty string for that book. Consider, for example::

    {author_sort}/{series}/{title} {series_index}

If a book has a series, the template will produce::

    Asimov, Isaac/Foundation/Second Foundation 3

and if a book does not have a series::

    Asimov, Isaac/Second Foundation

(calibre automatically removes multiple slashes and leading or trailing spaces).

Advanced formatting
----------------------

You can do more than just simple substitution with the templates. You can also conditionally include text and control how the substituted data is formatted.

First, conditionally including text. There are cases where you might want to have text appear in the output only if a field is not empty. A common case is ``series`` and ``series_index``, where you want either nothing or the two values with a hyphen between them. calibre handles this case using a special field syntax.

For example, assume you want to use the template::

        {series} - {series_index} - {title}

If the book has no series, the answer will be ``- - title``. Most people would rather the result be simply ``title``, without the hyphens. To do this, use the extended syntax ``{field:|prefix_text|suffix_text}``. When you use this syntax, if field has the value SERIES then the result will be ``prefix_textSERIESsuffix_text``. If field has no value, then the result will be the empty string (nothing); the prefix and suffix are ignored. The prefix and suffix can contain blanks. **Do not use subtemplates (`{ ... }`) or functions (see below) as the prefix or the suffix.**

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

If you use series indices with sub values (e.g., 1.1), you might want to ensure that the decimal points line up. For example, you might want the indices 1 and 2.5 to appear as 01.00 and 02.50 so that they will sort correctly. To do this, use::

   {series_index:0>5.2f} - Five characters, consisting of two digits with leading zeros, a decimal point, then 2 digits after the decimal point

If you want only the first two letters of the data, use::

   {author_sort:.2} - Only the first two letter of the author sort name

The calibre template language comes from Python and for more details on the syntax of these advanced formatting operations, look at the `Python documentation <https://docs.python.org/library/string.html#format-string-syntax>`_.


Using templates in custom columns
----------------------------------

Sometimes you want to display metadata in the book list that calibre does not normally display, or to display data in a way different from how calibre normally does. For example, you might want to display the ISBN, a field that calibre does not display. You can use custom columns for this by creating a column with the type 'column built from other columns' (hereafter called composite columns), and entering a template. Result: calibre will display a column showing the result of evaluating that template. To display the ISBN, create the column and enter ``{identifiers:select(isbn)}`` into the template box. To display a column containing the values of two series custom columns separated by a comma, use ``{#series1:||,}{#series2}``.

Composite columns can use any template option, including formatting.

You cannot edit the data displayed in a composite column. If you edit a composite column, for example by double-clicking it, you will open the template for editing, not the underlying data. Editing the template on the GUI is a quick way of testing and changing composite columns.

Using functions in templates - Single Function Mode
---------------------------------------------------

Suppose you want to display the value of a field in upper case, when that field is normally in title case. You can do this (and many more things) using the functions available for templates. For example, to display the title in upper case, use ``{title:uppercase()}``. To display it in title case, use ``{title:titlecase()}``.

Functions appear in the format part, going after the ``:`` and before the first ``|`` or the closing ``}``. If you have both a format and a function reference, the function comes after another ``:``. Functions must always end with ``()``. Some functions take extra values (arguments), and these go inside the ``()``.

Functions are always applied before format specifications. See further down for an example of using both a format and a function, where this order is demonstrated.

The syntax for using functions is ``{field:function(arguments)}``, or ``{field:function(arguments)|prefix|suffix}``. Arguments are separated by commas. Commas inside arguments must be preceded by a backslash ( ``\`` ). The last (or only) argument cannot contain a closing parenthesis ( ``)`` ). Functions return the value of the field used in the template, suitably modified.

Important: If you have programming experience, please note that the syntax in this mode (single function) is not what you might expect. Strings are not quoted. Spaces are significant. All arguments must be constants; there is no sub-evaluation. **Do not use subtemplates (`{ ... }`) as function arguments.** Instead, use :ref:`Template Program Mode <template_mode>` and :ref:`General Program Mode <general_mode>`.

Many functions use regular expressions. In all cases, regular expression matching is case-insensitive.

The functions available are listed below. Note that the definitive documentation for functions is available in the section :ref:`Function reference <template_functions_reference>`:

    * ``lowercase()``	-- return value of the field in lower case.
    * ``uppercase()``	-- return the value of the field in upper case.
    * ``titlecase()``	-- return the value of the field in title case.
    * ``capitalize()``	-- return the value with the first letter upper case and the rest lower case.
    * ``contains(pattern, text if match, text if not match)`` -- checks if field contains matches for the regular expression `pattern`. Returns `text if match` if matches are found, otherwise it returns `text if no match`.
    * ``count(separator)`` -- interprets the value as a list of items separated by `separator`, returning the number of items in the list. Most lists use a comma as the separator, but authors uses an ampersand. Examples: `{tags:count(,)}`, `{authors:count(&)}`
    * ``format_number(template)`` -- interprets the field as a number and format that number using a Python formatting template such as "{0:5.2f}" or "{0:,d}" or "${0:5,.2f}". The field_name part of the template must be a 0 (zero) (the "{0:" in the above examples). You can leave off the leading "{0:" and trailing "}" if the template contains only a format. See the template language and Python documentation for more examples. Returns the empty string if formatting fails.
    * ``human_readable()`` -- expects the value to be a number and returns a string representing that number in KB, MB, GB, etc.
    * ``ifempty(text)`` -- if the field is not empty, return the value of the field. Otherwise return `text`.
    * ``in_list(separator, pattern, found_val, ..., not_found_val)`` -- interpret the field as a list of items separated by `separator`, evaluating the `pattern` against each value in the list. If the `pattern` matches a value, return `found_val`, otherwise return `not_found_val`. The `pattern` and `found_value` can be repeated as many times as desired, permitting returning different values depending on the search. The patterns are checked in order. The first match is returned.
    * ``language_codes(lang_strings)`` -- return the language codes for the strings passed in `lang_strings`. The strings must be in the language of the current locale. `Lang_strings` is a comma-separated list.
    * ``language_strings(lang_codes, localize)`` -- return the strings for the language codes passed in `lang_codes`. If `localize` is zero, return the strings in English. If localize is not zero, return the strings in the language of the current locale. `Lang_codes` is a comma-separated list.
    * ``list_item(index, separator)`` -- interpret the field as a list of items separated by `separator`, returning the `index`th item. The first item is number zero. The last item can be returned using `list_item(-1,separator)`. If the item is not in the list, then the empty value is returned. The separator has the same meaning as in the `count` function.
    * ``lookup(pattern, field, pattern, field, ..., else_field)`` -- like switch, except the arguments are field (metadata) names, not text. The value of the appropriate field will be fetched and used. Note that because composite columns are fields, you can use this function in one composite field to use the value of some other composite field. This is extremely useful when constructing variable save paths (more later).
    * ``rating_to_stars(use_half_stars)`` -- Returns the rating as string of star characters. The source value must be a number between 0 and 5. Set use_half_stars to 1 if you want half star characters for custom ratings columns that are not integers, for example 2.5.
    * ``re(pattern, replacement)`` -- return the field after applying the regular expression. All instances of `pattern` are replaced with `replacement`. As in all of calibre, these are Python-compatible regular expressions.
    * ``select(key)`` -- interpret the field as a comma-separated list of items, with the items being of the form "id:value". Find the pair with the id equal to key, and return the corresponding value. This function is particularly useful for extracting a value such as an ISBN from the set of identifiers for a book.
    * ``shorten(left chars, middle text, right chars)`` -- Return a shortened version of the field, consisting of `left chars` characters from the beginning of the field, followed by `middle text`, followed by `right chars` characters from the end of the string. `Left chars` and `right chars` must be integers. For example, assume the title of the book is `Ancient English Laws in the Times of Ivanhoe`, and you want it to fit in a space of at most 15 characters. If you use ``{title:shorten(9,-,5)}``, the result will be `Ancient E-nhoe`. If the field's length is less than ``left chars`` + ``right chars`` + the length of ``middle text``, then the field will be used intact. For example, the title `The Dome` would not be changed.
    * ``str_in_list(separator, string, found_val, ..., not_found_val)`` -- interpret the field as a list of items separated by `separator`, comparing the `string` against each value in the list. If the `string` matches a value (ignoring case), return `found_val`, otherwise return `not_found_val`. If the string contains separators, then it is also treated as a list and each value is checked. The `string` and `found_value` can be repeated as many times as desired, permitting returning different values depending on the search. The strings are checked in order. The first match is returned.
    * ``subitems(start_index, end_index)`` -- This function is used to break apart lists of tag-like hierarchical items such as genres. It interprets the field as a comma-separated list of tag-like items, where each item is a period-separated list. Returns a new list made by first finding all the period-separated tag-like items, then for each such item extracting the components from `start_index` to `end_index`, then combining the results back together. The first component in a period-separated list has an index of zero. If an index is negative, then it counts from the end of the list. As a special case, an end_index of zero is assumed to be the length of the list. Examples::

        Assuming a #genre column containing "A.B.C":
            {#genre:subitems(0,1)} returns "A"
            {#genre:subitems(0,2)} returns "A.B"
            {#genre:subitems(1,0)} returns "B.C"
        Assuming a #genre column containing "A.B.C, D.E":
            {#genre:subitems(0,1)} returns "A, D"
            {#genre:subitems(0,2)} returns "A.B, D.E"

    * ``sublist(start_index, end_index, separator)`` -- interpret the field as a list of items separated by `separator`, returning a new list made from the items from `start_index` to `end_index`. The first item is number zero. If an index is negative, then it counts from the end of the list. As a special case, an end_index of zero is assumed to be the length of the list. Examples assuming that the tags column (which is comma-separated) contains "A, B ,C"::

        {tags:sublist(0,1,\,)} returns "A"
        {tags:sublist(-1,0,\,)} returns "C"
        {tags:sublist(0,-1,\,)} returns "A, B"

    * ``swap_around_articles(separator)`` -- returns the val with articles moved to the end. The value can be a list, in which case each member of the list is processed. If the value is a list then you must provide the list value separator. If no separator is provided then the value is treated as being a single value, not a list.
    * ``swap_around_comma()`` -- given a field with a value of the form ``B, A``, return ``A B``. This is most useful for converting names in LN, FN format to FN LN. If there is no comma, the function returns val unchanged.
    * ``switch(pattern, value, pattern, value, ..., else_value)`` -- for each ``pattern, value`` pair, checks if the field matches the regular expression ``pattern`` and if so, returns that ``value``. If no ``pattern`` matches, then ``else_value`` is returned. You can have as many ``pattern, value`` pairs as you want.
    * ``test(text if not empty, text if empty)`` -- return `text if not empty` if the field is not empty, otherwise return `text if empty`.
    * ``transliterate()`` -- Returns a string in a latin alphabet formed by approximating the sound of the words in the source field. For example, if the source field is ``Фёдор Миха́йлович Достоевский`` the function returns ``Fiodor Mikhailovich Dostoievskii``.'

Now, what about using functions and formatting in the same field. Suppose you have an integer custom column called ``#myint`` that you want to see with leading zeros, as in ``003``. To do this, you would use a format of ``0>3s``. However, by default, if a number (integer or float) equals zero then the field produces the empty value, so zero values will produce nothing, not ``000``. If you really want to see ``000`` values, then you use both the format string and the ``ifempty`` function to change the empty value back to a zero. The field reference would be::

    {#myint:0>3s:ifempty(0)}

Note that you can use the prefix and suffix as well. If you want the number to appear as ``[003]`` or ``[000]``, then use the field::

    {#myint:0>3s:ifempty(0)|[|]}

.. _template_mode:

More complex functions in templates - Template Program Mode
-------------------------------------------------------------

Template Program Mode differs from Single Function Mode in that it permits writing template expressions that refer to other metadata fields, use nested functions, modify values, and do arithmetic. It is a reasonably complete programming language.

You can use the functions documented above in Template Program Mode. See below for details.

Beginning with an example, assume you want your template to show the series for a book if it has one, otherwise show the value of a custom field #genre. You cannot do this in the basic template language because you cannot make reference to another metadata field within a template expression. In Template Program Mode, you can. The following expression works::

    {#series:'ifempty($, field('#genre'))'}

The example shows several things:

    * Template Program Mode is used if the expression begins with ``:'`` and ends with ``'``. Anything else is assumed to be in single function mode.
    * the variable ``$`` stands for the field the expression is operating upon, ``#series`` in this case.
    * functions must be given all their arguments. There is no default value. For example, the standard built-in functions must be given an additional initial parameter indicating the source field, which is a significant difference from single-function mode.
    * white space is ignored and can be used anywhere within the expression.
    * constant strings are enclosed in matching quotes, either ``'`` or ``"``.

The syntax of the language is shown by the following grammar. For a discussion of 'compare','if_expression', and 'template_call' see :ref:`General Program Mode <general_mode>`:::

    program         ::= expression_list
    expression_list ::= expression [ ';' expression ]*
    expression      ::= identifier | constant | function | assignment | compare | if_expression
    function        ::= identifier '(' expression [ ',' expression ]* ')'
    compare         ::= expression compare_op expression
    compare_op      ::= '==' | '!=' | '>=' | '>' | '<=' | '<' | '==#' | '!=#' | '>=#' | '>#' | '<=#' | '<#'
    if_expression   ::= 'if' expression 'then' expression_list [elif_expression] ['else' expression_list] 'fi'
    elif_expression ::= 'elif' expression 'then' expression_list elif_expression | ''
    assignment      ::= identifier '=' expression
    constant        ::= " string " | ' string ' | number
    identifier      ::= sequence of letters or ``_`` characters

Comments are lines with a '#' character at the beginning of the line.

An ``expression`` without errors always has a value. The value of an ``expression_list`` is the value of the last expression in the list. As such, the value of the program (expression_list)::

    1; 2; 'foobar'; 3

is 3.

Another example of a complex but rather silly program might help make things clearer::

    {series_index:'
        substr(
            strcat($, '->',
                cmp(divide($, 2), 1,
                    assign(c, 1); substr('lt123', c, 0),
                    'eq', 'gt')),
            0, 6)
       '| prefix | suffix}

This program does the following:

    * specify that the field being looked at is series_index. The variable ``$`` is set to its value.
    * calls the ``substr`` function, which takes 3 parameters ``(str, start, end)``. It returns a string formed by extracting the start through end characters from string, zero-based (the first character is character zero). In this case the string will be computed by the ``strcat`` function, the start is 0, and the end is 6. In this case it will return the first 6 characters of the string returned by ``strcat``, which must be evaluated before substr can return.
    * calls the ``strcat`` (string concatenation) function. Strcat accepts 1 or more arguments, and returns a string formed by concatenating all the values. In this case there are three arguments. The first parameter is the value in ``$``, which here is the value of ``series_index``. The second paremeter is the constant string ``'->'``. The third parameter is the value returned by the ``cmp`` function, which must be fully evaluated before ``strcat`` can return.
    * The ``cmp`` function takes 5 arguments ``(x, y, lt, eq, gt)``. It compares x and y and returns the third argument ``lt`` if x < y, the fourth argument ``eq`` if x == y, and the fifth argument ``gt`` if x > y. As with all functions, all of the parameters can be statements. In this case the first parameter (the value for ``x``) is the result of dividing the series_index by 2. The second parameter ``y`` is the constant ``1``. The third parameter ``lt`` is a statement (more later). The fourth parameter ``eq`` is the constant string ``'eq'``. The fifth parameter is the constant string ``'gt'``.
    * The third parameter (the one for ``lt``) is a statement, or a sequence of expressions. Remember that a statement (a sequence of semicolon-separated expressions) is also an expression, returning the value of the last expression in the list. In this case, the program first assigns the value ``1`` to a local variable ``c``, then returns a substring made by extracting the c'th character to the end. Since c always contains the constant ``1``, the substring will return the second through end'th characters, or ``'t123'``.
    * Once the statement providing the value to the third parameter is executed, ``cmp`` can return a value. At that point, ``strcat` can return a value, then ``substr`` can return a value. The program then terminates.

For various values of series_index, the program returns:

    * series_index == undefined, result = ``prefix ->t123 suffix``
    * series_index == 0.5, result = ``prefix 0.50-> suffix``
    * series_index == 1, result = ``prefix 1->t12 suffix``
    * series_index == 2, result = ``prefix 2->eq suffix``
    * series_index == 3, result = ``prefix 3->gt suffix``

**All the functions listed under single-function mode can be used in program mode**. To do so, you must supply the value that the function is to act upon as the first parameter in addition to the parameters documented above. For example, in program mode the parameters of the `test` function are ``test(x, text_if_not_empty, text_if_empty)``. The `x` parameter, which is the value to be tested, will almost always be a variable or a function call, often `field()`.

The following functions are available in addition to those described in single-function mode. Remember from the example above that the single-function mode functions require an additional first parameter specifying the field to operate on. With the exception of the ``id`` parameter of assign, all parameters can be statements (sequences of expressions). Note that the definitive documentation for functions is available in the section :ref:`Function reference <template_functions_reference>`:

    * ``and(value, value, ...)`` -- returns the string "1" if all values are not empty, otherwise returns the empty string. This function works well with test or first_non_empty. You can have as many values as you want.
    * ``add(x, y)`` -- returns x + y. Throws an exception if either x or y are not numbers.
    * ``assign(id, val)`` -- assigns val to id, then returns val. id must be an identifier, not an expression
    * ``approximate_formats()`` -- return a comma-separated list of formats that at one point were associated with the book. There is no guarantee that the list is correct, although it probably is. This function can be called in Template Program Mode using the template ``{:'approximate_formats()'}``. Note that format names are always uppercase, as in EPUB.
    * ``author_links(val_separator, pair_separator)`` -- returns a string containing a list of authors and that author's link values in the form ``author1 val_separator author1link pair_separator author2 val_separator author2link`` etc. An author is separated from its link value by the ``val_separator`` string with no added spaces. ``author:linkvalue`` pairs are separated by the ``pair_separator`` string argument with no added spaces. It is up to you to choose separator strings that do not occur in author names or links. An author is included even if the author link is empty.
    * ``author_sorts(val_separator)`` -- returns a string containing a list of author's sort values for the authors of the book. The sort is the one in the author metadata (different from the author_sort in books). The returned list has the form author sort 1 ``val_separator`` author sort 2 etc. The author sort values in this list are in the same order as the authors of the book. If you want spaces around ``val_separator`` then include them in the separator string
    * ``booksize()`` -- returns the value of the calibre 'size' field. Returns '' if there are no formats.
    * ``check_yes_no(field_name, is_undefined, is_false, is_true)`` -- checks the value of the yes/no field named by the lookup key ``field_name`` for a value specified by the parameters, returning "yes" if a match is found, otherwise returning an empty string. Set the parameter ``is_undefined``, ``is_false``, or ``is_true`` to 1 (the number) to check that condition, otherwise set it to 0. Example::

            check_yes_no("#bool", 1, 0, 1)

      returns "yes" if the yes/no field ``"#bool"`` is either undefined (neither True nor False) or True. More than one of ``is_undefined``, ``is_false``, or ``is_true`` can be set to 1.  This function is usually used by the ``test()`` or ``is_empty()`` functions.
    * ``ceiling(x)`` -- returns the smallest integer greater than or equal to x. Throws an exception if x is not a number.
    * ``cmp(x, y, lt, eq, gt)`` -- compares x and y after converting both to numbers. Returns ``lt`` if x < y. Returns ``eq`` if x == y. Otherwise returns ``gt``.
    * ``connected_device_name(storage_location)`` -- if a device is connected then return the device name, otherwise return the empty string. Each storage location on a device can have a different name. The location names are 'main', 'carda' and 'cardb'. This function works only in the GUI.
    * ``current_library_name()`` -- return the last name on the path to the current calibre library. This function can be called in Template Program Mode using the template ``{:'current_library_name()'}``.
    * ``current_library_path()`` -- return the path to the current calibre library. This function can be called in Template Program Mode using the template ``{:'current_library_path()'}``.
    * ``days_between(date1, date2)`` -- return the number of days between ``date1`` and ``date2``. The number is positive if ``date1`` is greater than ``date2``, otherwise negative. If either ``date1`` or ``date2`` are not dates, the function returns the empty string.
    * ``divide(x, y)`` -- returns x / y. Throws an exception if either x or y are not numbers.
    * ``eval(string)`` -- evaluates the string as a program, passing the local variables (those ``assign`` ed to). This permits using the template processor to construct complex results from local variables. Because the `{` and `}` characters are special, you must use `[[` for the `{` character and `]]` for the '}' character; they are converted automatically. Note also that prefixes and suffixes (the `|prefix|suffix` syntax) cannot be used in the argument to this function when using Template Program Mode.
    * ``field(name)`` -- returns the metadata field named by ``name``.
    * ``finish_formatting(val, fmt, prefix, suffix)`` -- apply the format,
      prefix, and suffix to a value in the same way as done in a template like
      ``{series_index:05.2f| - |- }``. This function is provided to ease
      conversion of complex single-function- or template-program-mode templates
      to :ref:`General Program Mode <general_mode>` (see below) to take
      advantage of GPM template compilation. For example, the following program
      produces the same output as the above template::

            program: finish_formatting(field("series_index"), "05.2f", " - ", " - ")


      Another example: for the template ``{series:re(([^\s])[^\s]+(\s|$),\1)}{series_index:0>2s| - | - }{title}`` use::

            program:
                strcat(
                    re(field('series'), '([^\s])[^\s]+(\s|$)', '\1'),
                    finish_formatting(field('series_index'), '0>2s', ' - ', ' - '),
                    field('title')
                )

    * ``first_matching_cmp(val, cmp1, result1, cmp2, r2, ..., else_result)`` -- compares ``val < cmpN`` in sequence, returning resultN for the first comparison that succeeds. Returns else_result if no comparison succeeds. Example::

            first_matching_cmp(10,5,"small",10,"middle",15,"large","giant")


      returns "large". The same example with a first value of 16 returns "giant".

    * ``first_non_empty(value, value, ...)`` -- returns the first value that is not empty. If all values are empty, then the empty value is returned. You can have as many values as you want.
    * ``floor(x)`` -- returns the largest integer less than or equal to x. Throws an exception if x is not a number.
    * ``format_date(val, format_string)`` -- format the value, which must be a date
      field, using the format_string, returning a string. The formatting codes
      are::

            d    : the day as number without a leading zero (1 to 31)
            dd   : the day as number with a leading zero (01 to 31)
            ddd  : the abbreviated localized day name (e.g. "Mon" to "Sun").
            dddd : the long localized day name (e.g. "Monday" to "Sunday").
            M    : the month as number without a leading zero (1 to 12).
            MM   : the month as number with a leading zero (01 to 12)
            MMM  : the abbreviated localized month name (e.g. "Jan" to "Dec").
            MMMM : the long localized month name (e.g. "January" to "December").
            yy   : the year as two digit number (00 to 99).
            yyyy : the year as four digit number.
            h    : the hours without a leading 0 (0 to 11 or 0 to 23, depending on am/pm)
            hh   : the hours with a leading 0 (00 to 11 or 00 to 23, depending on am/pm)
            m    : the minutes without a leading 0 (0 to 59)
            mm   : the minutes with a leading 0 (00 to 59)
            s    : the seconds without a leading 0 (0 to 59)
            ss   : the seconds with a leading 0 (00 to 59)
            ap   : use a 12-hour clock instead of a 24-hour clock, with 'ap' replaced by the localized string for am or pm.
            AP   : use a 12-hour clock instead of a 24-hour clock, with 'AP' replaced by the localized string for AM or PM.
            iso  : the date with time and timezone. Must be the only format present.


      You might get unexpected results if the date you are formatting contains localized month names, which can happen if you changed the format tweaks to contain ``MMMM``. In this case, instead of using something like ``{pubdate:format_date(yyyy)}``, write the template using Template Program Mode as in ``{:'format_date(raw_field('pubdate'),'yyyy')'}``.
    * ``formats_modtimes(format_string)`` -- return a comma-separated list of colon-separated items representing modification times for the formats of a book. The format_string parameter specifies how the date is to be formatted. See the `format_date()` function for details. You can use the select function to get the mod time for a specific format. Note that format names are always uppercase, as in EPUB.
    * ``formats_paths()`` -- return a comma-separated list of colon-separated items representing full path to the formats of a book. You can use the select function to get the path for a specific format. Note that format names are always uppercase, as in EPUB.
    * ``formats_sizes()`` -- return a comma-separated list of colon-separated items representing sizes in bytes of the formats of a book. You can use the select function to get the size for a specific format. Note that format names are always uppercase, as in EPUB.
    * ``fractional_part(x)`` -- returns the value after the decimal point. For example, fractional_part(3.14) returns 0.14. Throws an exception if x is not a number.
    * ``has_cover()`` -- return ``Yes`` if the book has a cover, otherwise return the empty string
    * ``not(value)`` -- returns the string "1" if the value is empty, otherwise returns the empty string. This function works well with test or first_non_empty.
    * ``list_difference(list1, list2, separator)`` -- return a list made by removing from `list1` any item found in `list2`, using a case-insensitive comparison. The items in `list1` and `list2` are separated by separator, as are the items in the returned list.
    * ``list_equals(list1, sep1, list2, sep2, yes_val, no_val)`` -- return `yes_val` if `list1` and `list2` contain the same items, otherwise return `no_val`. The items are determined by splitting each list using the appropriate separator character (`sep1` or `sep2`). The order of items in the lists is not relevant. The comparison is case-insensitive.
    * ``list_intersection(list1, list2, separator)`` -- return a list made by removing from `list1` any item not found in `list2`, using a case-insensitive comparison. The items in `list1` and `list2` are separated by separator, as are the items in the returned list.
    * ``list_re(src_list, separator, include_re, opt_replace)`` -- Construct a list by first separating `src_list` into items using the `separator` character. For each item in the list, check if it matches `include_re`. If it does, then add it to the list to be returned. If `opt_replace` is not the empty string, then apply the replacement before adding the item to the returned list.
    * ``list_re_group(src_list, separator, include_re, search_re, template_for_group_1, for_group_2, ...)`` -- Like list_re except replacements are not optional. It uses re_group(item, search_re, template ...) when doing the replacements.
    * ``list_sort(list, direction, separator)`` -- return list sorted using a case-insensitive sort. If `direction` is zero, the list is sorted ascending, otherwise descending. The list items are separated by separator, as are the items in the returned list.
    * ``list_union(list1, list2, separator)`` -- return a list made by merging the items in list1 and list2, removing duplicate items using a case-insensitive comparison. If items differ in case, the one in list1 is used. The items in list1 and list2 are separated by separator, as are the items in the returned list.
    * ``mod(x)`` -- returns the remainder of x / y, where x, y, and the result are integers. Throws an exception if either x or y is not a number.
    * ``multiply(x, y)`` -- returns x * y. Throws an exception if either x or y are not numbers.
    * ``ondevice()`` -- return the string "Yes" if ondevice is set, otherwise return the empty string
    * ``or(value, value, ...)`` -- returns the string "1" if any value is not empty, otherwise returns the empty string. This function works well with test or first_non_empty. You can have as many values as you want.
    * ``print(a, b, ...)`` -- prints the arguments to standard output. Unless you start calibre from the command line (``calibre-debug -g``), the output will go to a black hole.
    * ``raw_field(name)`` -- returns the metadata field named by name without applying any formatting.
    * ``raw_list(name, separator)`` -- returns the metadata list named by name without applying any formatting or sorting and with items separated by separator.
    * ``re_group(val, pattern, template_for_group_1, for_group_2, ...)`` --  return a string made by applying the regular expression pattern to the val and replacing each matched instance with the string computed by replacing each matched group by the value returned by the corresponding template. The original matched value for the group is available as $. In Template Program Mode, like for the template and the eval functions, you use [[ for { and ]] for }. The following example in Template Program Mode looks for series with more than one word and uppercases the first word::

        {series:'re_group($, "(\S* )(.*)", "[[$:uppercase()]]", "[[$]]")'}

    * ``round(x)`` -- returns the nearest integer to x. Throws an exception if x is not a number.
    * ``series_sort()`` -- returns the series sort value.
    * ``strcat(a, b, ...)`` -- can take any number of arguments. Returns a string formed by concatenating all the arguments.
    * ``strcat_max(max, string1, prefix2, string2, ...)`` -- Returns a string formed by concatenating the arguments. The returned value is initialized to string1. `Prefix, string` pairs are added to the end of the value as long as the resulting string length is less than `max`. String1 is returned even if string1 is longer than max. You can pass as many `prefix, string` pairs as you wish.
    * ``strcmp(x, y, lt, eq, gt)`` -- does a case-insensitive comparison x and y as strings. Returns ``lt`` if x < y. Returns ``eq`` if x == y. Otherwise returns ``gt``.
    * ``strlen(a)`` -- Returns the length of the string passed as the argument.
    * ``substr(str, start, end)`` -- returns the ``start``'th through the ``end``'th characters of ``str``. The first character in ``str`` is the zero'th character. If end is negative, then it indicates that many characters counting from the right. If end is zero, then it indicates the last character. For example, ``substr('12345', 1, 0)`` returns ``'2345'``, and ``substr('12345', 1, -1)`` returns ``'234'``.
    * ``subtract(x, y)`` -- returns x - y. Throws an exception if either x or y are not numbers.
    * ``today()`` -- return a date string for today. This value is designed for use in format_date or days_between, but can be manipulated like any other string. The date is in ISO format.
    * ``template(x)`` -- evaluates x as a template. The evaluation is done in its own context, meaning that variables are not shared between the caller and the template evaluation. Because the `{` and `}` characters are special, you must use `[[` for the `{` character and `]]` for the '}' character; they are converted automatically. For example, ``template('[[title_sort]]') will evaluate the template ``{title_sort}`` and return its value. Note also that prefixes and suffixes (the `|prefix|suffix` syntax) cannot be used in the argument to this function when using Template Program Mode.

.. _general_mode:

Using General Program Mode
-----------------------------------

For more complicated template programs it is often easier to avoid template syntax (all the `{` and `}` characters), instead writing a more classic-looking program. You can do this by beginning the template with `program:`. The template program is compiled and executed. No template processing (e.g., formatting, prefixes, suffixes) is done. The special variable `$` is not set.

One advantage of `program:` mode is that braces are no longer special. For example, it is not necessary to use `[[` and `]]` when using the `template()` function. Another advantage is readability.

Both General and Template Program Modes support ``if`` expressions with the following syntax::

    if <<expression>> then
        <<expression_list>>
    [elif <<expression>> then <<expression_list>>]*
    [else <<expression_list>> ]
    fi

The elif and else parts are optional. The words ``if``, ``then``, ``elif``, ``else``, and ``fi`` are reserved; you cannot use them as identifier names. You can put newlines and white space wherever they make sense. <<expression>> is one template language expression;  semicolons are not allowed. <<expression_list>> is a semicolon-separated sequence of template language expressions, including nested ifs. Examples:

    * ``program: if field('series') then 'yes' else 'no' fi``
    * ``program: if field('series') then a = 'yes'; b = 'no' else a = 'no'; b='yes' fi; strcat(a, '-', b)``
    * Nested ``if`` example::

        program:
            if field('series')
            then
                if check_yes_no(field('#mybool'), '', '', '1')
                then
                    'yes'
                else
                    'no'
                fi
            else
                'no series'
            fi

An ``if`` produces a value like any other language expression. This means that all the following are valid:

    * ``program: if field('series') then 'foo' else 'bar' fi``
    * ``program: if field('series') then a = 'foo' else a = 'bar' fi; a``
    * ``program: a = if field('series') then 'foo' else 'bar' fi; a``
    * ``program: a = field(if field('series') then 'series' else 'title' fi); a``

Template Program Mode and General Program Mode support classic relational (comparison) operators: ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``. The operators return '1' if they evaluate to True, otherwise ''. They do case-insensitive string comparison using lexical order. Examples:

    * ``program: field('series') == 'foo'`` returns '1' if the book's series is 'foo'.
    * ``program: if field('series') != 'foo' then 'bar' else 'mumble' fi`` returns 'bar' if the book's series is not 'foo', else 'mumble'.
    * ``program: if or(field('series') == 'foo', field('series') == '1632') then 'yes' else 'no' fi`` returns 'yes' if series is either 'foo' or '1632', otherwise 'no'.
    * ``program: if '11' > '2' then 'yes' else 'no' fi`` returns 'no' because it is doing a lexical comparison. If you want numeric comparison instead of lexical comparison, use the operators ``==#``, ``!=#``, ``<#``, ``<=#``, ``>#``, ``>=#``. In this case the left and right values are set to zero if they are undefined or the empty string. If they are not numbers then an error is raised.

General Program Mode supports saving templates and calling those templates from another template. You save
templates using :guilabel:`Preferences->Advanced->Template functions`. More information is provided in that dialog. You call
a template the same way you call a function, passing positional arguments if desired. An argument can be any expression.
Examples of calling a template, assuming the stored template is named ``foo``:

    * ``foo()`` -- call the template passing no arguments.
    * ``foo(a, b)`` call the template passing the values of the two variables ``a`` and ``b``.
    * ``foo(if field('series') then field('series_index') else 0 fi)`` -- if the book has a ``series`` then pass the             ``series_index``, otherwise pass the value ``0``.

In the stored template you retrieve the arguments passed in the call using the ``arguments`` function. It both declares and
initializes local variables, effectively parameters. The variables are positional; they get the value of the value given in
the call in the same position.
If the corresponding parameter is not provided in the call then ``arguments`` assigns that variable the provided default value. If there is no default value then the variable is set to the empty string. For example, the following ``arguments`` function declares 2 variables, ``key``, ``alternate``::

            arguments(key, alternate='series')

Examples, again assuming the stored template is named ``foo``:

    * ``foo('#myseries')`` -- argument ``key`` will have the value ``myseries`` and the argument ``alternate`` will have the value ``series``.
    * ``foo('series', '#genre')`` the variable ``key`` is assigned the value ``series`` and the variable ``alternate`` is assigned the value ``#genre``.
    * ``foo()`` -- the variable ``key`` is assigned the empty string and the variable ``alternate`` is assigned the value ``#genre``.

An easy way to test stored templates is using the ``Template tester`` dialog. Give it a keyboard shortcut in
:guilabel:`Preferences->Advanced->Keyboard shortcuts->Template tester`. Giving the ``Stored templates`` dialog a
shortcut will help switching more rapidly between the tester and editing the stored template's source code.

Notes on the difference between modes
-----------------------------------------

The three program modes, Single Function Mode (SFM), Template Program Mode (TPM), and
General Program Mode (GPM), work differently. SFM is intended to be 'simple' so it hides a lot
of programming language bits. For example, the value of the column is always passed as an 'invisible' first argument
to a function included in the template. SFM also doesn't support the difference between variables
and strings; all values are strings.

Example: the following SFM template returns either the series name or the string "no series"::

    {series:ifempty(no series)}

The equivalent template in TPM is ::

    ``{series:'ifempty($, 'no series')'}``
    
The equivalent template in GPM is::

    ``program: ifempty(field('series'), 'no series')``

The first argument to ``ifempty`` is the value of the field ``series``. The second argument
is the string ``no series``. In SFM the first argument, the value of the field,
is automatically passed (the invisible argument).

Several template functions, for example ``booksize()`` and ``current_library_name()``, take no arguments.
Because of the 'invisible argument' you cannot use these functions in SFM.

Nested functions, where a function calls another function to compute an argument, cannot be used in SFM.
For example this template, intended to return the first 5 characters of the series value uppercased, won't work in SFM::

    ``{series:uppercase(substr(0,5))}``

TPM and GPM support nested functions. The above template in TPM would be::

    ``{series:'uppercase(substr($, 0,5))'}``

In GPM it would be::

    ``program: uppercase(substr(field('series'), 0,5))``


User-defined Python template functions
------------------------------------------

You can add your own Python functions to the template processor. Such functions can be used in any of the three template programming modes. The functions are added by going to :guilabel:`Preferences -> Advanced -> Template functions`. Instructions are shown in that dialog.

Special notes for save/send templates
---------------------------------------

Special processing is applied when a template is used in a `save to disk` or `send to device` template. The values of the fields are cleaned, replacing characters that are special to file systems with underscores, including slashes. This means that field text cannot be used to create folders. However, slashes are not changed in prefix or suffix strings, so slashes in these strings will cause folders to be created. Because of this, you can create variable-depth folder structure.

For example, assume we want the folder structure `series/series_index - title`, with the caveat that if series does not exist, then the title should be in the top folder. The template to do this is::

    {series:||/}{series_index:|| - }{title}

The slash and the hyphen appear only if series is not empty.

The lookup function lets us do even fancier processing. For example, assume that if a book has a series, then we want the folder structure `series/series index - title.fmt`. If the book does not have a series, then we want the folder structure `genre/author_sort/title.fmt`. If the book has no genre, we want to use 'Unknown'. We want two completely different paths, depending on the value of series.

To accomplish this, we:
    1. Create a composite field (give it lookup name #AA) containing ``{series}/{series_index} - {title}``. If the series is not empty, then this template will produce `series/series_index - title`.
    2. Create a composite field (give it lookup name #BB) containing ``{#genre:ifempty(Unknown)}/{author_sort}/{title}``. This template produces `genre/author_sort/title`, where an empty genre is replaced with `Unknown`.
    3. Set the save template to ``{series:lookup(.,#AA,#BB)}``. This template chooses composite field #AA if series is not empty, and composite field #BB if series is empty. We therefore have two completely different save paths, depending on whether or not `series` is empty.

Templates and plugboards
---------------------------

Plugboards are used for changing the metadata written into books during send-to-device and save-to-disk operations. A plugboard permits you to specify a template to provide the data to write into the book's metadata. You can use plugboards to modify the following fields: authors, author_sort, language, publisher, tags, title, title_sort. This feature helps people who want to use different metadata in books on devices to solve sorting or display issues.

When you create a plugboard, you specify the format and device for which the plugboard is to be used. A special device is provided, save_to_disk, that is used when saving formats (as opposed to sending them to a device). Once you have chosen the format and device, you choose the metadata fields to change, providing templates to supply the new values. These templates are `connected` to their destination fields, hence the name `plugboards`. You can, of course, use composite columns in these templates.

When a plugboard might apply (Content server, save to disk, or send to device), calibre searches the defined plugboards to choose the correct one for the given format and device. For example, to find the appropriate plugboard for an EPUB book being sent to an ANDROID device, calibre searches the plugboards using the following search order:

    * a plugboard with an exact match on format and device, e.g., ``EPUB`` and ``ANDROID``
    * a plugboard with an exact match on format and the special ``any device`` choice, e.g., ``EPUB`` and ``any device``
    * a plugboard with the special ``any format`` choice and an exact match on device, e.g., ``any format`` and ``ANDROID``
    * a plugboard with ``any format`` and ``any device``

The tags and authors fields have special treatment, because both of these fields can hold more than one item. A book can have many tags and many authors. When you specify that one of these two fields is to be changed, the template's result is examined to see if more than one item is there. For tags, the result is cut apart wherever calibre finds a comma. For example, if the template produces the value ``Thriller, Horror``, then the result will be two tags, ``Thriller`` and ``Horror``. There is no way to put a comma in the middle of a tag.

The same thing happens for authors, but using a different character for the cut, a `&` (ampersand) instead of a comma. For example, if the template produces the value ``Blogs, Joe&Posts, Susan``, then the book will end up with two authors, ``Blogs, Joe`` and ``Posts, Susan``. If the template produces the value ``Blogs, Joe;Posts, Susan``, then the book will have one author with a rather strange name.

Plugboards affect the metadata written into the book when it is saved to disk or written to the device. Plugboards do not affect the metadata used by ``save to disk`` and ``send to device`` to create the file names. Instead, file names are constructed using the templates entered on the appropriate preferences window.

Tips
------------

You might find the following tips useful.

    * Use the Template Tester to test templates. Add the tester to the context menu for books in the library and/or give it a keyboard shortcut.
    * Templates can use other templates by referencing composite columns built with the desired template. Alternatively, you could
      use Stored Templates.
    * In a plugboard, you can set a field to empty (or whatever is equivalent to empty) by using the special template ``{}``. This template will always evaluate to an empty string.
    * The technique described above to show numbers even if they have a zero value works with the standard field series_index.

.. _template_functions_reference:

Function reference
---------------------------

.. toctree::
    :maxdepth: 3

    generated/en/template_ref

.. toctree::
  :hidden:

  generated/en/template_ref
