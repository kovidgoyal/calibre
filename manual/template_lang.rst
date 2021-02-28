.. _templatelangcalibre:

The calibre template language
=======================================================

The calibre template language is a calibre-specific programming language used throughout calibre. For example, it is used to specify the folder structure and file name when saving files from the calibre library to the disk or e-book reader, define 'rules' for adding icons to the calibre book list, and to define "virtual" columns that contain data from other columns. The language is built around the notion of a 'template'; a template specifies which book metadata to use and how it is to be formatted.

Basic Templates
---------------

A basic template consists one or more 'template expressions'. A template expression consists of text and names in curly brackets that are then replaced by the corresponding metadata from the book being processed. For example, the default template used for saving books to device in calibre is::

    {author_sort}/{title}/{title} - {authors}

For the book "The Foundation" by "Isaac Asimov" the  will become::

    Asimov, Isaac/The Foundation/The Foundation - Isaac Asimov

The slashes are text, which is put into the template where it appears. For example, if your template is::

    {author_sort} Some Important Text {title}/{title} - {authors}

For the book "The Foundation" by "Isaac Asimov" the template produces::

    Asimov, Isaac Some Important Text The Foundation/The Foundation - Isaac Asimov

A template can access all the metadata available in calibre, including custom columns (columns you create yourself), by using its ``lookup name``. To find the lookup name for a column (sometimes called a 'field'), hover your mouse over the column header in calibre's book list. Lookup names for custom columns always have a ``#`` as the first character. For series type columns there is an additional field named ``'#lookup name'_index`` that is the series index for that series. So if you have a custom series field named ``#myseries``, there will also be a field named ``#myseries_index``. The standard series column's index is named ``series_index``.

In addition to the column based fields, you also can use::

    {formats} - A list of formats available in the calibre library for a book
    {identifiers:select(isbn)} - The ISBN of the book

If a book does not have a particular piece of metadata, the field in the template is replaced by the empty string (``''``). Consider, for example::

    {author_sort}/{series}/{title} {series_index}

If a book has a series, the template produces::

    Asimov, Isaac/Foundation/Second Foundation 3

and if the book does not have a series::

    Asimov, Isaac/Second Foundation

The template processor automatically removes multiple slashes and leading or trailing spaces.

Advanced formatting
----------------------

You can do more than simple substitution with the templates. You can also conditionally include additional text and control how substituted data is formatted.

**Conditionally including text**

Sometimes you want to have text appear in the output only if a field is not empty. A common case is ``series`` and ``series_index``, where you want either nothing or the two values with a hyphen between them. calibre handles this case using a special template item syntax.

For example, assume you want to use the template::

        {series} - {series_index} - {title}

If the book has no series, the answer will be ``- - title``, which is probably not what is wished. Most people would prefer the result be ``title``, without the hyphens. To do this, use the extended template syntax::

  {field:|prefix_text|suffix_text}

When you use this syntax, if ``field`` has the value ``SERIES`` then the result will be ``prefix_textSERIESsuffix_text``. If ``field`` has no value, then the result will be the empty string (nothing) because the prefix and suffix are ignored. The prefix and suffix can contain blanks.

**Do not use subtemplates (`{ ... }`) or functions (see below) in the prefix or the suffix.**

Using this syntax, we can solve the above no-series problem with the template::

        {series}{series_index:| - | - }{title}

The hyphens will be included only if the book has a series index, which it has only if it has a series.

Notes::
  * You must include the colon after the lookup name if you want to use a prefix or a suffix.
  * You must either use no \| characters or both of them; using one, as in ``{field:| - }``, is not allowed.
  * It is OK not to provide text for either the prefix or the suffix, such as in ``{series:|| - }``. The template ``{title:||}`` is the same as ``{title}``.

**Formatting**

Suppose you want to ensure that the series_index is always formatted as three
digits with leading zeros. This does the trick::

    {series_index:0>3s} - Three digits with leading zeros

For trailing zeros, use::

   {series_index:0<3s} - Three digits with trailing zeros

If you use series indices with fractional values (e.g., 1.1), you might want the decimal points to line up. For example, you might want the indices 1 and 2.5 to appear as 01.00 and 02.50 so that they will sort correctly. To do this, use::

   {series_index:0>5.2f} - Five characters consisting of two digits with leading zeros, a decimal point, then 2 digits after the decimal point.

If you want only the first two letters of the data, use::

   {author_sort:.2} - Only the first two letter of the author sort name

Much of the calibre template language comes from Python. For more details on the syntax of these advanced formatting operations see the `Python documentation <https://docs.python.org/3/library/string.html#formatstrings>`_.


Using templates to define custom columns
-----------------------------------------

Sometimes you want to display information that isn't in calibre metadata or differently from how calibre's normal format. For example, you might want to display the ISBN, a field that calibre does not display. You can solve this problem using custom columns creating a column with the type 'Column built from other columns' (hereafter called composite columns), and entering a template to generate what is to be displayed. A column will be created showing the result of evaluating the template. For example, to display the ISBN, create the column and enter ``{identifiers:select(isbn)}`` into the template box. To display a column containing the values of two series custom columns separated by a comma, use ``{#series1:||,}{#series2}``.

Composite columns can use any template option, including formatting.

You cannot edit the data displayed in a composite column. If you edit a composite column, for example
by double-clicking it, calibre will open the template for editing, not the underlying data. Editing the template on the GUI is a quick way of testing and changing composite columns.

.. _single_mode:

Using functions in templates - Single Function Mode
---------------------------------------------------

Suppose you want to display the value of a field in upper case, when that field is normally in title case. You can do this using the functions available for templates. For example, to display the title in upper case, use the ``uppercase`` function, as in ``{title:uppercase()}``. To display it in title case, use ``{title:titlecase()}``.

Functions are put in the format part of the template, going after the ``:`` and before the first ``|`` or the closing ``}`` if no prefix/suffix is used. If you have both a format and a function reference, the function comes after another ``:``.  Functions return the value of the field used in the template, suitably modified.

The syntax for using functions is ``{lookup_name:function(arguments)}``, or ``{lookup_name:function(arguments)|prefix|suffix}``. Arguments are separated by commas. Literal commas (commas as arguments) must be preceded by a backslash ( ``\`` ). The last (or only) argument cannot contain a closing parenthesis ( ``)`` ). Function names must always end with ``()``. Some functions require extra values (arguments), and these go inside the ``()``.

Functions are evaluated before format specifications and the prefix/suffix. See further down for an example of using both a format and a function.

