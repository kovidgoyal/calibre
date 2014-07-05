
.. include:: global.rst

.. _polish_api:

API Documentation for the ebook editing tools
===============================================

The ebook editing tools consist of a
:class:`calibre.ebooks.oeb.polish.container.Container` object that represents a
book as a collection of HTML + resource files, and various tools that can be
used to perform operations on the container. All the tools are in the form of
module level functions in the various ``calibre.ebooks.oeb.polish.*`` modules.

.. module:: calibre.ebooks.oeb.polish.container
    :synopsis: The container object used to represent a book as a collection of its constituent HTML files.

You obtain a container object for a book at a path like this::

    from calibre.ebooks.oeb.polish.container import get_container
    container = get_container('Path to book file', tweak_mode=True)

If you are writing a plugin for the ebook editor, you get the current container
for the book being edited like this::

    from calibre.gui2.tweak_book import current_container
    container = current_container()
    if container is None:
        # No book has been opened yet


The Container object
----------------------

.. autoclass:: Container
   :members:


