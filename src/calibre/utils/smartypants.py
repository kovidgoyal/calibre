#!/usr/bin/python2
# vim:fileencoding=utf-8

__author__ = "Chad Miller <smartypantspy@chad.org>, Kovid Goyal <kovid at kovidgoyal.net>"
__description__ = "Smart-quotes, smart-ellipses, and smart-dashes for weblog entries in pyblosxom"

r"""
==============
smartypants.py
==============

----------------------------
SmartyPants ported to Python
----------------------------

Ported by `Chad Miller`_
Copyright (c) 2004, 2007 Chad Miller

original `SmartyPants`_ by `John Gruber`_
Copyright (c) 2003 John Gruber


Synopsis
========

A smart-quotes plugin for Pyblosxom_.

The priginal "SmartyPants" is a free web publishing plug-in for Movable Type,
Blosxom, and BBEdit that easily translates plain ASCII punctuation characters
into "smart" typographic punctuation HTML entities.

This software, *smartypants.py*, endeavours to be a functional port of
SmartyPants to Python, for use with Pyblosxom_.


Description
===========

SmartyPants can perform the following transformations:

- Straight quotes ( " and ' ) into "curly" quote HTML entities
- Backticks-style quotes (\`\`like this'') into "curly" quote HTML entities
- Dashes (``--`` and ``---``) into en- and em-dash entities
- Three consecutive dots (``...`` or ``. . .``) into an ellipsis entity

This means you can write, edit, and save your posts using plain old
ASCII straight quotes, plain dashes, and plain dots, but your published
posts (and final HTML output) will appear with smart quotes, em-dashes,
and proper ellipses.

SmartyPants does not modify characters within ``<pre>``, ``<code>``, ``<kbd>``,
``<math>`` or ``<script>`` tag blocks. Typically, these tags are used to
display text where smart quotes and other "smart punctuation" would not be
appropriate, such as source code or example markup.


Backslash Escapes
=================

If you need to use literal straight quotes (or plain hyphens and
periods), SmartyPants accepts the following backslash escape sequences
to force non-smart punctuation. It does so by transforming the escape
sequence into a decimal-encoded HTML entity:

(FIXME:  table here.)

.. comment    It sucks that there's a disconnect between the visual layout and table markup when special characters are involved.
.. comment ======  =====  =========
.. comment Escape  Value  Character
.. comment ======  =====  =========
.. comment \\\\\\\\    &#92;  \\\\
.. comment \\\\"     &#34;  "
.. comment \\\\'     &#39;  '
.. comment \\\\.     &#46;  .
.. comment \\\\-     &#45;  \-
.. comment \\\\`     &#96;  \`
.. comment ======  =====  =========

This is useful, for example, when you want to use straight quotes as
foot and inch marks: 6'2" tall; a 17" iMac.

Options
=======

For Pyblosxom users, the ``smartypants_attributes`` attribute is where you
specify configuration options.

Numeric values are the easiest way to configure SmartyPants' behavior:

"0"
    Suppress all transformations. (Do nothing.)
"1"
    Performs default SmartyPants transformations: quotes (including
    \`\`backticks'' -style), em-dashes, and ellipses. "``--``" (dash dash)
    is used to signify an em-dash; there is no support for en-dashes.

"2"
    Same as smarty_pants="1", except that it uses the old-school typewriter
    shorthand for dashes:  "``--``" (dash dash) for en-dashes, "``---``"
    (dash dash dash)
    for em-dashes.

"3"
    Same as smarty_pants="2", but inverts the shorthand for dashes:
    "``--``" (dash dash) for em-dashes, and "``---``" (dash dash dash) for
    en-dashes.

"-1"
    Stupefy mode. Reverses the SmartyPants transformation process, turning
    the HTML entities produced by SmartyPants into their ASCII equivalents.
    E.g.  "&#8220;" is turned into a simple double-quote ("), "&#8212;" is
    turned into two dashes, etc.


The following single-character attribute values can be combined to toggle
individual transformations from within the smarty_pants attribute. For
example, to educate normal quotes and em-dashes, but not ellipses or
\`\`backticks'' -style quotes:

``py['smartypants_attributes'] = "1"``

"q"
    Educates normal quote characters: (") and (').

"b"
    Educates \`\`backticks'' -style double quotes.

"B"
    Educates \`\`backticks'' -style double quotes and \`single' quotes.

"d"
    Educates em-dashes.

"D"
    Educates em-dashes and en-dashes, using old-school typewriter shorthand:
    (dash dash) for en-dashes, (dash dash dash) for em-dashes.

"i"
    Educates em-dashes and en-dashes, using inverted old-school typewriter
    shorthand: (dash dash) for em-dashes, (dash dash dash) for en-dashes.

"e"
    Educates ellipses.

"w"
    Translates any instance of ``&quot;`` into a normal double-quote character.
    This should be of no interest to most people, but of particular interest
    to anyone who writes their posts using Dreamweaver, as Dreamweaver
    inexplicably uses this entity to represent a literal double-quote
    character. SmartyPants only educates normal quotes, not entities (because
    ordinarily, entities are used for the explicit purpose of representing the
    specific character they represent). The "w" option must be used in
    conjunction with one (or both) of the other quote options ("q" or "b").
    Thus, if you wish to apply all SmartyPants transformations (quotes, en-
    and em-dashes, and ellipses) and also translate ``&quot;`` entities into
    regular quotes so SmartyPants can educate them, you should pass the
    following to the smarty_pants attribute:

The ``smartypants_forbidden_flavours`` list contains pyblosxom flavours for
which no Smarty Pants rendering will occur.


Caveats
=======

Why You Might Not Want to Use Smart Quotes in Your Weblog
---------------------------------------------------------

For one thing, you might not care.

Most normal, mentally stable individuals do not take notice of proper
typographic punctuation. Many design and typography nerds, however, break
out in a nasty rash when they encounter, say, a restaurant sign that uses
a straight apostrophe to spell "Joe's".

If you're the sort of person who just doesn't care, you might well want to
continue not caring. Using straight quotes -- and sticking to the 7-bit
ASCII character set in general -- is certainly a simpler way to live.

Even if you I *do* care about accurate typography, you still might want to
think twice before educating the quote characters in your weblog. One side
effect of publishing curly quote HTML entities is that it makes your
weblog a bit harder for others to quote from using copy-and-paste. What
happens is that when someone copies text from your blog, the copied text
contains the 8-bit curly quote characters (as well as the 8-bit characters
for em-dashes and ellipses, if you use these options). These characters
are not standard across different text encoding methods, which is why they
need to be encoded as HTML entities.

People copying text from your weblog, however, may not notice that you're
using curly quotes, and they'll go ahead and paste the unencoded 8-bit
characters copied from their browser into an email message or their own
weblog. When pasted as raw "smart quotes", these characters are likely to
get mangled beyond recognition.

That said, my own opinion is that any decent text editor or email client
makes it easy to stupefy smart quote characters into their 7-bit
equivalents, and I don't consider it my problem if you're using an
indecent text editor or email client.


Algorithmic Shortcomings
------------------------

One situation in which quotes will get curled the wrong way is when
apostrophes are used at the start of leading contractions. For example:

``'Twas the night before Christmas.``

In the case above, SmartyPants will turn the apostrophe into an opening
single-quote, when in fact it should be a closing one. I don't think
this problem can be solved in the general case -- every word processor
I've tried gets this wrong as well. In such cases, it's best to use the
proper HTML entity for closing single-quotes (``&#8217;``) by hand.


Bugs
====

To file bug reports or feature requests (other than topics listed in the
Caveats section above) please send email to: mailto:smartypantspy@chad.org

If the bug involves quotes being curled the wrong way, please send example
text to illustrate.

To Do list
----------

- Provide a function for use within templates to quote anything at all.


Version History
===============

1.5_1.6: Fri, 27 Jul 2007 07:06:40 -0400
    - Fixed bug where blocks of precious unalterable text was instead
      interpreted.  Thanks to Le Roux and Dirk van Oosterbosch.

1.5_1.5: Sat, 13 Aug 2005 15:50:24 -0400
    - Fix bogus magical quotation when there is no hint that the
      user wants it, e.g., in "21st century".  Thanks to Nathan Hamblen.
    - Be smarter about quotes before terminating numbers in an en-dash'ed
      range.

1.5_1.4: Thu, 10 Feb 2005 20:24:36 -0500
    - Fix a date-processing bug, as reported by jacob childress.
    - Begin a test-suite for ensuring correct output.
    - Removed import of "string", since I didn't really need it.
      (This was my first every Python program.  Sue me!)

1.5_1.3: Wed, 15 Sep 2004 18:25:58 -0400
    - Abort processing if the flavour is in forbidden-list.  Default of
      [ "rss" ]   (Idea of Wolfgang SCHNERRING.)
    - Remove stray virgules from en-dashes.  Patch by Wolfgang SCHNERRING.

1.5_1.2: Mon, 24 May 2004 08:14:54 -0400
    - Some single quotes weren't replaced properly.  Diff-tesuji played
      by Benjamin GEIGER.

1.5_1.1: Sun, 14 Mar 2004 14:38:28 -0500
    - Support upcoming pyblosxom 0.9 plugin verification feature.

1.5_1.0: Tue, 09 Mar 2004 08:08:35 -0500
    - Initial release

Version Information
-------------------

Version numbers will track the SmartyPants_ version numbers, with the addition
of an underscore and the smartypants.py version on the end.

New versions will be available at `http://wiki.chad.org/SmartyPantsPy`_

.. _http://wiki.chad.org/SmartyPantsPy: http://wiki.chad.org/SmartyPantsPy

Authors
=======

`John Gruber`_ did all of the hard work of writing this software in Perl for
`Movable Type`_ and almost all of this useful documentation.  `Chad Miller`_
ported it to Python to use with Pyblosxom_.


Additional Credits
==================

Portions of the SmartyPants original work are based on Brad Choate's nifty
MTRegex plug-in.  `Brad Choate`_ also contributed a few bits of source code to
this plug-in.  Brad Choate is a fine hacker indeed.

`Jeremy Hedley`_ and `Charles Wiltgen`_ deserve mention for exemplary beta
testing of the original SmartyPants.

`Rael Dornfest`_ ported SmartyPants to Blosxom.

.. _Brad Choate: http://bradchoate.com/
.. _Jeremy Hedley: http://antipixel.com/
.. _Charles Wiltgen: http://playbacktime.com/
.. _Rael Dornfest: http://raelity.org/


Copyright and License
=====================

SmartyPants_ license::

    Copyright (c) 2003 John Gruber
    (https://daringfireball.net/)
    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are
    met:

    *   Redistributions of source code must retain the above copyright
        notice, this list of conditions and the following disclaimer.

    *   Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in
        the documentation and/or other materials provided with the
        distribution.

    *   Neither the name "SmartyPants" nor the names of its contributors
        may be used to endorse or promote products derived from this
        software without specific prior written permission.

    This software is provided by the copyright holders and contributors "as
    is" and any express or implied warranties, including, but not limited
    to, the implied warranties of merchantability and fitness for a
    particular purpose are disclaimed. In no event shall the copyright
    owner or contributors be liable for any direct, indirect, incidental,
    special, exemplary, or consequential damages (including, but not
    limited to, procurement of substitute goods or services; loss of use,
    data, or profits; or business interruption) however caused and on any
    theory of liability, whether in contract, strict liability, or tort
    (including negligence or otherwise) arising in any way out of the use
    of this software, even if advised of the possibility of such damage.


smartypants.py license::

    smartypants.py is a derivative work of SmartyPants.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are
    met:

    *   Redistributions of source code must retain the above copyright
        notice, this list of conditions and the following disclaimer.

    *   Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in
        the documentation and/or other materials provided with the
        distribution.

    This software is provided by the copyright holders and contributors "as
    is" and any express or implied warranties, including, but not limited
    to, the implied warranties of merchantability and fitness for a
    particular purpose are disclaimed. In no event shall the copyright
    owner or contributors be liable for any direct, indirect, incidental,
    special, exemplary, or consequential damages (including, but not
    limited to, procurement of substitute goods or services; loss of use,
    data, or profits; or business interruption) however caused and on any
    theory of liability, whether in contract, strict liability, or tort
    (including negligence or otherwise) arising in any way out of the use
    of this software, even if advised of the possibility of such damage.



.. _John Gruber: https://daringfireball.net/
.. _Chad Miller: http://web.chad.org/

.. _Pyblosxom: http://roughingit.subtlehints.net/pyblosxom
.. _SmartyPants: https://daringfireball.net/projects/smartypants/
.. _Movable Type: http://www.movabletype.org/

"""

