.. _metadata:

Editing Ebook Metadata
========================

.. contents:: Contents
  :depth: 2
  :local:

Ebooks come in all shapes and sizes and more often than not, their metadata (things like title/author/series/publisher) is incomplete or incorrect.
The simplest way to change metadata in calibre is to simply double click on an entry and type in the correct replacement.
For more sophisticated, "power editing" use the edit metadata tools discussed below.

Editing the metadata of one book at a time
-------------------------------------------

Click the book you want to edit and then click the :guilabel:`Edit metadata` button or press the ``E`` key. A dialog opens that allows you to edit all aspects of the metadata. It has various features to make editing faster and more efficient. A list of the commonly used tips:

    * You can click the button in between title and authors to swap them automatically. 
    * You can click the button next to author sort to have calibre automatically fill it in using the sort values stored with each author. Use the :guilabel:`Manage authors` dialog to see and change the authors' sort values. This dialog can be opened by clicking and holding the button next to author sort.
    * You can click the button next to tags to use the Tag Editor to manage the tags associated with the book.
    * The "Ids" box can be used to enter an ISBN (and many other types of id), it will have a red background if you enter an invalid ISBN. It will be green for valid ISBNs.
    * The author sort box will be red if the author sort value differs from what calibre thinks it should be.

Downloading metadata
^^^^^^^^^^^^^^^^^^^^^

The nicest feature of the edit metadata dialog is its ability to automatically fill in many metadata fields by getting metadata from various websites. Currently, calibre uses isbndb.com, Google Books, Amazon and Library Thing. The metadata download can fill in Title, author, series, tags, rating, description and ISBN for you.

To use the download, fill in the title and author fields and click the :guilabel:`Fetch metadata` button. calibre will present you with a list of books that most closely match the title and author. If you fill in the ISBN field first, it will be used in preference to the title and author. If no matches are found, try making your search a little less specific by including only some key words in the title and only the author last name.

Managing book formats
^^^^^^^^^^^^^^^^^^^^^^^^

In calibre, a single book entry can have many different *formats* associated with it. For example you may have obtained the Complete Works of Shakespeare in EPUB format and later converted it to MOBI to read on your Kindle. calibre automatically manages multiple formats for you. In the :guilabel:`Available formats` section of the Edit metadata dialog, you can manage these formats. You can add a new format, delete an existing format and also ask calibre to set the metadata and cover for the book entry from the metadata in one of the formats.

All about covers
^^^^^^^^^^^^^^^^^^^^^

You can ask calibre to download book covers for you, provided the book has a known ISBN. Alternatively you can specify a file on your computer to use as the cover. calibre can even generate a default cover with basic metadata on it for you. You can drag and drop images onto the cover to change it and also right click to copy/paste cover images.

In addition, there is a button to automatically trim borders from the cover, in case your cover image has an ugly border.


Editing the metadata of many books at a time
---------------------------------------------

First select the books you want to edit by holding Ctrl or Shift and clicking on them. If you select more than one book, clicking the :guilabel:`Edit metadata` button will cause a new *Bulk* metadata edit dialog to open. Using this dialog, you can quickly set the author/publisher/rating/tags/series etc of a bunch of books to the same value. This is particularly useful if you have just imported a number of books that have some metadata in common. This dialog is very powerful, for example, it has a Search and Replace tab that you can use to perform bulk operations on metadata and even copy metadata from one column to another.

The normal edit metadata dialog also has :guilabel:`Next` and :guilabel:`Previous` buttons that you can use to edit the metadata of several books one after the other. 

Search and replace
^^^^^^^^^^^^^^^^^^^^

The :guilabel:`Bulk metadata edit` dialog allows you to perform arbitrarily powerful search and replace operations on the selected books. By default it uses a simple text search and replace, but it also support *regular expressions*. For more on regular expressions, see :ref:`regexptutorial`.

As noted above, there are two search and replace modes: character match and regular expression. Character match will look in the `Search field` you choose for the characters you type in the `search for` box and replace those characters with what you type in the `replace with` box. Each occurance of the search characters in the field will be replaced. For example, assume the field being searched contains `a bad cat`. If you search for `a` to be replaced with `HELLO`, then the result will be `HELLO bHELLOd cHELLOt`.

If the field you are searching on is a `multiple` field like tags, then each tag is treated separately. For example, if your tags contain `Horror, Scary`, the search expression `r,` will not match anything because the expression will first be applied to `Horror` and then to `Scary`.

If you want the search to ignore upper/lowercase differences, uncheck the `Case sensitive` box.

You can have calibre change the case of the result (information after the replace has happened) by choosing one of the functions from the `Apply function after replace` box. The operations available are:

    * `Lower case` -- change all the characters in the field to lower case
    * `Upper case` -- change all the characters in the field to upper case
    * `Title case` -- capitalize each word in the result.

The `Your test` box is provided for you to enter text to check that search/replace is doing what you want. In the majority of cases the book test boxes will be sufficient, but it is possible that there is a case you want to check that isn't shown in these boxes. Enter that case into `Your test`.

Regular expression mode has some differences from character mode, beyond (of course) using regular expressions. The first is that functions are applied to the parts of the string matched by the search string, not the entire field. The second is that functions apply to the replacement string, not to the entire field.

The third and most important is that the replace string can make reference to parts of the search string by using backreferences. A backreference is ``\\n`` where n is an integer that refers to the n'th parenthesized group in the search expression. For example, given the same example as above, `a bad cat`, a search expression `a (...) (...)`, and a replace expression `a \\2 \\1`, the result will be `a cat bad`. Please see the :ref:`regexptutorial` for more information on backreferences.

One useful pattern: assume you want to change the case of an entire field. The easiest way to do this is to use character mode, but lets further assume you want to use regular expression mode. The search expression should be `(.*)` the replace expression should be `\\1`, and the desired case change function should be selected.

Finally, in regular expression mode you can copy values from one field to another. Simply make the source and destination field different. The copy can replace the destination field, prepend to the field (add to the front), or append to the field (add at the end). The 'use comma' checkbox tells calibre to (or not to) add a comma between the text and the destination field in prepend and append modes. If the destination is multiple (e.g., tags), then you cannot uncheck this box.

Search and replace is done after all the other metadata changes in the other tabs are applied. This can lead to some confusion, because the test boxes will show the information before the other changes, but the operation will be applied after the other changes. If you have any doubts about what is going to happen, do not mix search/replace with other changes.

Bulk downloading of metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to download the metadata for multiple books at once, right-click the :guilabel:`Edit metadata` button and select :guilabel:`Download metadata`. You can choose to download only metadata, only covers, or both.


