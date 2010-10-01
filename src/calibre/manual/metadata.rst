.. include:: global.rst

.. _metadata:

Editing E-book Metadata
========================

E-books come in all shapes and sizes and more often than not, their metadata (things like title/author/series/publisher) is incomplete or incorrect. 
The simplest way to change metadata in |app| is to simply double click on an entry and type in the correct replacement.
For more sophisticated, "power editing" use the edit metadata tools discussed below.

Editing the metadata of one book at a time
-------------------------------------------

Click the book you want to edit and then click the :guilabel:`Edit metadata` button or press the ``E`` key. A dialog opens that allows you to edit all aspects of the metadata. It has various features to make editing faster and more efficient. A list of the commonly used tips:

    * You can click the button in between title and authors to swap them automatically. Or 
    * You can click the button next to author sort to automatically to have |app| automatically fill it from the author name.
    * You can click the button next to tags to use the Tag Editor to manage the tags associated with the book.
    * The ISBN box will have a red background if you enter an invalid ISBN. It will be green for valid ISBNs
    * The author sort box will be red if the author sort value differs from what |app| thinks it should be.

Downloading metadata
^^^^^^^^^^^^^^^^^^^^^

The nicest feature of the edit metadata dialog is its ability to automatically fill in many metadata fields by getting metadata from various websites. Currently, |app| uses isbndb.com, Google Books, Amazon and Library Thing. The metadata download can fill in Title, author, series, tags, rating, description and ISBN for you. 

To use the download, fill in the title and author fields and click the :guilabel:`Fetch metadata` button. |app| will present you with a list of books that most closely match the title and author. If you fill in the ISBN field first, it will be used in preference to the title and author. If no matches are found, try making your search a little less specific by including only some key words in the title and only the author last name. 

Managing book formats
^^^^^^^^^^^^^^^^^^^^^^^^

In |app|, a single book entry can have many different *formats* associated with it. For example you may have obtained the Complete Works of Shakespeare in EPUB format and later converted it to MOBI to read on your Kindle. |app| automatically manages multiple formats for you. In the :guilabel:`Available formats` section of the Edit metadata dialog, you can manage these formats. You can add a new format, delete an existing format and also ask |app| to set the metadata and cover for the book entry from the metadata in one of the formats.

All about covers
^^^^^^^^^^^^^^^^^^^^^

You can ask |app| to download book covers for you, provided the book has a known ISBN. Alternatively you can specify a file on your computer to use as the cover. |app| can even generate a default cover with basic metadata on it for you. You can drag and drop images onto the cover to change it and also right click to copy/paste cover images.

In addition, there is a button to automatically trim borders from the cover, in case your cover image has an ugly border.


Editing the metadata of many books at a time
---------------------------------------------

First select the books you want to edit by holding Ctrl or Shift and clicking on them. If you select more than one book, clicking the :guilabel:`Edit metadata` button will cause a new *Bulk* metadata edit dialog to open. Using this dialog, you can quickly set the author/publisher/rating/tags/series etc of a bunch of books to the same value. This is particularly useful if you have just imported a number of books that have some metadata in common. You can also click the arrow next to the :guilabel:`Edit metadata` button and select :guilabel:`Edit metadata individually` to use the powerful single book edit dialog from above for all the selected books in succession.

Search and replace
^^^^^^^^^^^^^^^^^^^^

The Bulk metadata edit dialog allows you to perform arbitrarily powerful search and replace operations on the selected books. By default it uses a simple text search and replace, but it also support *regular expressions*. For more on regular expressions, see :ref:`regexptutorial`.

Bulk downloading of metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to download the metadata for multiple books at once, click the arrow next to the :guilabel:`Edit metadata` button and select :guilabel:`Download metadata and covers`. You can choose to download only metadata, only covers, both or only social metadata (tags/rating/series). 