import re

# style added by Kovid
tags_to_skip_regex = re.compile(r"<(/)?(style|pre|code|kbd|script|math)[^>]*>", re.I)
self_closing_regex = re.compile(r'/\s*>$')


# interal functions below here

def parse_attr(attr):
    do_dashes = do_backticks = do_quotes = do_ellipses = do_stupefy = 0

    if attr == "1":
        do_quotes    = 1
        do_backticks = 1
        do_dashes    = 1
        do_ellipses  = 1
    elif attr == "2":
        # Do everything, turn all options on, use old school dash shorthand.
        do_quotes    = 1
        do_backticks = 1
        do_dashes    = 2
        do_ellipses  = 1
    elif attr == "3":
        # Do everything, turn all options on, use inverted old school dash shorthand.
        do_quotes    = 1
        do_backticks = 1
        do_dashes    = 3
        do_ellipses  = 1
    elif attr == "-1":
        # Special "stupefy" mode.
        do_stupefy   = 1
    else:
        for c in attr:
            if c == "q":
                do_quotes = 1
            elif c == "b":
                do_backticks = 1
            elif c == "B":
                do_backticks = 2
            elif c == "d":
                do_dashes = 1
            elif c == "D":
                do_dashes = 2
            elif c == "i":
                do_dashes = 3
            elif c == "e":
                do_ellipses = 1
            else:
                pass
                # ignore unknown option
    return do_dashes, do_backticks, do_quotes, do_ellipses, do_stupefy


