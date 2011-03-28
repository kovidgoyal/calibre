
.. include:: global.rst

.. _regexptutorial:

All about using regular expressions in |app|
=======================================================

Regular expressions are features used in many places in |app| to perform sophisticated manipulation of ebook content and metadata. This tutorial is a gentle introduction to getting you started with using regular expressions in |app|.

.. contents:: Contents
  :depth: 2
  :local:


First, a word of warning and a word of courage
-------------------------------------------------

This is, inevitably, going to be somewhat technical- after all, regular expressions are a technical tool for doing technical stuff. I'm going to have to use some jargon and concepts that may seem complicated or convoluted. I'm going to try to explain those concepts as clearly as I can, but really can't do without using them at all. That being said, don't be discouraged by any jargon, as I've tried to explain everything new. And while regular expressions themselves may seem like an arcane, black magic (or, to be more prosaic, a random string of mumbo-jumbo letters and signs), I promise that they are not all that complicated. Even those who understand regular expressions really well have trouble reading the more complex ones, but writing them isn't as difficult- you construct the expression step by step. So, take a step and follow me into the rabbit hole.

Where in |app| can you use regular expressions?
---------------------------------------------------

There are a few places |app| uses regular expressions. There's the Search & Replace in conversion options, metadata detection from filenames in the import settings and Search & Replace when editing the metadata of books in bulk.

What on earth *is* a regular expression?
------------------------------------------------

A regular expression is a way to describe sets of strings. A single regular expression cat *match* a number of different strings. This is what makes regular expression so powerful -- they are a concise way of describing a potentially large number of variations.

.. note:: I'm using string here in the sense it is used in programming languages: a string of one or more characters, characters including actual characters, numbers, punctuation and so-called whitespace (linebreaks, tabulators etc.). Please note that generally, uppercase and lowercase characters are not considered the same, thus "a" being a different character from "A" and so forth. In |app|, regular expressions are case insensitive in the search bar, but not in the conversion options. There's a way to make every regular expression case insensitive, but we'll discuss that later. It gets complicated because regular expressions allow for variations in the strings it matches, so one expression can match multiple strings, which is why people bother using them at all. More on that in a bit.

Care to explain?
--------------------

Well, that's why we're here. First, this is the most important concept in regular expressions: *A string by itself is a regular expression that matches itself*. That is to say, if I wanted to match the string ``"Hello, World!"`` using a regular expression, the regular expression to use would be ``Hello, World!``. And yes, it really is that simple. You'll notice, though, that this *only* matches the exact string ``"Hello, World!"``, not e.g. ``"Hello, wOrld!"`` or ``"hello, world!"`` or any other such variation. 

That doesn't sound too bad. What's next?
------------------------------------------

Next is the beginning of the really good stuff. Remember where I said that regular expressions can match multiple strings? This is were it gets a little more complicated. Say, as a somewhat more practical exercise, the ebook you wanted to convert had a nasty footer counting the pages, like "Page 5 of 423". Obviously the page number would rise from 1 to 423, thus you'd have to match 423 different strings, right? Wrong, actually: regular expressions allow you to define sets of characters that are matched: To define a set, you put all the characters you want to be in the set into square brackets. So, for example, the set ``[abc]`` would match either the character "a", "b" or "c". *Sets will always only match one of the characters in the set*. They "understand" character ranges, that is, if you wanted to match all the lower case characters, you'd use the set ``[a-z]`` for lower- and uppercase characters you'd use ``[a-zA-Z]`` and so on. Got the idea? So, obviously, using the expression ``Page [0-9] of 423`` you'd be able to match the first 9 pages, thus reducing the expressions needed to three: The second expression ``Page [0-9][0-9] of 423`` would match all two-digit page numbers, and I'm sure you can guess what the third expression would look like. Yes, go ahead. Write it down.

Hey, neat! This is starting to make sense!
---------------------------------------------

I was hoping you'd say that. But brace yourself, now it gets even better! We just saw that using sets, we could match one of several characters at once. But you can even repeat a character or set, reducing the number of expressions needed to handle the above page number example to one. Yes, ONE! Excited? You should be! It works like this: Some so-called special characters, "+", "?" and "*", *repeat the single element preceding them*. (Element means either a single character, a character set, an escape sequence or a group (we'll learn about those last two later)- in short, any single entity in a regular expression.) These characters are called wildcards or quantifiers. To be more precise, "?" matches *0 or 1* of the preceding element, "*" matches *0 or more* of the preceding element and "+" matches *1 or more* of the preceding element. A few examples: The expression ``a?`` would match either "" (which is the empty string, not strictly useful in this case) or "a", the expression ``a*`` would match "", "a", "aa" or any number of a's in a row, and, finally, the expression ``a+`` would match "a", "aa" or any number of a's in a row (Note: it wouldn't match the empty string!). Same deal for sets: The expression ``[0-9]+`` would match *every integer number there is*! I know what you're thinking, and you're right: If you use that in the above case of matching page numbers, wouldn't that be the single one expression to match all the page numbers? Yes, the expression ``Page [0-9]+ of 423`` would match every page number in that book!

.. note::
    A note on these quantifiers: They generally try to match as much text as possible, so be careful when using them. This is called "greedy behaviour"- I'm sure you get why. It gets problematic when you, say, try to match a tag. Consider, for example, the string ``"<p class="calibre2">Title here</p>"`` and let's say you'd want to match the opening tag (the part between the first pair of angle brackets, a little more on tags later). You'd think that the expression ``<p.*>`` would match that tag, but actually, it matches the whole string! (The character "." is another special character. It matches anything *except* linebreaks, so, basically, the expression ``.*`` would match any single line you can think of.) Instead, try using ``<p.*?>`` which makes the quantifier ``"*"`` non-greedy. That expression would only match the first opening tag, as intended.
    There's actually another way to accomplish this: The expression ``<p[^>]*>`` will match that same opening tag- you'll see why after the next section. Just note that there quite frequently is more than one way to write a regular expression.

Well, these special characters are very neat and all, but what if I wanted to match a dot or a question mark?
-----------------------------------------------------------------------------------------------------------------

You can of course do that: Just put a backslash in front of any special character and it is interpreted as the literal character, without any special meaning. This pair of a backslash followed by a single character is called an escape sequence, and the act of putting a backslash in front of a special character is called escaping that character. An escape sequence is interpreted as a single element. There are of course escape sequences that do more than just escaping special characters, for example ``"\t"`` means a tabulator. We'll get to some of the escape sequences later. Oh, and by the way, concerning those special characters: Consider any character we discuss in this introduction as having some function to be special and thus needing to be escaped if you want the literal character.

So, what are the most useful sets?
------------------------------------

Knew you'd ask. Some useful sets are ``[0-9]`` matching a single number, ``[a-z]`` matching a single lowercase letter, ``[A-Z]`` matching a single uppercase letter, ``[a-zA-Z]`` matching a single letter and ``[a-zA-Z0-9]`` matching a single letter or number. You can also use an escape sequence as shorthand:: 

    \d is equivalent to [0-9]
    \w is equivalent to [a-zA-Z0-9_]
    \s is equivalent to any whitespace
    
.. note::
    "Whitespace" is a term for anything that won't be printed. These characters include space, tabulator, line feed, form feed and carriage return. 
    
As a last note on sets, you can also define a set as any character *but* those in the set. You do that by including the character ``"^"`` as the *very first character in the set*. Thus, ``[^a]`` would match any character excluding "a". That's called complementing the set. Those escape sequence shorthands we saw earlier can also be complemented: ``"\D"`` means any non-number character, thus being equivalent to ``[^0-9]``. The other shorthands can be complemented by, you guessed it, using the respective uppercase letter instead of the lowercase one. So, going back to the example ``<p[^>]*>`` from the previous section, now you can see that the character set it's using tries to match any character except for a closing angle bracket.

But if I had a few varying strings I wanted to match, things get complicated?
-------------------------------------------------------------------------------

Fear not, life still is good and easy. Consider this example: The book you're converting has "Title" written on every odd page and "Author" written on every even page. Looks great in print, right? But in ebooks, it's annoying. You can group whole expressions in normal parentheses, and the character ``"|"`` will let you match *either* the expression to its right *or* the one to its left. Combine those and you're done. Too fast for you? Okay, first off, we group the expressions for odd and even pages, thus getting ``(Title)(Author)`` as our two needed expressions. Now we make things simpler by using the vertical bar (``"|"`` is called the vertical bar character): If you use the expression ``(Title|Author)`` you'll either get a match for "Title" (on the odd pages) or you'd match "Author" (on the even pages). Well, wasn't that easy?

You can, of course, use the vertical bar without using grouping parentheses, as well. Remember when I said that quantifiers repeat the element preceding them? Well, the vertical bar works a little differently: The expression "Title|Author" will also match either the string "Title" or the string "Author", just as the above example using grouping. *The vertical bar selects between the entire expression preceding and following it*. So, if you wanted to match the strings "Calibre" and "calibre" and wanted to select only between the upper- and lowercase "c", you'd have to use the expression ``(c|C)alibre``, where the grouping ensures that only the "c" will be selected. If you were to use ``c|Calibre``, you'd get a match on the string "c" or on the string "Calibre", which isn't what we wanted. In short: If in doubt, use grouping together with the vertical bar.

You missed...
-------------------

... wait just a minute, there's one last, really neat thing you can do with groups. If you have a group that you previously matched, you can use references to that group later in the expression: Groups are numbered starting with 1, and you reference them by escaping the number of the group you want to reference, thus, the fifth group would be referenced as ``\5``. So, if you searched for ``([^ ]+) \1`` in the string "Test Test", you'd match the whole string!


In the beginning, you said there was a way to make a regular expression case insensitive?
------------------------------------------------------------------------------------------------------------------

Yes, I did, thanks for paying attention and reminding me. You can tell |app| how you want certain things handled by using something called flags. You include flags in your expression by using the special construct ``(?flags go here)`` where, obviously, you'd replace "flags go here" with the specific flags you want. For ignoring case, the flag is ``i``, thus you include ``(?i)`` in your expression. Thus, ``test(?i)`` would match "Test", "tEst", "TEst" and any case variation you could think of.

Another useful flag lets the dot match any character at all, *including* the newline, the flag ``s``. If you want to use multiple flags in an expression, just put them in the same statement: ``(?is)`` would ignore case and make the dot match all. It doesn't matter which flag you state first, ``(?si)`` would be equivalent to the above. By the way, good places for putting flags in your expression would be either the very beginning or the very end. That way, they don't get mixed up with anything else.

I think I'm beginning to understand these regular expressions now... how do I use them in |app|?
-----------------------------------------------------------------------------------------------------

Conversions
^^^^^^^^^^^^^^

Let's begin with the conversion settings, which is really neat. In the Search and Replace part, you can input a regexp (short for regular expression) that describes the string that will be replaced during the conversion. The neat part is the wizard. Click on the wizard staff and you get a preview of what |app| "sees" during the conversion process. Scroll down to the string you want to remove, select and copy it, paste it into the regexp field on top of the window. If there are variable parts, like page numbers or so, use sets and quantifiers to cover those, and while you're at it, remember to escape special characters, if there are some. Hit the button labeled :guilabel:`Test` and |app| highlights the parts it would replace were you to use the regexp. Once you're satisfied, hit OK and convert. Be careful if your conversion source has tags like this example::

    Maybe, but the cops feel like you do, Anita. What's one more dead vampire?
    New laws don't change that. </p>
    <p class="calibre4"> <b class="calibre2">Generated by ABC Amber LIT Conv
    <a href="http://www.processtext.com/abclit.html" class="calibre3">erter,
    http://www.processtext.com/abclit.html</a></b></p>
    <p class="calibre4"> It had only been two years since Addison v. Clark.
    The court case gave us a revised version of what life was
    
(shamelessly ripped out of `this thread <http://www.mobileread.com/forums/showthread.php?t=75594">`_). You'd have to remove some of the tags as well. In this example, I'd recommend beginning with the tag ``<b class="calibre2">``, now you have to end with the corresponding closing tag (opening tags are ``<tag>``, closing tags are ``</tag>``), which is simply the next ``</b>`` in this case. (Refer to a good HTML manual or ask in the forum if you are unclear on this point.) The opening tag can be described using ``<b.*?>``, the closing tag using ``</b>``, thus we could remove everything between those tags using ``<b.*?>.*?</b>``. But using this expression would be a bad idea, because it removes everything enclosed by <b>- tags (which, by the way, render the enclosed text in bold print), and it's a fair bet that we'll remove portions of the book in this way. Instead, include the beginning of the enclosed string as well, making the regular expression ``<b.*?>\s*Generated\s+by\s+ABC\s+Amber\s+LIT.*?</b>`` The ``\s`` with quantifiers are included here instead of explicitly using the spaces as seen in the string to catch any variations of the string that might occur. Remember to check what |app| will remove to make sure you don't remove any portions you want to keep if you test a new expression. If you only check one occurrence, you might miss a mismatch somewhere else in the text. Also note that should you accidentally remove more or fewer tags than you actually wanted to, |app| tries to repair the damaged code after doing the removal.

Adding books
^^^^^^^^^^^^^^^^

Another thing you can use regular expressions for is to extract metadata from filenames. You can find this feature in the "Adding books" part of the settings. There's a special feature here: You can use field names for metadata fields, for example ``(?P<title>)`` would indicate that calibre uses this part of the string as book title. The allowed field names are listed in the windows, together with another nice test field. An example: Say you want to import a whole bunch of files named like ``Classical Texts: The Divine Comedy by Dante Alighieri.mobi``.
(Obviously, this is already in your library, since we all love classical italian poetry) or ``Science Fiction epics: The Foundation Trilogy by Isaac Asimov.epub``. This is obviously a naming scheme that |app| won't extract any meaningful data out of - its standard expression for extracting metadata is ``(?P<title>.+) - (?P<author>[^_]+)``. A regular expression that works here would be ``[a-zA-Z]+: (?P<title>.+) by (?P<author>.+)``. Please note that, inside the group for the metadata field, you need to use expressions to describe what the field actually matches. And also note that, when using the test field |app| provides, you need to add the file extension to your testing filename, otherwise you won't get any matches at all, despite using a working expression.

Bulk editing metadata
^^^^^^^^^^^^^^^^^^^^^^^

The last part is regular expression search and replace in metadata fields. You can access this by selecting multiple books in the library and using bulk metadata edit. Be very careful when using this last feature, as it can do **Very Bad Things** to your library! Doublecheck that your expressions do what you want them to using the test fields, and only mark the books you really want to change! In the regular expression search mode, you can search in one field, replace the text with something and even write the result into another field. A practical example: Say your library contained the books of Frank Herbert's Dune series, named after the fashion ``Dune 1 - Dune``, ``Dune 2 - Dune Messiah`` and so on. Now you want to get ``Dune`` into the series field. You can do that by searching for ``(.*?) \d+ - .*`` in the title field and replacing it with ``\1`` in the series field. See what I did there? That's a reference to the first group you're replacing the series field with. Now that you have the series all set, you only need to do another search for ``.*? -`` in the title field and replace it with ``""`` (an empty string), again in the title field, and your metadata is all neat and tidy. Isn't that great? By the way, instead of replacing the entire field, you can also append or prepend to the field, so, if you *wanted* the book title to be prepended with series info, you could do that as well. As you by now have undoubtedly noticed, there's a checkbox labeled :guilabel:`Case sensitive`, so you won't have to use flags to select behaviour here.

Well, that just about concludes the very short introduction to regular expressions. Hopefully I'll have shown you enough to at least get you started and to enable you to continue learning by yourself- a good starting point would be the `Python documentation for regexps <http://docs.python.org/library/re.html>`_.

One last word of warning, though: Regexps are powerful, but also really easy to get wrong. |app| provides really great testing possibilities to see if your expressions behave as you expect them to. Use them. Try not to shoot yourself in the foot. (God, I love that expression...) But should you, despite the warning, injure your foot (or any other body parts), try to learn from it.

Credits
-------------

Thanks for helping with tips, corrections and such:

    * ldolse
    * kovidgoyal
    * chaley
    * dwanthny
    * kacir
    * Starson17

For more about regexps see `The Python User Manual <http://docs.python.org/library/re.html>`_.

