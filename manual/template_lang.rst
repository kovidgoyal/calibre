.. _templatelangcalibre:

The calibre template language
=======================================================

The calibre template language is a calibre-specific language used throughout calibre for tasks such as specifying file paths, formatting values, and computing the value for user-specified columns. Examples:

* Specify the folder structure and file names when saving files from the calibre library to the disk or e-book reader.
* Define rules for adding icons and colors to the calibre book list.
* Define `virtual columns` that contain data from other columns.
* Advanced library searching.
* Advanced metadata search and replace.

The language is built around the notion of a `template`, which specifies which book metadata to use, computations on that metadata, and how it is to be formatted.

Basic templates
---------------

A basic template consists one or more ``template expressions``. A ``template expression`` consists of text and names in curly brackets (``{}``) that is replaced by the corresponding metadata from the book being processed. For example, the default template in calibre used for saving books to device has 4 ``template expressions``::

    {author_sort}/{title}/{title} - {authors}

For the book "The Foundation" by "Isaac Asimov" the  will become::

    Asimov, Isaac/The Foundation/The Foundation - Isaac Asimov

The slashes are not ``template expressions`` because they are in between in ``{}``. Such text is left where it appears. For example, if the template is::

    {author_sort} Some Important Text {title}/{title} - {authors}

then for "The Foundation" the template produces::

    Asimov, Isaac Some Important Text The Foundation/The Foundation - Isaac Asimov

A ``template expression`` can access all the metadata available in calibre, including custom columns (columns you create yourself), by using a column's ``lookup name``. To find the lookup name for a `column` (sometimes called `fields`), hover your mouse over the column header in calibre's book list. Lookup names for custom columns always begin with ``#``. For series type columns there is an additional field named ``#lookup name_index`` that is the series index for that book in the series. For example, if you have a custom series column named ``#myseries``, there will also be a column named ``#myseries_index``. The standard series column's index is named ``series_index``.

In addition to the standard column based fields, you also can use:

  * ``{formats}`` - A list of formats available in the calibre library for a book
  * ``{identifiers:select(isbn)}`` - The ISBN of the book

If the metadata for the field for a given book is not defined then the field in the template is replaced by the empty string (``''``). For example, consider the following template::

    {author_sort}/{series}/{title} {series_index}

If Asimov's book "Second Foundation" is in the series "Foundation" then the template produces::

    Asimov, Isaac/Foundation/Second Foundation 3

If a series has not been entered for the book then the template produces::

    Asimov, Isaac/Second Foundation

The template processor automatically removes multiple slashes and leading or trailing spaces.

Advanced formatting
----------------------

In addition to metadata substitution, templates can conditionally include additional text and control how substituted data is formatted.

**Conditionally including text**

Sometimes you want text to appear in the output only if a field is not empty. A common case is ``series`` and ``series_index`` where you want either nothing or the two values separated by a hyphen. calibre handles this case using a special ``template expression`` syntax.

For example and using the above Foundation example, assume you want the template to produce `Foundation - 3 - Second Foundation`. This template produces that output:

  ``{series} - {series_index} - {title}``

However, if a book has no series the template will produce `- - the title`, which is probably not what you want. Generally, people want the result be the title without the extraneous hyphens. You can accomplish this using the following template syntax:

  ``{field:|prefix_text|suffix_text}``

This ``template expression`` says that if ``field`` has the value `XXXX` then the result will be `prefix_textXXXXXsuffix_text`. If ``field`` is empty (has no value) then the result will be the empty string (nothing) because the prefix and suffix are ignored. The prefix and suffix can contain blanks.

**Do not use subtemplates (`{ ... }`) or functions (see below) in the prefix or the suffix.**

Using this syntax, we can solve the above no-series problem with the template::

  {series}{series_index:| - | - }{title}

The hyphens will be included only if the book has a series index, which it has only if it has a series. Continuing the Foundation example again, the template will produce `Foundation - 1 - Second Foundation`.

Notes:

* You must include the colon after the ``lookup name`` if you are using a prefix or a suffix.
* You must either use either no or both ``|`` characters. Using one, as in ``{field:| - }``, is not allowed.
* It is OK to provide no text for either the prefix or the suffix, such as in ``{series:|| - }``. The template ``{title:||}`` is the same as ``{title}``.

**Formatting**

Suppose you want the ``series_index`` to be formatted as three digits with leading zeros. This does the trick:

  ``{series_index:0>3s}`` - Three digits with leading zeros

For trailing zeros, use:

  ``{series_index:0<3s}`` - Three digits with trailing zeros

If you use series indices with fractional values, e.g., 1.1, you might want the decimal points to line up. For example, you might want the indices 1 and 2.5 to appear as 01.00 and 02.50 so that they will sort correctly on a device that does lexical sorting. To do this, use:

  ``{series_index:0>5.2f}`` - Five characters consisting of two digits with leading zeros, a decimal point, then 2 digits after the decimal point.

If you want only the first two letters of the data, use:

  ``{author_sort:.2}`` - Only the first two letters of the author sort name

Much of the calibre template language formatting comes from Python. For more details on the syntax of these advanced formatting operations see the `Python documentation <https://docs.python.org/3/library/string.html#formatstrings>`_.


Using templates to define custom columns
-----------------------------------------

Templates can be used to display information that isn't in calibre metadata, or to display metadata differently from calibre's normal format. For example, you might want to show the ``ISBN``, a field that calibre does not display. You can accomplish this creating a custom column with the type `Column built from other columns` (hereafter called `composite columns`) and providing a template to generate the displayed text. The column will display the result of evaluating the template. For example, to display the ISBN, create the column and enter ``{identifiers:select(isbn)}`` in the template box. To display a column containing the values of two series custom columns, separated by a comma, use ``{#series1:||,}{#series2}``.

Composite columns can use any template option, including formatting.

Note: You cannot edit the data displayed in a composite column. Instead you edit the source columns. If you edit a composite column, for example by double-clicking it, calibre will open the template for editing, not the underlying data.


Templates and plugboards
---------------------------

Plugboards are used for changing the metadata written into books during send-to-device and save-to-disk operations. A plugboard permits you to specify a template to provide the data to write into the book's metadata. You can use plugboards to modify the following fields: authors, author_sort, language, publisher, tags, title, title_sort. This feature helps people who want to use different metadata in books on devices to solve sorting or display issues.

When you create a plugboard, you specify the format and device for which the plugboard is to be used. A special device is provided, ``save_to_disk``, that is used when saving formats (as opposed to sending them to a device). Once you have chosen the format and device, you choose the metadata fields to change, providing templates to supply the new values. These templates are `connected` to their destination fields, hence the name `plugboards`. You can of course use composite columns in these templates.

Plugboards are quite flexible and can be written in Single Function Mode, Template Program Mode, General Program Mode, or Python Template mode.

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

.. _single_mode:

Using functions in templates - Single Function Mode
---------------------------------------------------

Suppose you want to display the value of a field in upper case when that field is normally in title case. You can do this using `template functions`. For example, to display the title in upper case use the ``uppercase`` function, as in ``{title:uppercase()}``. To display it in title case, use ``{title:titlecase()}``.

Functions go into the format part of the template, after the ``:`` and before the first ``|`` or the closing ``}`` if no prefix/suffix is used. If you have both a format and a function reference, the function comes after a second ``:``.  Functions return the value of the column specified in the template, suitably modified.

The syntax for using functions is one of::

  {lookup_name:function(arguments)}
  {lookup_name:format:function(arguments)}
  {lookup_name:function(arguments)|prefix|suffix}
  {lookup_name:format:function(arguments)|prefix|suffix}

Function names must always be followed by opening and closing parentheses. Some functions require extra values (arguments), and these go inside the parentheses. Arguments are separated by commas. Literal commas (commas as text, not argument separators) must be preceded by a backslash (``\``) . The last (or only) argument cannot contain a textual closing parenthesis.

Functions are evaluated before format specifications and the prefix/suffix. See further down for an example of using both a format and a function.

**Important**: If you have programming experience, please note that the syntax in `Single Function Mode` is not what you expect. Strings are not quoted and spaces are significant. All arguments are considered to be constants; there are no expressions.

**Do not use subtemplates (`{ ... }`) as function arguments.** Instead, use :ref:`Template Program Mode <template_mode>` and :ref:`General Program Mode <general_mode>`.

Notes on calling functions in Single Function Mode:

* When functions are used in Single Function Mode, the first parameter, ``value``, is automatically replaced by the content of the field specified in the template. For example, when the template ``{title:capitalize()}`` is processed, the content of the ``title`` field is passed as the parameter ``value`` to the capitalize function.
* In the function documentation, the notation ``[something]*`` means that ``something`` can be repeated zero or more times. The notation ``[something]+`` means that the ``something`` is repeated one or more times (must exist at least one time).
* Some functions use regular expressions. In the template language regular expression matching is case-insensitive.

Functions are documented in :ref:`template_functions_reference`. The documentation tells you what arguments the functions require and what the functions do. For example, here is the documentation of the :ref:`ff_ifempty` function.

* :ffdoc:`ifempty`

You see that the function requires two arguments, ``value`` and ``text_if_empty``. However, because we are using Single Function Mode, we omit the ``value`` argument, passing only ``text_if_empty``. For example, this template::

  {tags:ifempty(No tags on this book)}

shows the tags for a book, if any. If it has no tags then it show `No tags on this book`.

