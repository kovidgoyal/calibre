.. include:: global.rst

.. _edit:

Editing E-books 
========================

|app| has an integrated e-book editor that can be used to edit books in the
EPUB and AZW3 (Kindle) formats. The editor shows you the HTML and CSS that is
used internally inside the book files, with a live preview that updates as you
make changes. It also contains various automated tools to perform common
cleanup and fixing tasks.

You can use this editor by right clicking on any book in |app| and selecting
:guilabel:`Edit book`.

.. image:: images/edit-book.png
    :alt: The Edit Book tool
    :align: center

.. contents:: Contents
  :depth: 1
  :local:


Basic workflow
---------------

When you first open a book with the Edit book tool, you will be presented with
a list of files on the left. These are the individual HTML files, stylesheets,
images, etc. that make up the content of the book. Simply double click on a
file to start editing it. Note that if you want to do anything more
sophisticated than making a few small tweaks, you will need to know `HTML
Tutorial <http://html.net/tutorials/html/>`_ and `CSS Tutorial
<http://html.net/tutorials/css/>`_.

As you make changes to the HTML or CSS in the editor, the changes will be
previewed, live, in the preview panel to the right. When you are happy with how
the changes you have made look, click the Save button or use
:guilabel:`File->Save` to save your changes into the ebook. 

One useful feature is :guilabel:`Checkpoints`. Before you embark on some
ambitious set of edits, you can create a checkpoint. The checkpoint
will preserve the current state of your book, then if in the future you decide
you dont like the changes you have made to you can go back to the state when
you created the checkpoint. To create a checkpoint, use :guilabel:`Edit->Create
checkpoint`. Checkpoints will also be automatically created for you whenever you
run any automated tool like global search and replace. The checkpointing
functionality is in addition to the normal Undo/redo mechanism when editing
individual files. Checkpoints are useful for when changes are spread over
multiple files in the book.

That is the basic work flow for editing books -- Open a file, make changes,
preview and save. The rest of this manual will discuss the various tools and
features present to allow you to perform specific tasks efficiently.

The Files Browser
------------------

.. image:: images/files_browser.png
    :class: float-left-img

The :guilabel:`Files Browser` gives you an overview of the various files inside
the book you are editing. The files are arranged by category, with text (HTML)
files at the top, followed by stylesheet (CSS) files, images and so on. Simply
double click on a file to start editing it. Editing is supported for HTML, CSS
and image files. The order of text files is the same order that they would be
displayed in, if you were reading the book. All other files are arranged
alphabetically.

By hovering your mouse over an entry, you can see its size, and also, at
the bottom of the screen, the full path to the file inside the book. Note that
files inside ebooks are compressed, so the size of the final book is not the
sum of the individual file sizes.

Many files have special special meaning, in the book. These will typically have
an icon next to their names, indicating the special meaning. For example, in
the picture to the left, you can see that the files :guilabel:`cover_image.jpg`
and :guilabel:`titlepage.xhtml` have the ocon of a cover next to them, this
indicates they are the book cover image and titlepage. Similarly, the
:guilabel:`content.opf` file has a metadata icon next to it, indicating the
book metadata is present in it and the the :guilabel:`toc.ncx` file has a T
icon next to it, indicating it is the Table of Contents.

You can perform many actions on individual files, by right clicking them.

Renaming files
^^^^^^^^^^^^^^^

You can rename an individual file by right clicking it and selecting
:guilabel:`Rename`. Renaming a file automatically updates all links and
references to it throughout the book. So all you have to do is provide the new
name, |app| will take care of the rest.

You can also bulk rename many files at once. This is useful
if you want the files to have some simple name pattern. For example you might
want to rename all the HTML files to have names Chapter-1.html, Chapter-2.html
and so on. Select the files you want bulk renamed by holding down the Shift or
Ctrl key and clicking the files. Then right click and select :guilabel:`Bulk
rename`. Enter a prefix and what number you would like the automatic numbering
to start at, click OK and you are done.

Merging files
^^^^^^^^^^^^^^

Sometimes, you may want to merge two HTML files or two CSS files together. It
can sometimes be useful to have everything in a single file. Be wary, though,
putting a lot of content into a single file will cause performance problems
when viewing the book in a typical ebook reader.

To merge multiple files together, select them by holding the Ctrl key and
clicking on them (make sure you only select files of one type, either all HTML
files or all CSS files and so on). Then right click and select merge. That's
all, |app| will merge the files, automatically taking care of migrating all
links and references to the merged files. Note that merging files can sometimes
cause text styling to change, since the individual files could have used
different stylesheets.

Changing text file order
^^^^^^^^^^^^^^^^^^^^^^^^^^

You can re-arrange the order in which text (HTML) files are opened when reading
the book by simply dragging and dropping them int he Files browser. For the
technically inclined, this is called re-ordering the book spine.

Marking the cover
^^^^^^^^^^^^^^^^^^^^^^^^^^^

E-books typically have a cover image. This image is indicated in the Files
Browser by the icon of a brow book next to the image name. If you want to
designate some other image as the cover, you can do so by right clicking on the
file and choosing :guilabel:`Mark as cover`.

In addition, EPUB files has the concept of a *titlepage*. A title page is a
HTML file that acts as the title page/cover for th book. You can mark an HTML
file as the titlepage when editing EPUBs by right-clicking. Be careful that the
file you mark contains only the cover information. If it contains other
content, such as the first chapter, then that content will be lost if the user
ever converts the EPUB file in |app| to another format. This is because when
converting, |app| assumes that the marked title page contains only the cover
and no other content.

Deleteing files
^^^^^^^^^^^^^^^^

You can delete files by either right clicking on them or by selecting them and
pressing the Delete key.
