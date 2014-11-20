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
    from calibre import replace_entities
    from calibre import prepare_string_for_xml

    def replace(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):

        def replace_word(wmatch):
            # Try to remove the hyphen and replace the words if the resulting
            # hyphen free word is recognized by the dictionary
            without_hyphen = wmatch.group(1) + wmatch.group(2)
            if dictionaries.recognized(without_hyphen):
                return without_hyphen
            return wmatch.group()

        # Search for words split by a hyphen
        text = replace_entities(match.group()[1:-1])  # Handle HTML entities like &amp;
        corrected = regex.sub(r'(\w+)\s*-\s*(\w+)', replace_word, text, flags=regex.VERSION1 | regex.UNICODE)
        return '>%s<' % prepare_string_for_xml(corrected)  # Put back required entities 

Use this function with the same find expression as before, namely::

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


Auto numbering sections
---------------------------

Now we will see something a little different. Suppose your HTML file has many
sections, each with a heading in an :code:`<h2>` tag that looks like
:code:`<h2>Some text</h2>`. You can create a custom function that will
automatically number these headings with consecutive section numbers, so that
they look like :code:`<h2>1. Some text</h2>`.

.. code-block:: python

    def replace(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
        section_number = '%d. ' % number
        return match.group(1) + section_number + match.group(2)

Use it with the find expression::

    (<h2[^<>]*>)([^<>]+</h2>)

Place the cursor at the top of the file and click :guilabel:`Replace all`. This
function uses another of the useful extra arguments to ``replace()``: the
``number`` argument. When doing a :guilabel:`Replace All` number is
automatically incremented for every successive match.


Auto create a Table of Contents
-------------------------------------

Finally, lets try something a little more ambitious. Suppose your book has
headings in ``h1`` and ``h2`` tags that look like 
``<h1 id="someif">Some Text</h1>``. We will auto-generate an HTML Table of
Contents based on these headings. Create the custom function below:

.. code-block:: python

    from calibre import replace_entities
    from calibre.ebooks.oeb.polish.toc import TOC, toc_to_html
    from calibre.gui2.tweak_book import current_container
    from calibre.ebooks.oeb.base import xml2str

    def replace(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
        if match is None:
            # All matches found, output the resulting Table of Contents.
            # The argument metadata is the metadata of the book being edited
            if 'toc' in data:
                book = current_container()
                toc = data['toc']
                # Re-arrange the entries in the spine order of the book
                spine_order = {name:i for i, (name, is_linear) in enumerate(book.spine_names)}
                toc.sort(key=lambda x: spine_order.get(x[0]))
                root = TOC()
                for (file_name, tag_name, anchor, text) in toc:
                    parent = root.children[-1] if tag_name == 'h2' and root.children else root
                    parent.add(text, file_name, anchor)
                toc = toc_to_html(root, book, 'toc.html', 'Table of Contents for ' + metadata.title, metadata.language)
                print (xml2str(toc))
            else:
                print ('No headings to build ToC from found')
        else:
            # Add an entry corresponding to this match to the Table of Contents
            if 'toc' not in data:
                # The entries are stored in the data object, which will persist
                # for all invocations of this function during a 'Replace All' operation
                data['toc'] = []
            tag_name, anchor, text = match.group(1), replace_entities(match.group(2)), replace_entities(match.group(3))
            data['toc'].append((file_name, tag_name, anchor, text))
            return match.group()  # We dont want to make any actual changes, so return the original matched text

    # Ensure that we are called once after the last match is found so we can
    # output the ToC
    replace.call_after_last_match = True

And use it with the find expression::

    <(h[12]) [^<>]* id=['"]([^'"]+)['"][^<>]*>([^<>]+)

Run the search of :guilabel:`All text files` and at the end of the search, a
window will popup with "Debug Output from your function" which will have the
HTML Table of Contents, ready to be pasted into :file:`toc.html`.

The function above is heavily commented, so it should be easy to follow. The
key new feature is the use of another useful extra argument to the
``replace()`` function, the ``data`` object. The ``data`` object is a python
*dict* that persists between all successive invocations of ``replace()`` during
a single :guilabel:`Replace All` operation.

Another new feature is the use of ``call_after_last_match`` setting that to
True on the ``replace()`` function means that the editor will call
``replace()`` one extra time after all matches have been found. For this extra
call, the match object will be ``None``.
