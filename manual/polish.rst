.. _polish_api:

API documentation for the e-book editing tools
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
        report_error # No book has been opened yet


The Container object
----------------------

.. autoclass:: Container
   :members:

Managing component files in a container
--------------------------------------------------------

.. module:: calibre.ebooks.oeb.polish.replace

.. autofunction:: replace_links

.. autofunction:: rename_files

.. autofunction:: get_recommended_folders

Pretty printing and auto fixing parse errors
--------------------------------------------------------

.. module:: calibre.ebooks.oeb.polish.pretty

.. autofunction:: fix_html

.. autofunction:: fix_all_html

.. autofunction:: pretty_html

.. autofunction:: pretty_css

.. autofunction:: pretty_xml

.. autofunction:: pretty_all


Managing book jackets
-----------------------

.. module:: calibre.ebooks.oeb.polish.jacket

.. autofunction:: remove_jacket

.. autofunction:: add_or_replace_jacket

Splitting and merging of files
---------------------------------

.. module:: calibre.ebooks.oeb.polish.split

.. autofunction:: split

.. autofunction:: multisplit

.. autofunction:: merge

Managing covers
-------------------

.. module:: calibre.ebooks.oeb.polish.cover

.. autofunction:: set_cover

.. autofunction:: mark_as_cover

.. autofunction:: mark_as_titlepage

Working with CSS
-------------------

.. autofunction:: calibre.ebooks.oeb.polish.fonts.change_font

.. module:: calibre.ebooks.oeb.polish.css

.. autofunction:: remove_unused_css

.. autofunction:: filter_css


Working with the Table of Contents
-----------------------------------

.. module:: calibre.ebooks.oeb.polish.toc

.. autofunction:: from_xpaths

.. autofunction:: from_links

.. autofunction:: from_files

.. autofunction:: create_inline_toc


Edit book tool
--------------------

.. autoclass:: calibre.gui2.tweak_book.plugin.Tool
   :show-inheritance:
   :members:
   :member-order: bysource


Controlling the editor's user interface
-----------------------------------------

The ebook editor's user interface is controlled by a single global *Boss*
object. This has many useful methods that can be used in plugin code to
perform common tasks.

.. module:: calibre.gui2.tweak_book.boss

.. autoclass:: Boss
   :members:

