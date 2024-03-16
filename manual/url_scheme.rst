The calibre:// URL scheme
=========================================

calibre registers itself as the handler program for calibre:// URLs. So you can
use these to perform actions like opening books, searching for books, etc from
other programs/documents or via the command line. For example, running the
following at the command line::

    calibre calibre://switch-library/Some_Library

Will open calibre with the library named ``Some Library``. Library names are
the folder name of the library folder with spaces replaced by underscores. The
special value ``_`` means the current library.
The various types of URLs are documented below.

You can even place these links inside HTML files or Word documents or similar
and the operating system will automatically run calibre to perform the
specified action.


.. contents::
    :depth: 1
    :local:

Switch to a specific library
-------------------------------

The URL syntax is::

    calibre://switch-library/Library_Name

Library names are the folder name of the library with spaces replaced by
underscores. The special value ``_`` means the current library. You can also
use :ref:`hex encoding <hex_encoding>` for the library names, useful if the library names have
special characters that would otherwise require URL encoding. Hex encoded
library names look like::

    _hex_-AD23F4BC

Where the part after the ``_hex_-`` prefix is the library name encoded as UTF-8
and every byte represented by two hexadecimal characters.


Show a specific book in calibre
-------------------------------

The URL syntax is::

    calibre://show-book/Library_Name/book_id

This will show the book with ``book_id`` (a number) in calibre. The ids for
books can be seen in the calibre interface by hovering over the
:guilabel:`Click to open` link in the :guilabel:`Book details` panel, it is the number in
brackets at the end of the path to the book folder.

You can copy a link to the current book displayed in calibre by right clicking
the :guilabel:`Book details` panel and choosing :guilabel:`Copy link to book`.

If a search is active and the book is not matched by the search then the search is cleared.

If a Virtual library is selected, calibre will use it when showing the book. If
the book isn't found in that virtual library then the virtual library is cleared.

If you want to switch to a particular Virtual library when showing the book, use::

    calibre://show-book/Library_Name/book_id?virtual_library=Library%20Name
    or
    calibre://show-book/Library_Name/book_id?encoded_virtual_library=hex_encoded_virtual_library_name

replacing spaces in the Virtual library name by ``%20``. If the book isn't found in that
virtual library then the virtual library is ignored.


Open a specific book in the E-book viewer at a specific position
-------------------------------------------------------------------

The URL syntax is::

    calibre://view-book/Library_Name/book_id/book_format?open_at=location

Here, ``book_format`` is the format of the book, for example, ``EPUB`` or
``MOBI`` and the ``location`` is an optional location inside the book. The
easiest way to get these links is to open a book in the viewer, then in the
viewer controls select :guilabel:`Go to->Location` and there such a link
will be given that you can copy/paste elsewhere.


Searching for books
------------------------------

The URL syntax is::

    calibre://search/Library_Name?q=query
    calibre://search/Library_Name?eq=hex_encoded_query

Here query is any valid :ref:`search expression <search_interface>`. If the
search expression is complicated, :ref:`encode it as a hex string <hex_encoding>`
and use ``eq`` instead. Leaving out the query will cause the current search to
be cleared.

By default, if a Virtual library is selected, calibre will clear it before
doing the search to ensure all books are found. If you want to preserve the
Virtual library, use::

    calibre://search/Library_Name?q=query&virtual_library=_

If you want to switch to a particular Virtual library, use::

    calibre://search/Library_Name?virtual_library=Library%20Name
    or
    calibre://search/Library_Name?encoded_virtual_library=hex_encoded_virtual_library_name

replacing spaces in the Virtual library name by ``%20``.

If you perform a search in calibre and want to generate a link for it you can
do so by right clicking the search bar and choosing :guilabel:`Copy search as
URL`.

Open a book details window on a book in some library
------------------------------------------------------

The URL syntax is::

    calibre://book-details/Library_Name/book_id

This opens a book details window on the specified book from the specified library without changing the
current library or the selected book.


Open the notes associated with an author/series/etc.
------------------------------------------------------

The URL syntax is::

    calibre://book-details/Library_Name/Field_Name/id_Item_Id

This opens a window showing the notes of the specified item.
The easiest way to create such URLs is to show the notes you want
in calibre and click the :guilabel:`Copy URL` button to copy the URL
to the clipboard and paste it wherever you need.

Here ``Field_Name`` is the name of the columns such as ``authors`` or ``tags``.
For user created columns, replace the leading ``#`` in the field name with
an underscore, so ``#mytags`` becomes ``_mytags``.

In addition to specifying items by id using ``Item_Id`` you can also specify
them by name using either ``val_Item_Name`` or ``hex_Hex_Encoded_Item_Name``.
For example::

    calibre://book-details/Library_Name/authors/val_John%20Doe


.. _hex_encoding:

Hex encoding of URL parameters
----------------------------------

Hex encoding of URL parameters is done by first encoding the parameter as UTF-8
bytes, and then replacing each byte by two hexadecimal characters representing
the byte. For example, the string ``abc`` is the bytes ``0x61 0x62 and 0x63`` in
UTF-8, so the encoded version is the string: ``616263``.