The following functions are usable in Single Function Mode because their first parameter is ``value``.

* :ffsum:`capitalize`
* :ffsum:`ceiling`
* :ffsum:`cmp`
* :ffsum:`contains`
* :ffsum:`date_arithmetic`
* :ffsum:`floor`
* :ffsum:`format_date`
* :ffsum:`format_number`
* :ffsum:`fractional_part`
* :ffsum:`human_readable`
* :ffsum:`ifempty`
* :ffsum:`language_strings`
* :ffsum:`list_contains`
* :ffsum:`list_count`
* :ffsum:`list_count_matching`
* :ffsum:`list_item`
* :ffsum:`list_sort`
* :ffsum:`lookup`
* :ffsum:`lowercase`
* :ffsum:`mod`
* :ffsum:`rating_to_stars`
* :ffsum:`re`
* :ffsum:`re_group`
* :ffsum:`round`
* :ffsum:`select`
* :ffsum:`shorten`
* :ffsum:`str_in_list`
* :ffsum:`subitems`
* :ffsum:`sublist`
* :ffsum:`substr`
* :ffsum:`swap_around_articles`
* :ffsum:`swap_around_comma`
* :ffsum:`switch`
* :ffsum:`test`
* :ffsum:`titlecase`
* :ffsum:`transliterate`
* :ffsum:`uppercase`

**Using functions and formatting in the same template**