def smartyPants(text, attr='1'):
    # Parse attributes:
    # 0 : do nothing
    # 1 : set all
    # 2 : set all, using old school en- and em- dash shortcuts
    # 3 : set all, using inverted old school en and em- dash shortcuts
    #
    # q : quotes
    # b : backtick quotes (``double'' only)
    # B : backtick quotes (``double'' and `single')
    # d : dashes
    # D : old school dashes
    # i : inverted old school dashes
    # e : ellipses

    if attr == "0":
        # Do nothing.
        return text

    do_dashes, do_backticks, do_quotes, do_ellipses, do_stupefy = parse_attr(attr)
    dashes_func = {1: educateDashes, 2: educateDashesOldSchool, 3: educateDashesOldSchoolInverted}.get(do_dashes, lambda x: x)
    backticks_func = {1: educateBackticks, 2: lambda x: educateSingleBackticks(educateBackticks(x))}.get(do_backticks, lambda x: x)
    ellipses_func = {1: educateEllipses}.get(do_ellipses, lambda x: x)
    stupefy_func = {1: stupefyEntities}.get(do_stupefy, lambda x: x)
    skipped_tag_stack = []
    tokens = _tokenize(text)
    result = []
    in_pre = False

    prev_token_last_char = ""
    # This is a cheat, used to get some context
    # for one-character tokens that consist of
    # just a quote char. What we do is remember
    # the last character of the previous text
    # token, to use as context to curl single-
    # character quote tokens correctly.

    for cur_token in tokens:
        if cur_token[0] == "tag":
            # Don't mess with quotes inside some tags.  This does not handle self <closing/> tags!
            result.append(cur_token[1])
            skip_match = tags_to_skip_regex.match(cur_token[1])
            if skip_match is not None:
                is_self_closing = self_closing_regex.search(skip_match.group()) is not None
                if not is_self_closing:
                    if not skip_match.group(1):
                        skipped_tag_stack.append(skip_match.group(2).lower())
                        in_pre = True
                    else:
                        if len(skipped_tag_stack) > 0:
                            if skip_match.group(2).lower() == skipped_tag_stack[-1]:
                                skipped_tag_stack.pop()
                            else:
                                pass
                                # This close doesn't match the open.  This isn't XHTML.  We should barf here.
                        if len(skipped_tag_stack) == 0:
                            in_pre = False
        else:
            t = cur_token[1]
            last_char = t[-1:]  # Remember last char of this token before processing.
            if not in_pre:
                t = processEscapes(t)

                t = re.sub('&quot;', '"', t)
                t = dashes_func(t)
                t = ellipses_func(t)
                # Note: backticks need to be processed before quotes.
                t = backticks_func(t)

                if do_quotes is not 0:
                    if t == "'":
                        # Special case: single-character ' token
                        if re.match("\S", prev_token_last_char):
                            t = "&#8217;"
                        else:
                            t = "&#8216;"
                    elif t == '"':
                        # Special case: single-character " token
                        if re.match("\S", prev_token_last_char):
                            t = "&#8221;"
                        else:
                            t = "&#8220;"

                    else:
                        # Normal case:
                        t = educateQuotes(t)

                t = stupefy_func(t)

            prev_token_last_char = last_char
            result.append(t)

    return "".join(result)


def educateQuotes(str):
    """
    Parameter:  String.

    Returns:    The string, with "educated" curly quote HTML entities.

    Example input:  "Isn't this fun?"
    Example output: &#8220;Isn&#8217;t this fun?&#8221;
    """

    punct_class = r"""[!"#\$\%'()*+,-.\/:;<=>?\@\[\\\]\^_`{|}~]"""

    # Special case if the very first character is a quote
    # followed by punctuation at a non-word-break. Close the quotes by brute force:
    str = re.sub(r"""^'(?=%s\\B)""" % (punct_class,), r"""&#8217;""", str)
    str = re.sub(r"""^"(?=%s\\B)""" % (punct_class,), r"""&#8221;""", str)

    # Special case for double sets of quotes, e.g.:
    #   <p>He said, "'Quoted' words in a larger quote."</p>
    str = re.sub(r""""'(?=\w)""", """&#8220;&#8216;""", str)
    str = re.sub(r"""'"(?=\w)""", """&#8216;&#8220;""", str)
    str = re.sub(r'''""(?=\w)''', """&#8220;&#8220;""", str)
    str = re.sub(r"""''(?=\w)""", """&#8216;&#8216;""", str)
    str = re.sub(r'''\"\'''',     """&#8221;&#8217;""", str)
    str = re.sub(r'''\'\"''',     """&#8217;&#8221;""", str)
    str = re.sub(r'''""''',       """&#8221;&#8221;""", str)
    str = re.sub(r"""''""",       """&#8217;&#8217;""", str)

    # Special case for decade abbreviations (the '80s --> ’80s):
    # See http://practicaltypography.com/apostrophes.html
    str = re.sub(r"""(\W|^)'(?=\d{2}s)""", r"""\1&#8217;""", str)
    # Measurements in feet and inches or longitude/latitude: 19' 43.5" --> 19′ 43.5″
    str = re.sub(r'''(\W|^)([-0-9.]+\s*)'(\s*[-0-9.]+)"''', r'\1\2&#8242;\3&#8243;', str)

    # Special case for Quotes at inside of other entities, e.g.:
    #   <p>A double quote--"within dashes"--would be nice.</p>
    str = re.sub(r"""(?<=\W)"(?=\w)""", r"""&#8220;""", str)
    str = re.sub(r"""(?<=\W)'(?=\w)""", r"""&#8216;""", str)
    str = re.sub(r"""(?<=\w)"(?=\W)""", r"""&#8221;""", str)
    str = re.sub(r"""(?<=\w)'(?=\W)""", r"""&#8217;""", str)

    # The following are commented out as smartypants tokenizes text by
    # stripping out html tags. Therefore, there is no guarantee that the
    # start-of-line and end-ol-line regex operators will match anything
    # meaningful

    # Special case for Quotes at end of line with a preceeding space (may change just to end of line)
    # str = re.sub(r"""(?<=\s)"$""", r"""&#8221;""", str)
    # str = re.sub(r"""(?<=\s)'$""", r"""&#8217;""", str)

    # Special case for Quotes at beginning of line with a space - multiparagraph quoted text:
    # str = re.sub(r"""^"(?=\s)""", r"""&#8220;""", str)
    # str = re.sub(r"""^'(?=\s)""", r"""&#8216;""", str)

    close_class = r"""[^\ \t\r\n\[\{\(\-]"""
    dec_dashes = r"""&#8211;|&#8212;"""

    # Get most opening single quotes:
    opening_single_quotes_regex = re.compile(r"""
            (
                \s          |   # a whitespace char, or
                &nbsp;      |   # a non-breaking space entity, or
                --          |   # dashes, or
                &[mn]dash;  |   # named dash entities
                %s          |   # or decimal entities
                &\#x201[34];    # or hex
            )
            '                 # the quote
            (?=\w)            # followed by a word character
            """ % (dec_dashes,), re.VERBOSE)
    str = opening_single_quotes_regex.sub(r"""\1&#8216;""", str)

    closing_single_quotes_regex = re.compile(r"""
            (%s)
            '
            (?!\s | s\b | \d)
            """ % (close_class,), re.VERBOSE)
    str = closing_single_quotes_regex.sub(r"""\1&#8217;""", str)

    closing_single_quotes_regex = re.compile(r"""
            (%s)
            '
            (\s | s\b)
            """ % (close_class,), re.VERBOSE)
    str = closing_single_quotes_regex.sub(r"""\1&#8217;\2""", str)

    # Any remaining single quotes should be opening ones:
    str = re.sub(r"""'""", r"""&#8216;""", str)

    # Get most opening double quotes:
    opening_double_quotes_regex = re.compile(r"""
            (
                \s          |   # a whitespace char, or
                &nbsp;      |   # a non-breaking space entity, or
                --          |   # dashes, or
                &[mn]dash;  |   # named dash entities
                %s          |   # or decimal entities
                &\#x201[34];    # or hex
            )
            "                 # the quote
            (?=\w)            # followed by a word character
            """ % (dec_dashes,), re.VERBOSE)
    str = opening_double_quotes_regex.sub(r"""\1&#8220;""", str)

    # Double closing quotes:
    closing_double_quotes_regex = re.compile(r"""
            #(%s)?   # character that indicates the quote should be closing
            "
            (?=\s)
            """ % (close_class,), re.VERBOSE)
    str = closing_double_quotes_regex.sub(r"""&#8221;""", str)

    closing_double_quotes_regex = re.compile(r"""
            (%s)   # character that indicates the quote should be closing
            "
            """ % (close_class,), re.VERBOSE)
    str = closing_double_quotes_regex.sub(r"""\1&#8221;""", str)

    if str.endswith('-"'):
        # A string that endswith -" is sometimes used for dialogue
        str = str[:-1] + '&#8221;'

    # Any remaining quotes should be opening ones.
    str = re.sub(r'"', r"""&#8220;""", str)

    return str


def educateBackticks(str):
    """
    Parameter:  String.
    Returns:    The string, with ``backticks'' -style double quotes
                translated into HTML curly quote entities.
    Example input:  ``Isn't this fun?''
    Example output: &#8220;Isn't this fun?&#8221;
    """

    str = re.sub(r"""``""", r"""&#8220;""", str)
    str = re.sub(r"""''""", r"""&#8221;""", str)
    return str


def educateSingleBackticks(str):
    """
    Parameter:  String.
    Returns:    The string, with `backticks' -style single quotes
                translated into HTML curly quote entities.

    Example input:  `Isn't this fun?'
    Example output: &#8216;Isn&#8217;t this fun?&#8217;
    """

    str = re.sub(r"""`""", r"""&#8216;""", str)
    str = re.sub(r"""'""", r"""&#8217;""", str)
    return str


def educateDashes(str):
    """
    Parameter:  String.

    Returns:    The string, with each instance of "--" translated to
                an em-dash HTML entity.
    """

    str = re.sub(r"""---""", r"""&#8211;""", str)  # en  (yes, backwards)
    str = re.sub(r"""--""", r"""&#8212;""", str)  # em (yes, backwards)
    return str


def educateDashesOldSchool(str):
    """
    Parameter:  String.

    Returns:    The string, with each instance of "--" translated to
                an en-dash HTML entity, and each "---" translated to
                an em-dash HTML entity.
    """

    str = re.sub(r"""---""", r"""&#8212;""", str)    # em (yes, backwards)
    str = re.sub(r"""--""", r"""&#8211;""", str)    # en (yes, backwards)
    return str


