Function Mode for Search & Replace in the Editor
=======================================================================

The Search & Replace tool in the editor support a *function mode*. In this
mode, you can combine regular expressions (see :doc:`regexp`) with
arbitrarily powerful python functions to do all sorts of advanced text
processing. 

In the standard *regexp* mode for search and replace, you specify both a
regular expression to search for as well as a template that is used to replace
all found matches. In function mode, instead of using a fixed template, you
specify an arbitrary function, in the 
`python programming language <https://docs.python.org/2.7/>`_. This allows
you to do lots of things that are not possible with simple templates. 

Techniques for using function mode and the syntax will be described by means of
examples, showing you how to create functions to perform progressively more
complex tasks.


.. image:: images/function_replace.png
    :alt: The Function mode
    :align: center

Automatically fixing the case of headings in the document
-------------------------------------------------------------

Here, we will leverage one of the builtin functions in the editor to
automatically change the case of all text inside heading tags to title case::

    Find expression: <[Hh][1-6][^>]*>([^<>]+)</[hH][1-6]>
    
For the function, simply choose the :guilabel:`Title-case text` builtin
function. The will change titles that look like: ``<h1>some TITLE</h1>`` to
``<h1>Some Title</h1>``.


Your first custom function - smartening hyphens
------------------------------------------------------------------

The real power of function mode comes from being able to create your own
functions to process text in arbitrary ways. The Smarten Punctuation tool in
the editor leaves individual hyphens alone, so you can use the this function to
replace them with em-dashes.

To create a new function, simply click the Create/Edit button to create a new
function and copy the python code from below.

.. code-block:: python

    def replace(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
        return match.group().replace('--', '—').replace('-', '—')

Every Search & Replace custom function must have a unique name and consist of a
python function named replace, that accepts all the arguments shown above. 
For the moment, we wont worry about all the different arguments to
``replace()`` function. Just focus on the ``match`` argument. It represents a
match when running a search and replace. Its full documentation in available
`here <https://docs.python.org/2.7/library/re.html#match-objects>`_.
``match.group()`` simply returns all the matched text and all we do is replace
hyphens in that text with em-dashes, first replacing double hyphens and
then single hyphens.

Use this function with the find regular expression::

    >[^<>]+<

And it will replace all hyphens with em-dashes, but only in actual text and not
inside HTML tag definitions.


The power of function mode - using a spelling dictionary to fix mis-hyphenated words
----------------------------------------------------------------------------------------

Often, ebooks created from scans of printed books contain mis-hyphenated words
-- words that were split at the end of the line on the printed page. We will
write a simple function to automatically find and fix such words.

.. code-block:: python

    import regex

    def replace(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):

        def replace_word(wmatch):
            # Try to remove the hyphen and replace the words if the resulting
            # hyphen free word is recognized by the dictionary
            without_hyphen = wmatch.group(1) + wmatch.group(2)
            if dictionaries.recognized(without_hyphen):
                return without_hyphen
            return wmatch.group()

        # Search for words split by a hyphen
        return regex.sub(r'(\w+)\s*-\s*(\w+)', replace_word, match.group(), flags=regex.VERSION1 | regex.UNICODE)

Use this function with the same find expressions as before, namely::

    >[^<>]+<

And it will magically fix all mis-hyphenated words in the text of the book. The
main trick is to use one of the useful extra arguments to the replace function,
``dictionaries``.  This refers to the dictionaries the editor itself uses to
spell check text in the book. What this function does is look for words
separated by a hyphen, remove the hyphen and check if the dictionary recognizes
the composite word, if it does, the original words are replaced by the hyphen
free composite word.

Note that one limitation of this technique is it will only work for
mono-lingual books, because, by default, ``dictionaries.recognized()`` uses the
main language of the book.
