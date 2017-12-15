Quick reference for regexp syntax
=================================================

This checklist summarizes the most commonly used/hard to remember parts of the
regexp engine available in the calibre edit and conversion search/replace
features. Note that this engine is more powerful than the basic regexp engine
used throughout the rest of calibre.

.. contents:: Contents
  :depth: 2
  :local:


Character classes
------------------

Character classes are useful to represent different groups of characters,
succinctly.

Examples:

+-----------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **Representation**    | **Class**                                                                                                                                                                                              |
|                       |                                                                                                                                                                                                        |
+-----------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``[a-z]``             | Lowercase letters. Does not include characters with accent mark and ligatures                                                                                                                          |
|                       |                                                                                                                                                                                                        |
+-----------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``[a-z0-9]``          | Lowercase letters from a to z or numbers from 0 to 9                                                                                                                                                   |
|                       |                                                                                                                                                                                                        |
+-----------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``[A-Za-z-]``         | Uppercase or lowercase letters, or a dash. To include the dash in a class, you must put it at the beginning or at the end so as not to confuse it with the hyphen that specifies a range of characters |
|                       |                                                                                                                                                                                                        |
+-----------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``[^0-9]``            | Any character except a digit. The caret (^) placed at the beginning of the class excludes the characters of the class (complemented class)                                                             |
|                       |                                                                                                                                                                                                        |
+-----------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``[[a-z]--[aeiouy]]`` | The lowercase consonants. A class can be included in a class. The characters -- exclude what follows them                                                                                              |
|                       |                                                                                                                                                                                                        |
+-----------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``[\w--[\d_]]``       | All letters (including foreign accented characters). Abbreviated classes can be used inside a class                                                                                                    |
|                       |                                                                                                                                                                                                        |
+-----------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+


Example::

    <[^<>]+> to select an HTML tag

Shorthand character classes
---------------------------

+---------------------+----------------------------------------------------------------------------------------------------------------------------------------------+
| **Representation**  | **Class**                                                                                                                                    |
|                     |                                                                                                                                              |
+---------------------+----------------------------------------------------------------------------------------------------------------------------------------------+
| ``\d``              | A digit (same as ``[0-9]``)                                                                                                                  |
|                     |                                                                                                                                              |
+---------------------+----------------------------------------------------------------------------------------------------------------------------------------------+
| ``\D``              | Any non-numeric character (same as ``[^0-9]``)                                                                                               |
|                     |                                                                                                                                              |
+---------------------+----------------------------------------------------------------------------------------------------------------------------------------------+
| ``\w``              | An alphanumeric character plus the underscore (``[a-zA-Z0-9_]``) including characters with accent mark and ligatures                         |
|                     |                                                                                                                                              |
+---------------------+----------------------------------------------------------------------------------------------------------------------------------------------+
| ``\W``              | Any “non-word” character                                                                                                                     |
|                     |                                                                                                                                              |
+---------------------+----------------------------------------------------------------------------------------------------------------------------------------------+
| ``\s``              | Space, non-breaking space, tab, return line                                                                                                  |
|                     |                                                                                                                                              |
+---------------------+----------------------------------------------------------------------------------------------------------------------------------------------+
| ``\S``              | Any “non-whitespace” character                                                                                                               |
|                     |                                                                                                                                              |
+---------------------+----------------------------------------------------------------------------------------------------------------------------------------------+
| ``.``               | Any character except newline. Use the “dot all” checkbox or the ``(?s)`` regexp modifier to include the newline character.                   |
|                     |                                                                                                                                              |
+---------------------+----------------------------------------------------------------------------------------------------------------------------------------------+

The quantifiers
---------------