def educateDashesOldSchoolInverted(str):
    """
    Parameter:  String.

    Returns:    The string, with each instance of "--" translated to
                an em-dash HTML entity, and each "---" translated to
                an en-dash HTML entity. Two reasons why: First, unlike the
                en- and em-dash syntax supported by
                EducateDashesOldSchool(), it's compatible with existing
                entries written before SmartyPants 1.1, back when "--" was
                only used for em-dashes.  Second, em-dashes are more
                common than en-dashes, and so it sort of makes sense that
                the shortcut should be shorter to type. (Thanks to Aaron
                Swartz for the idea.)
    """
    str = re.sub(r"""---""", r"""&#8211;""", str)    # em
    str = re.sub(r"""--""", r"""&#8212;""", str)    # en
    return str


def educateEllipses(str):
    """
    Parameter:  String.
    Returns:    The string, with each instance of "..." translated to
                an ellipsis HTML entity.

    Example input:  Huh...?
    Example output: Huh&#8230;?
    """

    str = re.sub(r"""\.\.\.""", r"""&#8230;""", str)
    str = re.sub(r"""\. \. \.""", r"""&#8230;""", str)
    return str


def stupefyEntities(str):
    """
    Parameter:  String.
    Returns:    The string, with each SmartyPants HTML entity translated to
                its ASCII counterpart.

    Example input:  &#8220;Hello &#8212; world.&#8221;
    Example output: "Hello -- world."
    """

    str = re.sub(r"""&#8211;""", r"""-""", str)  # en-dash
    str = re.sub(r"""&#8212;""", r"""--""", str)  # em-dash

    str = re.sub(r"""&#8216;""", r"""'""", str)  # open single quote
    str = re.sub(r"""&#8217;""", r"""'""", str)  # close single quote

    str = re.sub(r"""&#8220;""", r'''"''', str)  # open double quote
    str = re.sub(r"""&#8221;""", r'''"''', str)  # close double quote

    str = re.sub(r"""&#8230;""", r"""...""", str)  # ellipsis

    return str


def processEscapes(str):
    r"""
    Parameter:  String.
    Returns:    The string, with after processing the following backslash
                escape sequences. This is useful if you want to force a "dumb"
                quote or other character to appear.

                Escape  Value
                ------  -----
                \\      &#92;
                \"      &#34;
                \'      &#39;
                \.      &#46;
                \-      &#45;
                \`      &#96;
    """
    str = re.sub(r"""\\\\""", r"""&#92;""", str)
    str = re.sub(r'''\\"''', r"""&#34;""", str)
    str = re.sub(r"""\\'""", r"""&#39;""", str)
    str = re.sub(r"""\\\.""", r"""&#46;""", str)
    str = re.sub(r"""\\-""", r"""&#45;""", str)
    str = re.sub(r"""\\`""", r"""&#96;""", str)

    return str


def _tokenize(str):
    """
    Parameter:  String containing HTML markup.
    Returns:    Reference to an array of the tokens comprising the input
                string. Each token is either a tag (possibly with nested,
                tags contained therein, such as <a href="<MTFoo>">, or a
                run of text between tags. Each element of the array is a
                two-element array; the first is either 'tag' or 'text';
                the second is the actual value.

    Based on the _tokenize() subroutine from Brad Choate's MTRegex plugin.
        <http://www.bradchoate.com/past/mtregex.php>
    """

    tokens = []

    # depth = 6
    # nested_tags = "|".join(['(?:<(?:[^<>]',] * depth) + (')*>)' * depth)
    # match = r"""(?: <! ( -- .*? -- \s* )+ > ) |  # comments
    # (?: <\? .*? \?> ) |  # directives
    # %s  # nested tags       """ % (nested_tags,)
    tag_soup = re.compile(r"""([^<]*)(<[^>]*>)""")

    token_match = tag_soup.search(str)

    previous_end = 0
    while token_match is not None:
        if token_match.group(1):
            tokens.append(['text', token_match.group(1)])

        tokens.append(['tag', token_match.group(2)])

        previous_end = token_match.end()
        token_match = tag_soup.search(str, token_match.end())

    if previous_end < len(str):
        tokens.append(['text', str[previous_end:]])

    return tokens