Important: If you have programming experience, please note that the syntax in this mode (Single Function Mode) is not what you expect. Strings are not quoted. Spaces are significant. All arguments must be constants; there is no sub-evaluation.

**Do not use subtemplates (`{ ... }`) as function arguments.** Instead, use :ref:`Template Program Mode <template_mode>` and :ref:`General Program Mode <general_mode>`.

Some functions use regular expressions. In the template language regular expression matching is case-insensitive.

The functions intended for use in Single Function Mode are listed below. Note: the definitive documentation for functions is available in the section :ref:`Function reference <template_functions_reference>`:

    * ``lowercase()``	-- returns the value of the field in lower case.
    * ``uppercase()``	-- returns the value of the field in upper case.
    * ``titlecase()``	-- returns the value of the field in title case.
    * ``capitalize()``	-- returns the value with the first letter upper case and the rest lower case.
    * ``contains(pattern, text if match, text if not match)`` -- checks if the field's value is matched by the regular expression ``pattern``. Returns ``text if match`` if if the pattern matches the value, otherwise it returns ``text if no match``.
    * ``count(separator)`` -- interprets the value as a list of items separated by ``separator`` and returns the number of items in the list. Most lists use a comma as the separator, but ``authors`` uses an ampersand (&). Examples: ``{tags:count(,)}``, ``{authors:count(&)}``. Aliases: ``count()``, ``list_count()``
    * ``format_number(template)`` -- interprets the value as a number and formats that number using a Python formatting template such as ``"{0:5.2f}"`` or ``"{0:,d}"`` or ``"${0:5,.2f}"``. The formatting template must begin with ``{0:`` and end with ``}`` as in the above examples. Exception: you can leave off the leading "{0:" and trailing "}" if the format template contains only a format. See the template language and the `Python documentation <https://docs.python.org/3/library/string.html#formatstrings>`_ for more examples. Returns the empty string if formatting fails.
    * ``human_readable()`` -- expects the value to be a number and returns a string representing that number in KB, MB, GB, etc.
    * ``ifempty(text if empty)`` -- if the value is not empty then return the value of the field, otherwise return `text if empty`.
    * ``in_list(separator, pattern, found_val, ..., not_found_val)`` -- interpret the value as a list of items separated by ``separator``, checking the ``pattern`` against each item in the list. If the ``pattern`` matches an item then return ``found_val``, otherwise return ``not_found_val``. The pair ``pattern`` and ``found_value`` can be repeated as many times as desired, permitting returning different values depending on the item value. The patterns are checked in order. The first match is returned.
    * ``language_codes(lang_strings)`` -- return the `language codes <https://www.loc.gov/standards/iso639-2/php/code_list.php>`_ for the language names passed in `lang_strings`. The strings must be in the language of the current locale. ``Lang_strings`` is a comma-separated list.
    * ``language_strings(lang_codes, localize)`` -- return the `language names <https://www.loc.gov/standards/iso639-2/php/code_list.php>`_ for the language codes passed in `lang_codes`. If `localize` is zero, return the strings in English. If ``localize`` is not zero, return the strings in the language of the current locale. ``Lang_codes`` is a comma-separated list.
    * ``list_item(index, separator)`` -- interpret the value as a list of items separated by ``separator``, returning the `index`th item. The first item is number zero. The last item can be returned using an index of ``-1`` as in ``list_item(-1,separator)``. If the item is not in the list, then the empty string is returned.
    * ``lookup(pattern, field, pattern, field, ..., else_field)`` -- like ``switch`` (below), except the ``field`` arguments are ``lookup names``, not text. The value of the field named by ``lookup key`` will be used. Note that because composite columns are fields, you can use this function in one composite column to use the value of some other composite column.
    * ``rating_to_stars(use_half_stars)`` -- Returns the rating as string of star (``★``) characters. The value must be a number between 0 and 5. Set use_half_stars to 1 if you want half star characters for fractional numbers.
    * ``re(pattern, replacement)`` -- return the field after applying the regular expression. All instances of `pattern` are replaced with `replacement`. The template language uses `Python regular expressions <https://docs.python.org/3/library/re.html>`_.
    * ``select(key)`` -- interpret the value as a comma-separated list of items, with each item having the form ``id:value`` (``identifier`` format). The function finds the first pair with the id equal to key and returns the corresponding value. This function is particularly useful for extracting a value such as an ISBN from the set of identifiers for a book.
    * ``shorten(left chars, middle text, right chars)`` -- Return a shortened version of the value, consisting of ``left chars`` characters from the beginning of the value, followed by ``middle text``, followed by ``right chars`` characters from the end of the value. ``Left chars`` and ``right chars`` must be postive integers. Example: assume you want to display the title in a field at most 15 characters in length. One template that does this is ``{title:shorten(9,-,5)}``. For a book with the title `Ancient English Laws in the Times of Ivanhoe` the result will be `Ancient E-nhoe`: the first 9 characters of the title, a ``-``, then the last 5 characters. If the value's length is less than ``left chars`` + ``right chars`` + the length of ``middle text`` then the value will be returned unchanged. For example, the title `The Dome` would not be changed.
    * ``str_in_list(separator, string, found_val, ..., not_found_val)`` -- interpret the field as a list of items separated by ``separator``, comparing ``string`` against each value in the list. The ``string`` is not a regular expression. If ``string`` equals an item (ignoring case) then return ``found_val``, otherwise return ``not_found_val``. If ``string`` contains separators then it is also treated as a list and each subvalue is checked. The ``string`` and ``found_value`` pairs can be repeated as many times as desired, permitting returning different values depending on the search. If none of the strings match then ``not_found_value`` is returned. The strings are checked in order. The first match is returned.
    * ``subitems(start_index, end_index)`` -- This function breaks apart lists of tag-like hierarchical items such as genres. It interprets the value as a comma-separated list of tag-like items, where each item is a period-separated list. It returns a new list made by extracting from each item the components from ``start_index`` to ``end_index``, then merging the results back together. Duplicates are removed. The first subitem in a period-separated list has an index of zero. If an index is negative then it counts from the end of the list. As a special case, an end_index of zero is assumed to be the length of the list.

      Examples::

        * Assuming a #genre column containing "A.B.C"
            {#genre:subitems(0,1)} returns "A"
            {#genre:subitems(0,2)} returns "A.B"
            {#genre:subitems(1,0)} returns "B.C"
        * Assuming a #genre column containing "A.B.C, D.E":
            {#genre:subitems(0,1)} returns "A, D"
            {#genre:subitems(0,2)} returns "A.B, D.E"

    * ``sublist(start_index, end_index, separator)`` -- interpret the value as a list of items separated by ``separator``, returning a new list made from the items from ``start_index`` to ``end_index``. The first item is number zero. If an index is negative, then it counts from the end of the list. As a special case, an end_index of zero is assumed to be the length of the list.

      Examples assuming that the tags column (which is comma-separated) contains "A, B ,C"::

        {tags:sublist(0,1,\,)} returns "A"
        {tags:sublist(-1,0,\,)} returns "C"
        {tags:sublist(0,-1,\,)} returns "A, B"

    * ``swap_around_articles(separator)`` -- returns the value with articles moved to the end. The value can be a list, in which case each item in the list is processed. If the value is a list then you must provide the ``separator``. If no ``separator`` is provided then the value is treated as being a single value, not a list.
    * ``swap_around_comma()`` -- given a value of the form ``B, A``, return ``A B``. This is most useful for converting names in LN, FN format to FN LN. If there is no comma in the value then the function returns the value unchanged.
    * ``switch(pattern, value, pattern, value, ..., else_value)`` -- for each ``pattern, value`` pair, checks if the field value matches the regular expression ``pattern`` and if so, returns the associated ``value``. If no ``pattern`` matches, then ``else_value`` is returned. You can have as many ``pattern, value`` pairs as you wish. The first match is returned.
    * ``test(text if not empty, text if empty)`` -- return ``text if not empty`` if the value is not empty, otherwise return ``text if empty``.
    * ``transliterate()`` -- Return a string in a latin alphabet formed by approximating the sound of the words in the source field. For example, if the source field is ``Фёдор Миха́йлович Достоевский`` this function returns ``Fiodor Mikhailovich Dostoievskii``.

**Using functions and formatting in the same template**

Suppose you have an integer custom column ``#myint`` that you want displayed with leading zeros, as in ``003``. To do this, you would use a format of ``0>3s``. However, by default if a number (integer or float) equals zero then the value is displayed as the empty string so zero values will produce the empty string, not ``000``. If you want to see ``000`` values then you use both the format string and the ``ifempty`` function to change the empty value back to a zero. The template would be::

    {#myint:0>3s:ifempty(0)}

Note that you can use the prefix and suffix as well. If you want the number to appear as ``[003]`` or ``[000]``, then use the template::

    {#myint:0>3s:ifempty(0)|[|]}

.. _general_mode:

General Program Mode
-----------------------------------

General Program Mode replaces the template with a program written in the `template language`. The syntax of the language is defined by the following grammar::

    program         ::= 'program:' expression_list
    expression_list ::= top_expression [ ';' top_expression ]*
    top_expression  ::= or_expression
    or_expression   ::= and_expression [ '||' and_expression ]*
    and_expression  ::= not_expression [ '&&' not_expression ]*
    not_expression  ::= ['!' not_expression]* | compare_exp
    compare_expr    ::= add_sub_expr [ compare_op add_sub_expr ]
    compare_op      ::= '==' | '!=' | '>=' | '>' | '<=' | '<' | 'in' |
                        '==#' | '!=#' | '>=#' | '>#' | '<=#' | '<#'
    add_sub_expr    ::= times_div_expr [ add_sub_op times_div_expr ]*
    add_sub_op      ::= '+' | '-'
    times_div_expr  ::= unary_op_expr [ times_div_op unary_op_expr ]*
    times_div_op    ::= '*' | '/'
    unary_op_expr   ::= [ add_sub_op unary_op_expr ]* | expression
    expression      ::= identifier | constant | function | assignment |
                        compare | if_expression | for_expression | '(' top_expression ')'
    identifier      ::= sequence of letters or ``_`` characters
    constant        ::= " string " | ' string ' | number
    function        ::= identifier '(' top_expression [ ',' top_expression ]* ')'
    assignment      ::= identifier '=' top_expression
    if_expression   ::= 'if' condition 'then' expression_list
                        [elif_expression] ['else' expression_list] 'fi'
    condition       ::= top_expression
    elif_expression ::= 'elif' condition 'then' expression_list elif_expression | ''
    for_expression  ::= 'for' identifier 'in' list_expression
                        [ 'separator' separator_expr ] ':' expression_list 'rof'
    list_expression ::= top_expression
    separator_expr  ::= top_expression

Comments are lines with a '#' character at the beginning of the line. You can't have comments that begin later in the line.

A ``top_expression`` always has a value. The value of an ``expression_list`` is the value
of the last ``top_expression`` in the list. For example the value of the following ``expression_list``::

    1; 2; 'foobar'; 3

is 3.

**Operator Precedence**

The operator precedence (order of evaluation) specified by the above grammar is:

    * Function calls, constants, parenthesized expressions, statement expressions, assignment expressions. In the template language, ``if``, ``for``, and assignments return a value (see below).
    * Unary plus (``+``) and minus (``-``). These operators evaluate right to left. These and all the other arithmetic operators return integers if the expression results in a fractional part equal to zero. Example: if an expression returns ``3.0`` it is changed to ``3``.
    * Multiply (``*``) and divide (``/``). These operators are associative and evaluate left to right. Use parentheses if you want to change the order of evaluation.
    * Add (``+``) and subtract (``-``). These operators are associative and evaluate left to right.
    * Numeric and string comparisons. These operators return ``1`` (the number one) if the comparison is True (a non-empty string), otherwise the empty string (``''``). Comparisons are not associative: ``a < b < c`` is a syntax error.
    * Unary logical not (``!``). This operator returns '1' if the expression is False (evaluates to the empty string), otherwise ``''``.
    * Logical and (``&&``). This operator returns '1' if both the left-hand and right-hand expressions are True or the empty string ``''`` if either is False. It is associative, evaluates left to right, and does `short-circuiting <https://chortle.ccsu.edu/java5/Notes/chap40/ch40_2.html>`_.
    * Logical or (``||``). This operator returns ``'1'`` if either the left-hand or right-hand expression is True or ``''`` if both are False. It is associative, evaluates left to right, and does short-circuiting. The operator is an inclusive or, returning '1' if both the left- and right-hand expressions are True.

**If Expressions**

``If`` expressions first evaluate the ``condition``, which is True if it evaluates to anything other than the empty string. If it is True then the ``expression_list`` in the ``then`` clause is evaluated. If it is False then the ``expression_list`` in the ``elif`` or ``else`` clause is evaluated. The ``elif`` and ``else`` parts are optional. The words ``if``, ``then``, ``elif``, ``else``, and ``fi`` are reserved; you cannot use them as identifier names. You can put newlines and white space wherever they make sense. The ``condition`` is a ``top_expression`` not an ``expression_list``; semicolons are not allowed. The ``expression_lists`` are semicolon-separated sequences of template language top_expressions. An ``if`` expression returns the result of the last ``top_expression`` in the evaluated ``expression_list``, or '' if no expression list was evaluated.

Examples::

    * program: if field('series') then 'yes' else 'no' fi
    * program:
          if field('series') then
              a = 'yes';
              b = 'no'
          else
              a = 'no';
              b='yes'
          fi;
          strcat(a, '-', b)
    * Nested ``if`` example::

        program:
            if field('series') then
                if check_yes_no(field('#mybool'), '', '', '1') then
                    'yes'
                else
                    'no'
                fi
            else
                'no series'
            fi

As said above, like all ``expressions`` an ``if`` produces a value. This means that all the
following are equivalent::

    * program: if field('series') then 'foo' else 'bar' fi
    * program: if field('series') then a = 'foo' else a = 'bar' fi; a
    * program: a = if field('series') then 'foo' else 'bar' fi; a

As a last example, this program returns the word `series` if the book has a series otherwise the word `title`::

    program: a = field(if field('series') then 'series' else 'title' fi); a

**For Expressions**

The ``list_expression`` in a ``for`` must evaluate to either a metadata field lookup key, for example ``tags`` or ``#genre``, or a list of values. If the result is a valid lookup key then the field's value is fetched and the separator specified for that field type is used. If the result isn't a valid lookup name then it is assumed to be a list of values. The list is assumed to be separated by commas unless the optional keyword ``separator`` is supplied, in which case the list values must be separated by the result of evaluating the ``separator_expr``. Each value in the list is assigned to the variable ``id`` then the ``expression_list`` is evaluated.

Example: This template removes the first hierarchical name for each value in Genre (``#genre``), constructing a list with the new names::

        program:
        	new_tags = '';
        	for i in '#genre':
        		j = re(i, '^.*?\.(.*)$', '\1');
        		new_tags = list_union(new_tags, j, ',')
        	rof;
            new_tags

If the original Genre is `History.Military, Science Fiction.Alternate History, ReadMe` then the template returns `Military, Alternate History, ReadMe`. You could use this template in calibre's
:guilabel:`Edit metadata in bulk -> Search & replace` with :guilabel:`Search for` set to ``template`` to strip off the first level of the hierarchy and assign the resulting value to Genre.

Note: the last line in the template, ``new_tags``, isn't strictly necessary in this case because ``for`` returns the value of the last top_expression in the expression list.

**Relational Operators**

Relational operators return '1' if they evaluate to True, otherwise the empty string ('').

There are two forms of relational operator: string comparisons and numeric comparisons. The supported string comparison operators are ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, and ``in``.
They do case-insensitive string comparison using lexical order. For the ``in`` operator, the result of the left hand expression is interpreted as a regular expression pattern. The ``in`` operator is True if the pattern matches the result of the right hand expression. The match is case-insensitive.

The numeric comparison operators are ``==#``, ``!=#``, ``<#``, ``<=#``, ``>#``, ``>=#``. The left and right expressions must evaluate to numeric values with two exceptions: the string value "None" (undefined field) and the empty string evaluate to the value zero.

Examples:

    * ``program: field('series') == 'foo'`` returns '1' if the book's series is 'foo', otherwise ``''``.
    * ``program: 'f.o' in field('series')`` returns '1' if the book's series matches the regular expression ``f.o``, otherwise ``''``.
    * ``program: if field('series') != 'foo' then 'bar' else 'mumble' fi`` returns ``bar`` if the book's series is not ``foo``, else ``mumble``.
    * ``program: if or(field('series') == 'foo', field('series') == '1632') then 'yes' else 'no' fi`` returns ``yes`` if series is either `foo` or `1632`, otherwise ``no``.
    * ``program: if '^(foo|1632)$' in field('series') then 'yes' else 'no' fi`` returns 'yes' if series is either `foo` or `1632`, otherwise 'no'.
    * ``program: if '11' > '2' then 'yes' else 'no' fi`` returns `no` because it does a lexical comparison.
    * ``program: if '11' ># '2' then 'yes' else 'no' fi`` returns `yes` because it does a numeric comparison.

**Additional Available Functions**

The following functions are available in addition to those described in :ref:`Single Function Mode <single_mode>`.

In General Program Mode the Single Function Mode functions require an additional first parameter
specifying the value to operate upon. All parameters are top_expressions (see the grammar above). Note that the definitive documentation for functions is available in the section :ref:`Function reference <template_functions_reference>`:

    * ``add(x, y, ...)`` -- returns the sum of its arguments. Throws an exception if an argument is not a number. In most cases you can use the ``+`` operator instead of this function.
    * ``and(value, value, ...)`` -- returns the string "1" if all values are not empty, otherwise returns the empty string. This function works well with test or first_non_empty. You can have as many values as you want. In most cases you can use the ``&&`` operator instead of this function.  A reason it cannot be replaced is if short-circuiting will change the results.
    * ``assign(id, val)`` -- assigns val to id, then returns val. id must be an identifier, not an expression. In most cases you can use the ``=`` operator instead of this function.
    * ``approximate_formats()`` -- return a comma-separated list of formats that at one point were associated with the book. There is no guarantee that the list is correct, although it probably is. This and other zero-parameter functions can be called in Template Program Mode (see below) using the template ``{:'approximate_formats()'}``. Note that resulting format names are always uppercase, as in EPUB.
    * ``author_links(val_separator, pair_separator)`` -- returns a string containing a list of authors and those authors' link values in the form:

       ``author1 val_separator author1_link pair_separator author2 val_separator author2_link`` etc.

      An author is separated from its link value by the ``val_separator`` string with no added spaces. ``author:linkvalue`` pairs are separated by the ``pair_separator`` string argument with no added spaces. It is up to you to choose separator strings that do not occur in author names or links. An author is included even if the author link is empty.
    * ``author_sorts(val_separator)`` -- returns a string containing a list of author's sort values for the authors of the book. The sort is the one in the author metadata information (different from the author_sort in books). The returned list has the form ``author sort 1`` ``val_separator`` ``author sort 2`` etc. The author sort values in this list are in the same order as the authors of the book. If you want spaces around ``val_separator`` then include them in the ``val_separator`` string.
    * ``booksize()`` -- returns the value of the calibre 'size' field. Returns '' if there are no formats.
    * ``check_yes_no(field_name, is_undefined, is_false, is_true)`` -- checks the value of the yes/no field named by the lookup key ``field_name`` for a value specified by the parameters, returning ``'yes'`` if a match is found, otherwise returning the empty string. Set the parameter ``is_undefined``, ``is_false``, or ``is_true`` to 1 (the number) to check that condition, otherwise set it to 0. Example::

            check_yes_no("#bool", 1, 0, 1)

      returns ``'yes'`` if the yes/no field ``"#bool"`` is either undefined (neither True nor False) or True. More than one of ``is_undefined``, ``is_false``, or ``is_true`` can be set to 1.
    * ``ceiling(x)`` -- returns the smallest integer greater than or equal to ``x``. Throws an exception if ``x`` is not a number.
    * ``cmp(x, y, lt, eq, gt)`` -- compares ``x`` and ``y`` after converting both to numbers. Returns ``lt`` if ``x`` < ``y``. Returns ``eq`` if ``x`` == ``y``, otherwise returns ``gt``.
    * ``connected_device_name(storage_location_key)`` -- if a device is connected then return the device name, otherwise return the empty string. Each storage location on a device can have a different device name. The ``storage_location_key`` names are ``'main'``, ``'carda'`` and ``'cardb'``. This function works only in the GUI.
    * ``connected_device_uuid(storage_location_key)`` -- if a device is connected then return the device uuid (unique id), otherwise return the empty string. Each storage location on a device has a different uuid. The ``storage_location_key`` location names are ``'main'``, ``'carda'`` and ``'cardb'``. This function works only in the GUI.
    * ``current_library_name()`` -- return the last name on the path to the current calibre library.
    * ``current_library_path()`` -- return the full path to the current calibre library.
    * ``days_between(date1, date2)`` -- return the number of days between ``date1`` and ``date2``. The number is positive if ``date1`` is greater than ``date2``, otherwise negative. If either ``date1`` or ``date2`` are not dates, the function returns the empty string.
    * ``divide(x, y)`` -- returns ``x / y``. Throws an exception if either ``x`` or ``y`` are not numbers. This function can usually be replaced by the ``/`` operator.
    * ``eval(string)`` -- evaluates the string as a program, passing the local variables (those ``assign`` ed to). This permits using the template processor to construct complex results from local variables. In Template Program Mode, because the `{` and `}` characters are interpreted before the template is evaluated you must use `[[` for the `{` character and `]]` for the ``}`` character. they are converted automatically. Note also that prefixes and suffixes (the `|prefix|suffix` syntax) cannot be used in the argument to this function when using Template Program Mode.
    * ``field(name)`` -- returns the value of the metadata field named by ``name``.
    * ``field_exists(field_name)`` -- checks if a field (column) named ``field_name`` exists, returning ``'1'`` if so and ``''`` if not.
    * ``finish_formatting(val, fmt, prefix, suffix)`` -- apply the format, prefix, and suffix to a value in the same way as done in a template like ``{series_index:05.2f| - |- }``. This function is provided to ease conversion of complex single-function- or template-program-mode templates to General Program Mode Templates. For example, the following program produces the same output as the above template::

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

    * ``first_non_empty(value, value, ...)`` -- returns the first ``value`` that is not empty. If all values are empty, then the empty value is returned. You can have as many values as you want.
    * ``floor(x)`` -- returns the largest integer less than or equal to ``x``. Throws an exception if ``x`` is not a number.
    * ``format_date(val, format_string)`` -- format the value, which must be a date string, using the format_string, returning a string. The formatting codes are::

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

      You might get unexpected results if the date you are formatting contains localized month names, which can happen if you changed the date format tweaks to contain ``MMMM``. In this case, instead of using something like ``format_date(field('pubdate'), 'yyyy')``, write the template using ``raw_field``, as in ``format_date(raw_field('pubdate'), 'yyyy')``.
    * ``formats_modtimes(date_format_string)`` -- return a comma-separated list of colon-separated items ``FMT:DATE`` representing modification times for the formats of a book. The ``date_format_string`` parameter specifies how the date is to be formatted. See the ``format_date()`` function for details. You can use the ``select`` function to get the modification time for a specific format. Note that format names are always uppercase, as in EPUB.
    * ``formats_paths()`` -- return a comma-separated list of colon-separated items ``FMT:PATH`` giving the full path to the formats of a book. You can use the select function to get the path for a specific format. Note that format names are always uppercase, as in EPUB.
    * ``formats_sizes()`` -- return a comma-separated list of colon-separated ``FMT:SIZE`` items giving the sizes in bytes of the formats of a book. You can use the select function to get the size for a specific format. Note that format names are always uppercase, as in EPUB.
    * ``fractional_part(x)`` -- returns the value after the decimal point. For example, ``fractional_part(3.14)`` returns ``0.14``. Throws an exception if ``x`` is not a number.
    * ``has_cover()`` -- return ``'Yes'`` if the book has a cover, otherwise the empty string.
    * ``is_marked()`` -- check whether the book is `marked` in calibre. If it is then return the value of the mark, either ``'true'`` (lower case) or a comma-separated list of named marks. Returns ``''`` (the empty string) if the book is not marked. This function works only in the GUI.
    * ``list_contains(separator, pattern, found_val, ..., not_found_val)`` -- (Alias of ``in_list``) Interpret the value as a list of items separated by ``separator``, evaluating the ``pattern`` against each value in the list. If the ``pattern`` matches any value, return ``found_val``, otherwise return ``not_found_val``. The ``pattern`` and ``found_value`` can be repeated as many times as desired, permitting returning different values depending on the search. The patterns are checked in order. The first match is returned. Aliases: ``in_list()``, ``list_contains()``
    * ``list_count(separator)`` -- interprets the value as a list of items separated by ``separator``, returning the number of items in the list. Aliases: ``count()``, ``list_count()``
    * ``list_count_matching(list, pattern, separator)`` -- interprets ``list`` as a list of items separated by ``separator``, returning the number of items in the list that match the regular expression ``pattern``. Aliases: ``list_count_matching()``, ``count_matching()``
    * ``list_difference(list1, list2, separator)`` -- return a list made by removing from ``list1`` any item found in ``list2`` using a case-insensitive comparison. The items in ``list1`` and ``list2`` are separated by separator, as are the items in the returned list.
    * ``list_equals(list1, sep1, list2, sep2, yes_val, no_val)`` -- return ``yes_val`` if ``list1`` and `list2` contain the same items, otherwise return ``no_val``. The items are determined by splitting each list using the appropriate separator character (``sep1`` or ``sep2``). The order of items in the lists is not relevant. The comparison is case-insensitive.
    * ``list_intersection(list1, list2, separator)`` -- return a list made by removing from ``list1`` any item not found in ``list2``, using a case-insensitive comparison. The items in ``list1`` and ``list2`` are separated by separator, as are the items in the returned list.
    * ``list_re(src_list, separator, include_re, opt_replace)`` -- Construct a list by first separating ``src_list`` into items using the ``separator`` character. For each item in the list, check if it matches ``include_re``. If it does then add it to the list to be returned. If ``opt_replace`` is not the empty string then apply the replacement before adding the item to the returned list.
    * ``list_re_group(src_list, separator, include_re, search_re, template_for_group_1, for_group_2, ...)`` -- Like list_re except replacements are not optional. It uses ``re_group(item, search_re, template ...)`` when doing the replacements.
    * ``list_remove_duplicates(list, separator)`` -- return a list made by removing duplicate items in ``list``. If items differ only in case then the last is returned. The items in ``list`` are separated by ``separator``, as are the items in the returned list.
    * ``list_sort(list, direction, separator)`` -- return ``list`` sorted using a case-insensitive lexical sort. If ``direction`` is zero, ``list`` is sorted ascending, otherwise descending. The list items are separated by ``separator``, as are the items in the returned list.
    * ``list_union(list1, list2, separator)`` -- return a list made by merging the items in ``list1`` and ``list2``, removing duplicate items using a case-insensitive comparison. If items differ in case, the one in ``list1`` is used. The items in ``list1`` and ``list2`` are separated by ``separator``, as are the items in the returned list. Aliases: ``merge_lists()``, ``list_union()``
    * ``mod(x, y)`` -- returns the ``floor`` of the remainder of ``x / y``. Throws an exception if either ``x`` or ``y`` is not a number.
    * ``multiply(x, y, ...)`` -- returns the product of its arguments. Throws an exception if any argument is not a number. This function can usually be replaced by the ``*`` operator.
    * ``not(value)`` -- returns the string "1" if the value is empty, otherwise returns the empty string. This function can usually be replaced with the unary not (``!``) operator.
    * ``ondevice()`` -- return the string ``'Yes'`` if ``ondevice`` is set, otherwise return the empty string.
    * ``or(value, value, ...)`` -- returns the string ``"1"`` if any value is not empty, otherwise returns the empty string. You can have as many values as you want. This function can usually be replaced by the ``||`` operator. A reason it cannot be replaced is if short-circuiting will change the results.
    * ``print(a, b, ...)`` -- prints the arguments to standard output. Unless you start calibre from the command line (``calibre-debug -g``), the output will go to a black hole. The ``print`` function always returns the empty string.
    * ``raw_field(name [, optional_default]))`` -- returns the metadata field named by name without applying any formatting. It evaluates and returns the optional second argument ``optional_default`` if the field's value is undefined (``None``).
    * ``raw_list(``lookup_name``, separator)`` -- returns the metadata list named by ``lookup_name`` without applying any formatting or sorting and with items separated by separator.
    * ``re_group(value, pattern, template_for_group_1, for_group_2, ...)`` --  return a string made by applying the regular expression pattern to ``value`` and replacing each matched instance with the the value returned by the corresponding template. In Template Program Mode, like for the ``template`` and the ``eval`` functions, you use ``[[`` for ``{`` and ``]]`` for ``}``.

      The following example looks for a series with more than one word and uppercases the first word::

        program: re_group(field('series'), "(\S* )(.*)", "{$:uppercase()}", "{$}")'}

    * ``round(x)`` -- returns the nearest integer to ``x``. Throws an exception if ``x`` is not a number.
    * ``series_sort()`` -- returns the series sort value.
    * ``split(list_val, sep, id_prefix)`` -- splits ``list_val`` into separate values using ``sep``, then assigns the values to variables named ``id_prefix_N`` where N is the position of the value in the list. The first item has position 0 (zero). The function returns the last element in the list.

      Example::

        split('one, two, foo', ',', 'var')

      is equivalent to::

        var_0 = 'one';
        var_1 = 'two';
        var_3 = 'foo

    * ``strcat(a, b, ...)`` -- can take any number of arguments. Returns a string formed by concatenating all the arguments.
    * ``strcat_max(max, string1, prefix2, string2, ...)`` -- Returns a string formed by concatenating the arguments. The returned value is initialized to ``string1``. Strings made from ``prefix, string`` pairs are added to the end of the value as long as the resulting string length is less than ``max``. Prefixes can be empty. Returns ``string1`` even if ``string1`` is longer than ``max``. You can pass as many ``prefix, string`` pairs as you wish.
    * ``strcmp(x, y, lt, eq, gt)`` -- does a case-insensitive lexical comparison of ``x`` and ``y``. Returns ``lt`` if ``x < y``, ``eq`` if ``x == y``, otherwise ``gt``.
    * ``strlen(value)`` -- Returns the length of the string ``value``.
    * ``substr(str, start, end)`` -- returns the ``start``'th through the ``end``'th characters of ``str``. The first character in ``str`` is the zero'th character. If ``end`` is negative, then it indicates that many characters counting from the right. If ``end`` is zero, then it indicates the last character. For example, ``substr('12345', 1, 0)`` returns ``'2345'``, and ``substr('12345', 1, -1)`` returns ``'234'``.
    * ``subtract(x, y)`` -- returns ``x - y``. Throws an exception if either ``x`` or ``y`` are not numbers. This function can usually be replaced by the ``-`` operator.
    * ``today()`` -- return a date+time string for today (now). This value is designed for use in `format_date` or `days_between`, but can be manipulated like any other string. The date is in `ISO <https://en.wikipedia.org/wiki/ISO_8601>`_ date/time format.
    * ``template(x)`` -- evaluates ``x`` as a template. The evaluation is done in its own context, meaning that variables are not shared between the caller and the template evaluation.

.. _template_mode:

More complex programs in templates - Template Program Mode
-------------------------------------------------------------

Template Program Mode is a blend of :ref:`General Program Mode <general_mode>` and
:ref:`Single Function Mode <single_mode>`. Template Program Mode differs from
Single Function Mode in that it permits writing template expressions that refer to other metadata fields, use nested functions, modify variables, and do arithmetic. It differs from General Program Mode in that the template is contained between ``{`` and ``}`` characters and doesn't begin with the word ``program:``. The program portion of the template is a General Program Mode expression list.

Example: assume you want a template to show the series for a book if it has one, otherwise show
the value of a custom field #genre. You cannot do this in the :ref:`Single Function Mode <single_mode>` because you cannot make reference to another metadata field within a template expression. In Template Program Mode you can, as the following expression demonstrates::

    {#series:'ifempty($, field('#genre'))'}

The example shows several things:

    * Template Program Mode is used if the expression begins with ``:'`` and ends with ``'``. Anything else is assumed to be in :ref:`Single Function Mode <single_mode>`.
    * the variable ``$`` stands for the field named in the template: the expression is operating upon, ``#series`` in this case.
    * functions must be given all their arguments. There is no default value. For example, the standard built-in functions must be given an additional initial parameter indicating the source field.
    * white space is ignored and can be used anywhere within the expression.
    * constant strings are enclosed in matching quotes, either ``'`` or ``"``.

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

    * specifies that the value being used is the field `series_index`. The variable ``$`` is set to its value.
    * calls the ``substr`` function, which takes 3 parameters ``(str, start, end)``. It returns a string formed by extracting the ``start`` through ``end`` characters from string, zero-based (the first character is character zero). In this case ``substr`` will return the first 6 characters of the string returned by ``strcat``, which must be evaluated before substr can return.
    * calls the ``strcat`` (string concatenation) function. Strcat accepts 1 or more arguments, and returns a string formed by concatenating all the arguments. In this case there are three arguments. The first parameter is the value in ``$``, here the value of ``series_index``. The second paremeter is the constant string ``'->'``. The third parameter is the value returned by the ``cmp`` function, which must be fully evaluated before ``strcat`` can return.
    * The ``cmp`` function takes 5 arguments ``(x, y, lt, eq, gt)``. It compares ``x`` and ``y`` and returns the third argument ``lt`` if ``x < y``, the fourth argument ``eq`` if ``x == y``, and the fifth argument ``gt`` if ``x > y``. As with all functions, all of the parameters can be an ``expression list``. In this case the first argument (the value for ``x``) is the result of dividing the ``series_index`` by 2. The second argument ``y`` is the constant ``1``. The third argument ``lt`` is an ``expression_list`` (more later). The fourth argument ``eq`` is the constant string ``'eq'``. The fifth argument is the constant string ``'gt'``.
    * The third argument (the one for ``lt``) is an ``expression_list``, or a sequence of ``top_expressions``. Remember that an ``expression_list`` is also an expression, returning the value of the last ``top_expression in the list``. In this case, the program first assigns the value ``1`` to a local variable ``c``, then returns a substring made by extracting the ``c``'th character to the end. Since ``c`` always contains the constant ``1``, the substring will return the second through ``end``'th characters, or ``'t123'``.
    * Once the statement providing the value to the third parameter is executed, ``cmp`` can return a value. At that point, ``strcat` can return a value, then ``substr`` can return a value. The program then terminates.

For various values of series_index, the program returns:

    * series_index == undefined, result = ``prefix ->t123 suffix``
    * series_index == 0.5, result = ``prefix 0.50-> suffix``
    * series_index == 1, result = ``prefix 1->t12 suffix``
    * series_index == 2, result = ``prefix 2->eq suffix``
    * series_index == 3, result = ``prefix 3->gt suffix``

**All the functions listed under :ref:`Single Function Mode <single_mode>`
and :ref:`General Program Mode <general_mode>` can be used in Template Program Mode**.

For functions documented under :ref:`Single Function Mode <single_mode>` you must supply the value the function is to act upon as the first parameter in addition to the documented parameters. In Template Program Mode you can use ``$`` to access the value specified for the template. In General Program Mode that first parameter is frequently be a variable or a function call, often `field()`.


Stored General Program Mode Templates
----------------------------------------

:ref:`General Program Mode <general_mode>` supports saving templates and calling those templates from another template. You save templates using :guilabel:`Preferences->Advanced->Template functions`. More information is provided in that dialog. You call a template the same way you call a function, passing positional arguments if desired. An argument can be any expression. Examples of calling a template, assuming the stored template is named ``foo``:

    * ``foo()`` -- call the template passing no arguments.
    * ``foo(a, b)`` call the template passing the values of the two variables ``a`` and ``b``.
    * ``foo(if field('series') then field('series_index') else 0 fi)`` -- if the book has a ``series`` then pass the ``series_index``, otherwise pass the value ``0``.

In the stored template you retrieve the arguments passed in the call using the ``arguments`` function. It both declares and initializes local variables, effectively parameters. The variables are positional; they get the value of the value given in the call in the same position. If the corresponding parameter is not provided in the call then ``arguments`` assigns that variable the provided default value. If there is no default value then the variable is set to the empty string. For example, the following ``arguments`` function declares 2 variables, ``key``, ``alternate``::

            arguments(key, alternate='series')

Examples, again assuming the stored template is named ``foo``:

    * ``foo('#myseries')`` -- argument ``key`` will have the value ``myseries`` and the argument ``alternate`` will have the value ``series``.
    * ``foo('series', '#genre')`` the variable ``key`` is assigned the value ``series`` and the variable ``alternate`` is assigned the value ``#genre``.
    * ``foo()`` -- the variable ``key`` is assigned the empty string and the variable ``alternate`` is assigned the value ``#genre``.

An easy way to test stored templates is using the ``Template tester`` dialog. Give it a keyboard shortcut in :guilabel:`Preferences->Advanced->Keyboard shortcuts->Template tester`. Giving the ``Stored templates`` dialog a shortcut will help switching more rapidly between the tester and editing the stored template's source code.

Providing additional information to templates
----------------------------------------------

A developer can choose to pass additional information to the template processor, such as application-specific book metadata or information about what the processor is being asked to do. A template can access this information and use it during the evaluation.

**Developer: how to pass additional information**

The additional information is a Python dictionary containing pairs ``variable_name: variable_value`` where the values must be strings. The template can access the dict, creating template local variables named ``variable_name`` containing the value ``variable_value``. The user cannot change the name so it is best to use names that won't collide with other template local variables, for example by prefixing the name with an underscore.

This dict is passed to the template processor (the ``formatter``) using the named parameter ``global_vars=your_dict``. The full method signature is:

    def safe_format(self, fmt, kwargs, error_value, book,
                    column_name=None, template_cache=None,
                    strip_results=True, template_functions=None,
                    global_vars={})


**Template writer: how to access the additional information**

You access the additional information (the ``globals`` dict) in a template using the template function::

  globals(id[=expression] [, id[=expression]]*)

where ``id`` is any legal variable name. This function checks whether the additional information provided by the developer contains the name. If it does then the function assigns the provided value to a template local variable with that name. If the name is not in the additional information and if an ``expression`` is provided, the ``expression`` is evaluated and the result is assigned to the local variable. If neither a value nor an expression is provided, the function assigns the empty string (``''``) to the local variable.

A template can set a value in the ``globals`` dict using the template function::

  set_globals(id[=expression] [, id[=expression]]*)

This function sets the ``globals`` dict key:value pair ``id:value`` where ``value`` is the value of the template local variable ``id``. If that local variable doesn't exist then ``value`` is set to the result of evaluating ``expression``.


Notes on the difference between modes
-----------------------------------------

The three program modes, :ref:`Single Function Mode <single_mode>` (SFM), :ref:`Template Program Mode <template_mode>` (TPM), and :ref:`General Program Mode <general_mode>` (GPM), work differently. SFM is intended to be 'simple' so it hides a lot of programming language bits. For example, the value of the column is always passed as an 'invisible' first argument to a function included in the template. SFM also doesn't support the difference between variables and strings; all values are strings.

Example: the following SFM template returns either the series name or the string "no series"::

    {series:ifempty(no series)}

The equivalent template in TPM is ::

    {series:'ifempty($, 'no series')'}

The equivalent template in GPM is::

    program: ifempty(field('series'), 'no series')

The first argument to ``ifempty`` is the value of the field ``series``. The second argument is the string ``no series``. In SFM the first argument, the value of the field, is automatically passed (the invisible argument).

Several template functions, for example ``booksize()`` and ``current_library_name()``, take no arguments. Because of the 'invisible argument' you cannot use these functions in SFM.

Nested functions, where a function calls another function to compute an argument, cannot be used in SFM. For example this template, intended to return the first 5 characters of the series value uppercased, won't work in SFM::

    {series:uppercase(substr(0,5))}

TPM and GPM support nested functions. The above template in TPM would be::

    {series:'uppercase(substr($, 0,5))'}

In GPM it would be::

    program: uppercase(substr(field('series'), 0,5))


User-defined Python template functions
------------------------------------------

You can add your own Python functions to the template processor. Such functions can be used in any of the three template programming modes. The functions are added by going to :guilabel:`Preferences -> Advanced -> Template functions`. Instructions are shown in that dialog.

Special notes for save/send templates
---------------------------------------

Special processing is applied when a template is used in a `save to disk` or `send to device` template. The values of the fields are cleaned, replacing characters that are special to file systems with underscores, including slashes. This means that field text cannot be used to create folders. However, slashes are not changed in prefix or suffix strings, so slashes in these strings will cause folders to be created. Because of this, you can create variable-depth folder structure.

For example, assume we want the folder structure `series/series_index - title`, with the caveat that if series does not exist, then the title should be in the top folder. The template to do this is::

    {series:||/}{series_index:|| - }{title}

The slash and the hyphen appear only if series is not empty.

The lookup function lets us do even fancier processing. For example, assume that if a book has a series, then we want the folder structure `series/series index - title.fmt`. If the book does not have a series then we want the folder structure `genre/author_sort/title.fmt`. If the book has no genre then we want to use 'Unknown'. We want two completely different paths, depending on the value of series.

To accomplish this, we:
    1. Create a composite field (give it lookup name #aa) containing ``{series}/{series_index} - {title}``. If
       the series is not empty, then this template will produce `series/series_index - title`.
    2. Create a composite field (give it lookup name #bb) containing ``{#genre:ifempty(Unknown)}/{author_sort}/{title}``.
       This template produces `genre/author_sort/title`, where an empty genre is replaced with `Unknown`.
    3. Set the save template to ``{series:lookup(.,#aa,#bb}``. This template chooses composite field ``#aa`` if series is not empty and composite field ``#bb`` if series is empty. We therefore have two completely different save paths, depending on whether or not `series` is empty.

Templates and plugboards
---------------------------

Plugboards are used for changing the metadata written into books during send-to-device and save-to-disk operations. A plugboard permits you to specify a template to provide the data to write into the book's metadata. You can use plugboards to modify the following fields: authors, author_sort, language, publisher, tags, title, title_sort. This feature helps people who want to use different metadata in books on devices to solve sorting or display issues.

When you create a plugboard, you specify the format and device for which the plugboard is to be used. A special device is provided, ``save_to_disk``, that is used when saving formats (as opposed to sending them to a device). Once you have chosen the format and device, you choose the metadata fields to change, providing templates to supply the new values. These templates are `connected` to their destination fields, hence the name `plugboards`. You can of course use composite columns in these templates.

When a plugboard might apply (Content server, save to disk, or send to device), calibre searches the
defined plugboards to choose the correct one for the given format and device. For example, to find the appropriate plugboard for an EPUB book being sent to an ANDROID device, calibre searches
the plugboards using the following search order:

    * a plugboard with an exact match on format and device, e.g., ``EPUB`` and ``ANDROID``
    * a plugboard with an exact match on format and the special ``any device`` choice, e.g., ``EPUB`` and ``any device``
    * a plugboard with the special ``any format`` choice and an exact match on device, e.g., ``any format`` and ``ANDROID``
    * a plugboard with ``any format`` and ``any device``

The tags and authors fields have special treatment, because both of these fields can hold more than one item. A book can have many tags and many authors. When you specify that one of these two fields is to be changed, the template's result is examined to see if more than one item is there. For tags, the result is cut apart wherever calibre finds a comma. For example, if the template produces
the value ``Thriller, Horror``, then the result will be two tags, ``Thriller`` and ``Horror``. There is no way to put a comma in the middle of a tag.

The same thing happens for authors, but using a different character for the cut, a `&` (ampersand) instead of a comma. For example, if the template produces the value ``Blogs, Joe&Posts, Susan``, then the book will end up with two authors, ``Blogs, Joe`` and ``Posts, Susan``. If the template produces the value ``Blogs, Joe;Posts, Susan``, then the book will have one author with a rather strange name.

Plugboards affect the metadata written into the book when it is saved to disk or written to the device. Plugboards do not affect the metadata used by ``save to disk`` and ``send to device`` to create the file names. Instead, file names are constructed using the templates entered on the appropriate preferences window.

Tips:
------------

    * Use the Template Tester to test templates. Add the tester to the context menu for books in the
      library and/or give it a keyboard shortcut.
    * Templates can use other templates by referencing composite columns built with the desired template. Alternatively, you can use Stored Templates.
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