+----------------+---------------------------------------------------------------------------+
| **Quantifier** | **Number of occurrences of the expression preceding the quantifier**      |
|                |                                                                           |
+----------------+---------------------------------------------------------------------------+
| ``?``          | 0 or 1 occurrence of the expression. Same as ``{0,1}``                    |
|                |                                                                           |
+----------------+---------------------------------------------------------------------------+
| ``+``          | 1 or more occurrences of the expression. Same as ``{1,}``                 |
|                |                                                                           |
+----------------+---------------------------------------------------------------------------+
| ``*``          | 0, 1 or more occurrences of the expression. Same as ``{0,}``              |
|                |                                                                           |
+----------------+---------------------------------------------------------------------------+
| ``{n}``        | Exactly n occurrences of the expression                                   |
|                |                                                                           |
+----------------+---------------------------------------------------------------------------+
| ``{min,max}``  | Number of occurrences between the minimum and maximum values included     |
|                |                                                                           |
+----------------+---------------------------------------------------------------------------+
| ``{min,}``     | Number of occurrences between the minimum value included and the infinite |
|                |                                                                           |
+----------------+---------------------------------------------------------------------------+
| ``{,max}``     | Number of occurrences between 0 and the maximum value included            |
|                |                                                                           |
+----------------+---------------------------------------------------------------------------+



Greed
-----

By default, with quantifiers, the regular expression engine is greedy: it
extends the selection as much as possible. This often causes surprises, at
first. ``?`` follows a quantifier to make it lazy.
Avoid putting two in the same expression, the result can be unpredictable.

Beware of nesting quantifiers, for example, the pattern ``(a*)*``, as it
exponentially increases processing time.

Alternation
-----------

The ``|`` character in a regular expression is a logical ``OR``. It means
that either the preceding or the following expression can match.

Exclusion
---------

Method 1

``pattern_to_exclude(*SKIP)(*FAIL)|pattern_to_select``

Example:

``"Blabla"(*SKIP)(*FAIL)|Blabla``

selects Blabla, in the strings Blabla or "Blabla or Blabla", but not in "Blabla".

Method 2

``pattern_to_exclude\K|(pattern_to_select)``

``"Blabla"\K|(Blabla)``

selects Blabla, in the strings Blabla or "Blabla or Blabla", but not in "Blabla".

Anchors
-------

An anchor is a way to match a logical location in a string, rather than a
character. The most useful anchors for text processing are:

  ``\b``
     Designates a word boundary, i.e. a transition from space to non-space
     character. For example, you can use ``\bsurd`` to match ``the surd`` but
     not ``absurd``.

  ``^``
     Matches the start of the string or in multi-line mode the start of a line.

  ``$``
     Matches the end of the string or, in multi-line mode the end of a line.

  ``\K``
     Resets the start position of the selection to its position in the pattern.
     Some regexp engines (but not calibre) do not allow lookbehind of variable
     length, especially with quantifiers. When you can use ``\K`` with these
     engines, it also allows you to get rid of this limit by writing the
     equivalent of a positive lookbehind of variable length.

Groups
------

    ``(expression)``        
        Capturing group, which stores the selection and can be recalled later
        in the *search* or *replace* patterns with ``\n``, where ``n`` is the
        sequence number of the capturing group (starting at 1 in reading order)  

    ``(?:expression)``        
        Group that does not capture the selection

    ``(?>expression)``      
        Atomic Group: As soon as the expression is satisfied, the regexp engine
        passes, and if the rest of the pattern fails, it will not backtrack to
        try other combinations with the expression. Atomic groups do not
        capture. 

    ``(?|expression)``      
        Branch reset group: the branches of the alternations included in the
        expression share the same group numbers
        
    ``(?<name>expression)`` 
        Group named “name”. The selection can be recalled later in the *search*
        pattern by ``(?P=name)`` and in the *replace* by ``\g<name>``. Two
        different groups can use the same name.


Lookarounds
-----------

+----------------+---------------------------------------------------------+
| **Lookaround** | **Meaning**                                             |
|                |                                                         |
+----------------+---------------------------------------------------------+
| ``?=``         | Positive lookahead (to be placed after the selection)   |
|                |                                                         |
+----------------+---------------------------------------------------------+
| ``?!``         | Negative lookahead (to be placed after the selection)   |
|                |                                                         |
+----------------+---------------------------------------------------------+
| ``?<=``        | Positive lookbehind (to be placed before the selection) |
|                |                                                         |
+----------------+---------------------------------------------------------+
| ``?<!``        | Negative lookbehind (to be placed before the selection) |
|                |                                                         |
+----------------+---------------------------------------------------------+