def run_tests(return_tests=False):
    import unittest
    sp = smartyPants

    class TestSmartypantsAllAttributes(unittest.TestCase):
        # the default attribute is "1", which means "all".

        def test_dates(self):
            self.assertEqual(sp("one two '60s"), "one two &#8217;60s")
            self.assertEqual(sp("1440-80's"), "1440-80&#8217;s")
            self.assertEqual(sp("1440-'80s"), "1440-&#8217;80s")
            self.assertEqual(sp("1440---'80s"), "1440&#8211;&#8217;80s")
            self.assertEqual(sp("1960s"), "1960s")  # no effect.
            self.assertEqual(sp("1960's"), "1960&#8217;s")
            self.assertEqual(sp("one two '60s"), "one two &#8217;60s")
            self.assertEqual(sp("'60s"), "&#8217;60s")

        def test_measurements(self):
            ae = self.assertEqual
            ae(sp("one two 1.1'2.2\""), "one two 1.1&#8242;2.2&#8243;")
            ae(sp("1' 2\""), "1&#8242; 2&#8243;")

        def test_skip_tags(self):
            self.assertEqual(
                sp("""<script type="text/javascript">\n<!--\nvar href = "http://www.google.com";\nvar linktext = "google";\ndocument.write('<a href="' + href + '">' + linktext + "</a>");\n//-->\n</script>"""),  # noqa
                   """<script type="text/javascript">\n<!--\nvar href = "http://www.google.com";\nvar linktext = "google";\ndocument.write('<a href="' + href + '">' + linktext + "</a>");\n//-->\n</script>""")  # noqa
            self.assertEqual(
                sp("""<p>He said &quot;Let's write some code.&quot; This code here <code>if True:\n\tprint &quot;Okay&quot;</code> is python code.</p>"""),
                   """<p>He said &#8220;Let&#8217;s write some code.&#8221; This code here <code>if True:\n\tprint &quot;Okay&quot;</code> is python code.</p>""")  # noqa

            self.assertEqual(
                sp('''<script/><p>It's ok</p>'''),
                '''<script/><p>It&#8217;s ok</p>''')

        def test_ordinal_numbers(self):
            self.assertEqual(sp("21st century"), "21st century")  # no effect.
            self.assertEqual(sp("3rd"), "3rd")  # no effect.

        def test_educated_quotes(self):
            self.assertEqual(sp('''"Isn't this fun?"'''), '''&#8220;Isn&#8217;t this fun?&#8221;''')

    tests = unittest.defaultTestLoader.loadTestsFromTestCase(TestSmartypantsAllAttributes)
    if return_tests:
        return tests
    unittest.TextTestRunner(verbosity=4).run(tests)


if __name__ == "__main__":
    run_tests()