Suppose you have an integer custom column ``#myint`` that you want displayed with leading zeros, as in ``003``. One way to do this is to use a format of ``0>3s``. However, by default if a number (integer or float) equals zero then the value is displayed as the empty string so zero values will produce the empty string, not ``000``. If you want to see ``000`` values then you use both the format string and the ``ifempty`` function to change the empty value back to a zero. The template would be::

    {#myint:0>3s:ifempty(0)}

Note that you can use the prefix and suffix as well. If you want the number to appear as ``[003]`` or ``[000]``, then use the template::

    {#myint:0>3s:ifempty(0)|[|]}

.. _general_mode:

General Program Mode
-----------------------------------

`General Program Mode` (`GPM`) replaces `template expressions` with a program written in the `template language`. The syntax of the language is defined by the following grammar::

    program         ::= 'program:' expression_list
    expression_list ::= top_expression [ ';' top_expression ]*
    top_expression  ::= or_expression
    or_expression   ::= and_expression [ '||' and_expression ]*
    and_expression  ::= not_expression [ '&&' not_expression ]*
    not_expression  ::= [ '!' not_expression ]* | concatenate_expr
    concatenate_expr::= compare_expr [ '&' compare_expr ]*
    compare_expr    ::= add_sub_expr [ compare_op add_sub_expr ]
    compare_op      ::= '==' | '!=' | '>=' | '>' | '<=' | '<' |
                        'in' | 'inlist' | 'inlist_field' |
                        '==#' | '!=#' | '>=#' | '>#' | '<=#' | '<#'
    add_sub_expr    ::= times_div_expr [ add_sub_op times_div_expr ]*
    add_sub_op      ::= '+' | '-'
    times_div_expr  ::= unary_op_expr [ times_div_op unary_op_expr ]*
    times_div_op    ::= '*' | '/'
    unary_op_expr   ::= [ add_sub_op unary_op_expr ]* | expression
    expression      ::= identifier | constant | function | assignment | field_reference |
                        if_expr | for_expr | break_expr | continue_expr |
                        '(' expression_list ')' | function_def
    field_reference ::= '$' [ '$' ] [ '#' ] identifier
    identifier      ::= id_start [ id_rest ]*
    id_start        ::= letter | underscore
    id_rest         ::= id_start | digit
    constant        ::= " string " | ' string ' | number
    function        ::= identifier '(' expression_list [ ',' expression_list ]* ')'
    function_def    ::= 'def' identifier '(' top_expression [ ',' top_expression ]* ')' ':'
                        expression_list 'fed'
    assignment      ::= identifier '=' top_expression
    if_expr         ::= 'if' condition 'then' expression_list
                        [ elif_expr ] [ 'else' expression_list ] 'fi'
    condition       ::= top_expression
    elif_expr       ::= 'elif' condition 'then' expression_list elif_expr | ''
    for_expr        ::= for_list | for_range
    for_list        ::= 'for' identifier 'in' list_expr
                        [ 'separator' separator_expr ] ':' expression_list 'rof'
    for_range       ::= 'for' identifier 'in' range_expr ':' expression_list 'rof'
    range_expr      ::= 'range' '(' [ start_expr ',' ] stop_expr
                        [ ',' step_expr [ ',' limit_expr ] ] ')'
    list_expr       ::= top_expression
    break_expr      ::= 'break'
    continue_expr   ::= 'continue'
    separator_expr  ::= top_expression
    start_expr      ::= top_expression
    stop_expr       ::= top_expression
    step_expr       ::= top_expression
    limit_expr      ::= top_expression

Notes:

* a ``top_expression`` always has a value. The value of an ``expression_list`` is the value of the last ``top_expression`` in the list. For example, the value of the expression list ``1;2;'foobar';3`` is ``3``.
* In a logical context, any non-empty value is ``True``
* In a logical context, the empty value is ``False``
* Strings and numbers can be used interchangeably. For example, ``10`` and ``'10'`` are the same thing.
* Comments are lines starting with a '#' character. Comments beginning later in a line are not supported.

**Operator precedence**

The operator precedence (order of evaluation) from highest (evaluated first) to lowest (evaluated last) is:

* Function calls, constants, parenthesized expressions, statement expressions, assignment expressions, field references.
* Unary plus (``+``) and minus (``-``). These operators evaluate right to left.

  These and all the other arithmetic operators return integers if the expression results in a fractional part equal to zero. For example, if an expression returns ``3.0`` it is changed to ``3``.
* Multiply (``*``) and divide (``/``). These operators are associative and evaluate left to right. Use parentheses if you want to change the order of evaluation.
* Add (``+``) and subtract (``-``). These operators are associative and evaluate left to right.
* Numeric and string comparisons. These operators return ``'1'`` if the comparison succeeds, otherwise the empty string (``''``). Comparisons are not associative: ``a < b < c`` is a syntax error.
* String concatenation (``&``). The ``&`` operator returns a string formed by concatenating the left-hand and right-hand expressions. Example: ``'aaa' & 'bbb'`` returns ``'aaabbb'``. The operator is associative and evaluates left to right.
* Unary logical not (``!``). This operator returns ``'1'`` if the expression is False (evaluates to the empty string), otherwise ``''``.
* Logical and (``&&``). This operator returns '1' if both the left-hand and right-hand expressions are True, or the empty string ``''`` if either is False. It is associative, evaluates left to right, and does `short-circuiting <https://chortle.ccsu.edu/java5/Notes/chap40/ch40_2.html>`_.
* Logical or (``||``). This operator returns ``'1'`` if either the left-hand or right-hand expression is True, or ``''`` if both are False. It is associative, evaluates left to right, and does `short-circuiting <https://chortle.ccsu.edu/java5/Notes/chap40/ch40_2.html>`_. It is an `inclusive or`, returning ``'1'`` if both the left- and right-hand expressions are True.

**Field references**

A ``field_reference`` evaluates to the value of the metadata field named by lookup name that follows the ``$`` or ``$$``. Using ``$`` is equivalent to using the :ref:`ff_field` function. Using ``$$`` is equivalent to using the :ref:`ff_raw_field` function. Examples::

* $authors ==> field('authors')
* $#genre ==> field('#genre')
* $$pubdate ==> raw_field('pubdate')
* $$#my_int ==> raw_field('#my_int')

**If expressions**

``If`` expressions first evaluate the ``condition``. If the ``condition`` is True (a non-empty value) then the ``expression_list`` in the ``then`` clause is evaluated. If it is False then if present the ``expression_list`` in the ``elif`` or ``else`` clause is evaluated. The ``elif`` and ``else`` parts are optional. The words ``if``, ``then``, ``elif``, ``else``, and ``fi`` are reserved; you cannot use them as identifier names. You can put newlines and white space wherever they make sense. The ``condition`` is a ``top_expression`` not an ``expression_list``; semicolons are not allowed. The ``expression_lists`` are semicolon-separated sequences of ``top_expressions``. An ``if`` expression returns the result of the last ``top_expression`` in the evaluated ``expression_list``, or the empty string if no expression list was evaluated.

Examples::

    * program: if field('series') then 'yes' else 'no' fi
    * program:
          if field('series') then
              a = 'yes';
              b = 'no'
          else
              a = 'no';
              b = 'yes'
          fi;
          strcat(a, '-', b)

Nested ``if`` example::

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

As said above, an ``if`` produces a value. This means that all the following are equivalent::

    * program: if field('series') then 'foo' else 'bar' fi
    * program: if field('series') then a = 'foo' else a = 'bar' fi; a
    * program: a = if field('series') then 'foo' else 'bar' fi; a

For example, this program returns the value of the ``series`` column if the book has a series, otherwise the value of the ``title`` column::

    program: field(if field('series') then 'series' else 'title' fi)

**For expressions**

The ``for`` expression iterates over a list of values, processing them one at a time. The ``list_expression`` must evaluate either to a metadata field ``lookup name`` e.g., ``tags`` or ``#genre``, or to a list of values. The :ref:`ff_range` generates a list of numbers. If the result is a valid ``lookup name`` then the field's value is fetched and the separator specified for that field type is used. If the result isn't a valid lookup name then it is assumed to be a list of values. The list is assumed to be separated by commas unless the optional keyword ``separator`` is supplied, in which case the list values must be separated by the result of evaluating the ``separator_expr``. A separator cannot be used if the list is generated by ``range()``. Each value in the list is assigned to the specified variable then the ``expression_list`` is evaluated. You can use ``break`` to jump out of the loop, and ``continue`` to jump to the beginning of the loop for the next iteration.

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

Note: the last line in the template, ``new_tags``, isn't strictly necessary in this case because ``for`` returns the value of the last top_expression in the expression list. The value of an assignment is the value of its expression, so the value of the ``for`` statement is what was assigned to ``new_tags``.

**Function definition**

If you have repeated code in a template then you can put that code into a local function. The ``def`` keyword starts the definition. It is followed by the function name, the argument list, then the code in the function. The function definition ends with the ``fed`` keyword.

Arguments are positional. When a function is called the supplied arguments are matched left to right against the defined parameters, with the value of the argument assigned to the parameter. It is an error to provide more arguments than defined parameters. Parameters can have default values, such as ``a = 25``. If an argument is not supplied for that parameter then the default value is used, otherwise the parameter is set to the empty string.

The ``return`` statement can be used in a local function.

A function must be defined before it can be used.

Example: This template computes an approximate duration in years, months, and days from a number of days. The function ``to_plural()`` formats the computed values. Note that the example also uses the ``&`` operator::

  program:
  	days = 2112;
	years = floor(days/360);
	months = floor(mod(days, 360)/30);
	days = days - ((years*360) + (months * 30));

	def to_plural(v, str):
		if v == 0 then return '' fi;
		return v & ' ' & (if v == 1 then str else str & 's' fi) & ' '
	fed;

	to_plural(years, 'year') & to_plural(months, 'month') & to_plural(days,'day')

**Relational operators**

Relational operators return ``'1'`` if the comparison is true, otherwise the empty string (``''``).

There are two forms of relational operators: string comparisons and numeric comparisons.

String comparisons do case-insensitive string comparison using lexical order. The supported string comparison operators are ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, ``in``, ``inlist``, and ``inlist_field``.
For the ``in`` operator, the result of the left hand expression is interpreted as a regular expression pattern. The ``in`` operator is True if the value of left-hand regular expression matches the value of the right hand expression.

The ``inlist`` operator is true if the left hand regular expression matches any one of the items in the right hand list where the items in the list are separated by commas. The ``inlist_field`` operator is true if the left hand regular expression matches any of the items in the field (column) named by the right hand expression, using the separator defined for the field. NB: the ``inlist_field`` operator requires the right hand expression to evaluate to a field name, while the ``inlist`` operator requires the right hand expression to evaluate to a string containing a comma-separated list. Because of this difference, ``inlist_field`` is substantially faster than ``inlist`` because no string conversions or list constructions are done. The regular expressions are case-insensitive.

The numeric comparison operators are ``==#``, ``!=#``, ``<#``, ``<=#``, ``>#``, ``>=#``. The left and right expressions must evaluate to numeric values with two exceptions: both the string value "None" (undefined field) and the empty string evaluate to the value zero.

Examples:

  * ``program: field('series') == 'foo'`` returns ``'1'`` if the book's series is `foo`, otherwise ``''``.
  * ``program: 'f.o' in field('series')`` returns ``'1'`` if the book's series matches the regular expression ``f.o`` (e.g., `foo`, `Off Onyx`, etc.), otherwise ``''``.
  * ``program: 'science' inlist $#genre`` returns ``'1'`` if any of the values retrieved from the book's genres match the regular expression ``science``, e.g., `Science`, `History of Science`, `Science Fiction` etc., otherwise ``''``.
  * ``program: '^science$' inlist $#genre`` returns ``'1'`` if any of the book's genres exactly match the regular expression ``^science$``, e.g., `Science`, otherwise ``''``. The genres `History of Science` and `Science Fiction` don't match.
  * ``program: 'asimov' inlist $authors`` returns ``'1'`` if any author matches the regular expression ``asimov``, e.g., `Asimov, Isaac` or `Isaac Asimov`, otherwise ``''``.
  * ``program: 'asimov' inlist_field 'authors'`` returns ``'1'`` if any author matches the regular expression ``asimov``, e.g., `Asimov, Isaac` or `Isaac Asimov`, otherwise ``''``.
  * ``program: 'asimov$' inlist_field 'authors'`` returns ``'1'`` if any author matches the regular expression ``asimov$``, e.g., `Isaac Asimov`, otherwise ``''``. It doesn't match `Asimov, Isaac` because of the ``$`` anchor in the regular expression.
  * ``program: if field('series') != 'foo' then 'bar' else 'mumble' fi`` returns ``'bar'`` if the book's series is not `foo`. Otherwise it returns ``'mumble'``.
  * ``program: if field('series') == 'foo' || field('series') == '1632' then 'yes' else 'no' fi`` returns ``'yes'`` if series is either `foo` or `1632`, otherwise ``'no'``.
  * ``program: if '^(foo|1632)$' in field('series') then 'yes' else 'no' fi`` returns ``'yes'`` if series is either `foo` or `1632`, otherwise ``'no'``.
  * ``program: if 11 > 2 then 'yes' else 'no' fi`` returns ``'no'`` because the ``>`` operator does a lexical comparison.
  * ``program: if 11 ># 2 then 'yes' else 'no' fi`` returns ``'yes'`` because the ``>#`` operator does a numeric comparison.

**Functions in General Program Mode**

See :ref:`template_functions_reference` for the list of functions built into the template language.

Notes:

* As opposed to :ref:`Single Function Mode <single_mode>`, in General Program Mode you must specify the first parameter ``value``.
* All parameters are expression_lists (see the grammar above).

.. _template_mode:

More complex programs in template expressions - Template Program Mode
----------------------------------------------------------------------

`Template Program Mode` (`TPM`) is a blend of :ref:`General Program Mode <general_mode>` and
:ref:`Single Function Mode <single_mode>`. `TPM` differs from Single Function Mode in that it permits writing template expressions that refer to other metadata fields, use nested functions, modify variables, and do arithmetic. It differs from `General Program Mode` in that the template is contained between ``{`` and ``}`` characters and doesn't begin with the word ``program:``. The program portion of the template is a General Program Mode expression list.

Example: assume you want a template to show the series for a book if it has one, otherwise show
the value of a custom field #genre. You cannot do this in the :ref:`Single Function Mode <single_mode>` because you cannot make reference to another metadata field within a template expression. In `TPM` you can, as the following expression demonstrates::

    {series_index:0>7.1f:'ifempty($, -5)'}

The example shows several things:

* `TPM` is used if the expression begins with ``:'`` and ends with ``'}``. Anything else is assumed to be in :ref:`Single Function Mode <single_mode>`.

  If the template contains a prefix and suffix, the expression ends with ``'|`` where the ``|`` is the delimiter for the prefix. Example::

    {series_index:0>7.1f:'ifempty($, -5)'|prefix | suffix}

* Functions must be given all their arguments. For example, the standard built-in functions must be given the initial parameter ``value``.
* The variable ``$`` is usable as the ``value`` argument and stands for the value of the field named in the template, ``series_index`` in this case.
* white space is ignored and can be used anywhere within the expression.
* constant strings are enclosed in matching quotes, either ``'`` or ``"``.

In `TPM`, using ``{`` and ``}`` characters in string literals can lead to errors or unexpected results because they confuse the template processor. It tries to treat them as template expression boundaries, not characters. In some but not all cases you can replace a ``{`` with ``[[`` and a ``}`` with `]]`. Generally, if your program contains ``{`` and ``}`` characters then you should use `General Program Mode`.

.. _python_mode:

Python Template Mode
-----------------------------------

Python Template Mode (PTM) lets you write templates using native Python and the `calibre API <https://manual.calibre-ebook.com/develop.html#api-documentation-for-various-parts-of-calibre>`_. The database API will be of most use; further discussion is beyond the scope of this manual. PTM templates are faster and can do more complicated operations but you must know how to write code in Python using the calibre API.

A PTM template begins with:

.. code-block:: python

 python:
 def evaluate(book, context):
     # book is a calibre metadata object
     # context is an instance of calibre.utils.formatter.PythonTemplateContext,
     # which currently contains the following attributes:
     # db: a calibre legacy database object.
     # globals: the template global variable dictionary.
     # arguments: is a list of arguments if the template is called by a GPM template, otherwise None.
     # funcs: used to call Built-in/User functions and Stored GPM/Python templates.
     # Example: context.funcs.list_re_group()

     # your Python code goes here
     return 'a string'

You can add the above text to your template using the context menu, usually accessed with a right click. The comments are not significant and can be removed. You must use python indenting.

The context object supports ``str(context)`` that returns a string of the context's contents, and ``context.attributes`` that returns a list of the attribute names in the context.

The ``context.funcs`` attribute allows calling Built-in and User template functions, and Stored GPM/Python templates, so that you can execute them directly in your code. The functions are retrieved using their names. If the name conflicts with a Python keyword, add an underscore to the end of the name. Examples:

.. code-block:: python

 context.funcs.list_re_group()
 context.funcs.assert_()

Here is an example of a PTM template that produces a list of all the authors for a series. The list is stored in a `Column built from other columns, behaves like tags`. It shows in :guilabel:`Book details` and has the :guilabel:`on separate lines` checked (in :guilabel:`Preferences->Look & feel->Book details`). That option requires the list to be comma-separated. To satisfy that requirement the template converts commas in author names to semicolons then builds a comma-separated list of authors. The authors are then sorted, which is why the template uses author_sort.

.. code-block:: python

    python:
    def evaluate(book, context):
        if book.series is None:
            return ''
        db = context.db.new_api
        ans = set()
        # Get the list of books in the series
        ids = db.search(f'series:"={book.series}"', '')
        if ids:
            # Get all the author_sort values for the books in the series
            author_sorts = (v for v in db.all_field_for('author_sort', ids).values())
            # Add the names to the result set, removing duplicates
            for aus in author_sorts:
                ans.update(v.strip() for v in aus.split('&'))
        # Make a sorted comma-separated string from the result set
        return ', '.join(v.replace(',', ';') for v in sorted(ans))

The output in :guilabel:`Book details` looks like this:

.. image:: images/python_template_example.png
    :align: center
    :alt: E-book conversion dialog
    :class: half-width-img

Stored templates
----------------------------------------

Both :ref:`General Program Mode <general_mode>` and :ref:`Python Template Mode <python_mode>` support saving templates and calling those templates from another template, much like calling stored functions. You save templates using :guilabel:`Preferences->Advanced->Template functions`. More information is provided in that dialog. You call a template the same way you call a function, passing positional arguments if desired. An argument can be any expression. Examples of calling a template, assuming the stored template is named ``foo``:

* ``foo()`` -- call the template passing no arguments.
* ``foo(a, b)`` call the template passing the values of the two variables ``a`` and ``b``.
* ``foo(if field('series') then field('series_index') else 0 fi)`` -- if the book has a ``series`` then pass the ``series_index``, otherwise pass the value ``0``.

In GPM you retrieve the arguments passed in the call to the stored template using the ``arguments`` function. It both declares and initializes local variables, effectively parameters. The variables are positional; they get the value of the parameter given in the call in the same position. If the corresponding parameter is not provided in the call then ``arguments`` assigns that variable the provided default value. If there is no default value then the variable is set to the empty string. For example, the following ``arguments`` function declares 2 variables, ``key``, ``alternate``::

  arguments(key, alternate='series')

Examples, again assuming the stored template is named ``foo``:

* ``foo('#myseries')`` -- argument ``key`` is assigned the value ``'myseries'`` and the argument ``alternate`` is assigned the default value ``'series'``.
* ``foo('series', '#genre')`` the variable ``key`` is assigned the value ``'series'`` and the variable ``alternate`` is assigned the value ``'#genre'``.
* ``foo()`` -- the variable ``key`` is assigned the empty string and the variable ``alternate`` is assigned the value ``'series'``.

In PTM the arguments are passed in the ``arguments`` parameter, which is a list of strings. There isn't any way to specify default values. You must check the length of the ``arguments`` list to be sure that the number of arguments is what you expect.

An easy way to test stored templates is using the ``Template tester`` dialog. For ease of access give it a keyboard shortcut in :guilabel:`Preferences->Advanced->Keyboard shortcuts->Template tester`. Giving the ``Stored templates`` dialog a shortcut will help switching more rapidly between the tester and editing the stored template's source code.

Providing additional information to templates
----------------------------------------------

A developer can choose to pass additional information to the template processor, such as application-specific book metadata or information about what the processor is being asked to do. A template can access this information and use it during the evaluation.

**Developer: how to pass additional information**

The additional information is a Python dictionary containing pairs ``variable_name: variable_value`` where the values must be strings. The template can access the dictionary, creating template local variables named ``variable_name`` containing the value ``variable_value``. The user cannot change the name so it is best to use names that won't collide with other template local variables, for example by prefixing the name with an underscore.

This dictionary is passed to the template processor (the ``formatter``) using the named parameter ``global_vars=your_dict``. The full method signature is::

    def safe_format(self, fmt, kwargs, error_value, book,
                    column_name=None, template_cache=None,
                    strip_results=True, template_functions=None,
                    global_vars={})


**Template writer: how to access the additional information**

You access the additional information (the ``globals`` dictionary) in a template using the template function::

  globals(id[=expression] [, id[=expression]]*)

where ``id`` is any legal variable name. This function checks whether the additional information provided by the developer contains the name. If it does then the function assigns the provided value to a template local variable with that name. If the name is not in the additional information and if an ``expression`` is provided, the ``expression`` is evaluated and the result is assigned to the local variable. If neither a value nor an expression is provided, the function assigns the empty string (``''``) to the local variable.

A template can set a value in the ``globals`` dictionary using the template function::

  set_globals(id[=expression] [, id[=expression]]*)

This function sets the ``globals`` dictionary key:value pair ``id:value`` where ``value`` is the value of the template local variable ``id``. If that local variable doesn't exist then ``value`` is set to the result of evaluating ``expression``.

Notes on the difference between modes
-----------------------------------------

The three program modes, :ref:`Single Function Mode <single_mode>` (SFM), :ref:`Template Program Mode <template_mode>` (`TPM`), and :ref:`General Program Mode <general_mode>` (`GPM`), work differently. SFM is intended to be 'simple' so it hides a lot of programming language bits.

Differences:

* In SFM the value of the column is always passed as an 'invisible' first argument to a function included in the template.
* SFM doesn't support the difference between variables and strings; all values are strings.
* The following SFM template returns either the series name or the string "no series"::

    {series:ifempty(no series)}

  The equivalent template in `TPM` is ::

    {series:'ifempty($, 'no series')'}

  The equivalent template in `GPM` is::

    program: ifempty(field('series'), 'no series')

  The first argument to ``ifempty`` is the value of the field ``series``. The second argument is the string ``no series``. In SFM the first argument, the value of the field, is automatically passed (the invisible argument).
* Several template functions, for example ``booksize()`` and ``current_library_name()``, take no arguments. Because of the 'invisible argument' you cannot use these functions in SFM.
* Nested functions, where a function calls another function to compute an argument, cannot be used in SFM. For example this template, intended to return the first 5 characters of the series value uppercased, won't work in SFM::

    {series:uppercase(substr(0,5))}

* `TPM` and `GPM` support nested functions. The above template in `TPM` would be::

    {series:'uppercase(substr($, 0,5))'}

  In `GPM` it would be::

    program: uppercase(substr(field('series'), 0,5))

* As noted in the above :ref:`Template Program Mode <template_mode>` section, using ``{`` and ``}`` characters in `TPM` string literals can lead to errors or unexpected results because they confuse the template processor. It tries to treat them as template boundaries, not characters. In some but not all cases you can replace a ``{`` with ``[[`` and a ``}`` with `]]`. Generally, if your program contains ``{`` and ``}`` characters then you should use `General Program Mode`.


User-defined Python template functions
------------------------------------------

You can add your own Python functions to the template processor. Such functions can be used in any of the three template programming modes. The functions are added by going to :guilabel:`Preferences -> Advanced -> Template functions`. Instructions are shown in that dialog. Note that you can use `Python Templates` for a similar purpose. As calling user-defined functions is faster than calling a Python template, user-defined functions might be more efficient depending on the complexity of what the function or template does.

Special notes for save/send templates
---------------------------------------

Special processing is applied when a template is used in a `save to disk` or `send to device` template. The values of the fields are cleaned, replacing characters that are special to file systems with underscores, including slashes. This means that field text cannot be used to create folders. However, slashes are not changed in prefix or suffix strings, so slashes in these strings will cause folders to be created. Because of this, you can create variable-depth folder structure.

For example, assume we want the folder structure `series/series_index - title`, with the caveat that if series does not exist, then the title should be in the top folder. The template to do this is::

    {series:||/}{series_index:|| - }{title}

The slash and the hyphen appear only if series is not empty.

The lookup function lets us do even fancier processing. For example, assume that if a book has a series, then we want the folder structure `series/series index - title.fmt`. If the book does not have a series then we want the folder structure `genre/author_sort/title.fmt`. If the book has no genre then we want to use 'Unknown'. We want two completely different paths, depending on the value of series.

To accomplish this, we:

1. Create a composite field (give it lookup name #aa) containing ``{series}/{series_index} - {title}``. If the series is not empty, then this template will produce `series/series_index - title`.
2. Create a composite field (give it lookup name #bb) containing ``{#genre:ifempty(Unknown)}/{author_sort}/{title}``. This template produces `genre/author_sort/title`, where an empty genre is replaced with `Unknown`.
3. Set the save template to ``{series:lookup(.,#aa,#bb)}``. This template chooses composite field ``#aa`` if series is not empty and composite field ``#bb`` if series is empty. We therefore have two completely different save paths, depending on whether or not `series` is empty.

Tips
-----

* Use the Template Tester to test templates. Add the tester to the context menu for books in the library and/or give it a keyboard shortcut.
* Templates can use other templates by referencing composite columns built with the desired template. Alternatively, you can use Stored Templates.
* In a plugboard, you can set a field to empty (or whatever is equivalent to empty) by using the special template ``{}``. This template will always evaluate to an empty string.
* The technique described above to show numbers even if they have a zero value works with the standard field series_index.

.. _template_functions_reference:

Template function reference
---------------------------

.. toctree::
    :maxdepth: 3

    generated/en/template_ref

.. toctree::
  :hidden:

  generated/en/template_ref