Lookaheads and lookbehinds do not consume characters, they are zero length and
do not capture. They are atomic groups: as soon as the assertion is satisfied,
the regexp engine passes, and if the rest of the pattern fails, it will not
backtrack inside the lookaround to try other combinations. 

When looking for multiple matches in a string, at the starting position of each
match attempt, a lookbehind can inspect the characters before the current
position. Therefore, on the string 123, the pattern ``(?<=\d)\d`` (a digit preceded
by a digit) should, in theory, select 2 and 3. On the other hand, ``\d\K\d`` can
only select 2, because the starting position after the first selection is
immediately before 3, and there are not enough digits for a second match.
Similarly, ``\d(\d)`` only captures 2. In calibre's regexp engine practice, the
positive lookbehind behaves in the same way, and selects only 2, contrary to
theory. 

Groups can be placed inside lookarounds, but capture is rarely useful.
Nevertheless, if it is useful, it will be necessary to be very careful in the
use of a quantifier in a lookbehind: the greed associated with the absence of
backtracking can give a surprising capture. For this reason, use ``\K`` rather than
a positive lookbehind when you have a quantifier (or worse, several) in a
capturing group of the positive lookbehind.

Example of negative lookahead:

``(?![^<>{}]*[>}])``

Placed at the end of the pattern prevents to select within a tag or a style embedded in the file.

Whenever possible, it is always better to "anchor" the lookarounds, to reduce
the number of steps necessary to obtain the result.

Recursion
---------

+--------------------+-----------------------------------------------------------------------------+
| **Representation** | **Meaning**                                                                 |
|                    |                                                                             |
+--------------------+-----------------------------------------------------------------------------+
| ``(?R)``           | Recursion of the entire pattern                                             |
|                    |                                                                             |
+--------------------+-----------------------------------------------------------------------------+
| ``(?1)``           | Recursion of the only pattern of the numbered capturing group, here group 1 |
|                    |                                                                             |
+--------------------+-----------------------------------------------------------------------------+

Recursion is calling oneself. This is useful for balanced queries, such as
quoted strings, which can contain embedded quoted strings. Thus, if during the
processing of a string between double quotation marks, we encounter the
beginning of a new string between double quotation marks, well we know how to
do, and we call ourselves. Then we have a pattern like::

    start-pattern(?>atomic sub-pattern|(?R))*end-pattern

To select a string between double quotation marks without stopping on an embedded string::

    “((?>[^“”]+|(?R))*[^“”]+)”

This template can also be used to modify pairs of tags that can be
embedded, such as ``<div>`` tags. 


Special characters
------------------

+--------------------+-------------------+
| **Representation** | **Character**     |
|                    |                   |
+--------------------+-------------------+
| ``\t``             | tabulation        |
|                    |                   |
+--------------------+-------------------+
| ``\n``             | line break        |
|                    |                   |
+--------------------+-------------------+
| ``\x20``           | (breakable) space |
|                    |                   |
+--------------------+-------------------+
| ``\xa0``           | no-break space    |
|                    |                   |
+--------------------+-------------------+

Meta-characters
---------------

Meta-characters are those that have a special meaning for the regexp engine. Of
these, twelve must be preceded by an escape character, the backslash (``\``), to
lose their special meaning and become a regular character again::

    ^ . [ ] $ ( ) * + ? | \

Seven other meta-characters do not need to be preceded by a backslash (but can
be without any other consequence)::

    { } ! < > = :


Special characters lose their status if they are used inside a class (between
brackets ``[]``). The closing bracket and the dash have a special status in a
class. Outside the class, the dash is a simple literal, the closing bracket
remains a meta-character.

The slash (/) and the number sign (or hash character) (#) are not
meta-characters, they don’t need to be escaped.

In some tools, like regex101.com with the Python engine, double quotes have the
special status of separator, and must be escaped, or the options changed. This
is not the case in the editor of calibre.

Modes
-----

    ``(?s)``
        Causes the dot (``.``) to match newline characters as well

    ``(?m)``
        Makes the ``^`` and ``$`` anchors match the start and end of lines
        instead of the start and end of the entire string.

