
.. include:: global.rst

.. _subgroups-tutorial:

Managing subgroups of books, for example "genre"
==================================================

Some people wish to organize the books in their library into subgroups, similar to subfolders. The most common wish is to create genre hierarchies, but there are many others. One user asked for a way to organize textbooks by subject and course number. Another wanted to keep track of gifts by subject and recipient. I will use the genre example for the rest of this post.

Before I go on, please note that I am not talking about folders on the hard disk. Subgroups are not file folders. Books will not be copied anywhere. Calibre's library file structure is not affected. Instead, I am talking about a way to display subgroups of books within a calibre library.

.. contents::
    :depth: 1
    :local:

.. |sgtree| image:: images/sg_tree.jpg
    :class: float-left-img


The commonly expressed requirements for subgroups such as genres are:

    * A subgroup (e.g., a genre) must contain (point to) books, not categories of books. This is what distinguishes subgroups from user categories.
    * A book can be in multiple subgroups (genres). This distinguishes subgroups from physical file folders.
    * Subgroups (genres) must form a hierarchy; subgroups can contain subgroups.

|sgtree| Tags give you the first two. If you tag a book with the genre then you can use the tag browser (or search) for find the books with that genre, giving you the first. Many books can have the same tag, giving you the second. The problem is that tags don't satisfy the third requirement. They don't provide a hierarchy.

Calibre's new hierarchy feature gives you the third, the ability to see the genres in a 'tree' and the ability to easily search for books in genre or sub-genre. For example, assume that your genre structure is similar to the following::

    Genre
        . History
        .. Japanese
        .. Military
        .. Roman
        . Mysteries
        .. English
        .. Vampire
        . Science Fiction
        .. Alternate History
        .. Military
        .. Space Opera
        . Thrillers
        .. Crime
        .. Horror
        etc.

By using the hierarchy feature, you can see these genres in the tag browser in a tree form. As you can see, in this example the outermost level (Genre) is a custom column. The genres themselves appear under that column. Genres containing sub-genres appear with a small triangle next to them. Clicking on that triangle will open the item and show the sub-genres, as you see with History and Science Fiction.

Clicking on a genre will search for all books with that genre or children of that genre. For example, clicking on Science Fiction will give all three of the child genres, Alternate History, Military, and Space Opera. Clicking on Alternate History will give books in that genre, ignoring those in Military and Space Opera. Of course, a book can have multiple genres. If a book has both Space Opera and Military genres, then you see that book if you click on either genre. Searching is discussed in more detail below.

Another thing you can see from the image is that the genre Military appears twice, once under History and once under Science Fiction. Because the genres are in a hierarchy, these are two separate genres. A book can be in one, the other, or (doubtfully in this case) both. For example, Winston Churchill's World War II books could be in "History.Military". David Weber's Honor Harrington books could be in "Science Fiction.Military", and in "Science Fiction.Space Opera" for that matter.

Once a genre exists, that is the genre has been applied to at least one book, you can easily apply it to other books by dragging a book from the library view onto the genre you want the book to have. You can also apply them in the metadata editors. More on this below.

Setup
----------------------------------------


Your question by now might be "how did I set all of this up?". There are three steps: 1) create the custom column, 2) tell calibre that the new column is to be treated as a hierarchy, and 3) add genres.

I created the custom column in the usual way, using Preferences -> Add your own columns. I used "genre" as the lookup name and "Genre" as the column heading. The column type is "Comma-separated text, like tags, shown in the tag browser." 

.. image:: images/sg_cc.jpg
    :align: center

Then after restarting calibre, I told calibre that the column is to be treated as a hierarchy. I went to Preferences -> Look and Feel and entered the lookup name "#genre" into the "Categories with hierarchical items" box. I pressed Apply and was done with setting up.

.. image:: images/sg_pref.jpg
    :align: center

At the point there are no genres. We are left with the last step: how to apply a genre to a book. A genre does not exist until it appears on at least one book. To apply a genre for the first time, we must go into some detail about what a genre looks like in the metadata for a book.

A hierarchy of 'things' is built by creating an item consisting of phrases separated by periods. Continuing the Genre example, these items would "History.Military", "Mysteries.Vampire", "Science Fiction.Space Opera", etc. Thus to create a new genre, you pick a book that should have that genre, edit its metadata, and enter the new genre into the column you created. Continuing my example, if I want to assign a new genre "Comics" with a sub-genre "Superheros" to a book, I would 'edit metadata' for that (comic) book, choose the Custom metadata tab, and then enter "Comics.Superheros" as shown in the following (ignore my other custom columns):

.. image:: images/sg_genre.jpg
    :align: center

After I do the above, I see in the tag browser:

.. image:: images/sg_tb.jpg
    :align: center

From here on, to apply this new genre to a book (a comic book, presumably), I can either drag the book onto the genre, or add it to the book using edit metadata in exactly the same way as I did above.

Searching
---------------

.. image:: images/sg_search.jpg
    :align: center

The easiest way to search for genres is to use the tag browser, clicking on the genre you want to see. Clicking on a genre with children will show you books with that genre and all child genres. However, this might bring up a question. Just because a genre has children doesn't mean that it isn't a genre in its own right. For example, a book can have the genre "History" but not "History.Military". How do I search for books with only "History"?

The tag browser search mechanism knows if an item has children. If it does, clicking on the item cycles through 5 searches instead of the normal three. The first is the normal green plus, which shows you books with that genre only. The second is new: a doubled plus (shown below), which shows you books with that genre and all sub-genres. The third is the normal red minus, which shows you books without that exact genre. The fourth is new: a doubled minus, which shows you books without that genre or sub-genres. The fifth is back to the beginning, no mark, meaning no search.

Restrictions
---------------

If you search for a genre then create a saved search, you can use the 'restrict to' box to create a virtual library of books with that genre. This is most useful if you want to do other searches within the genre or to manage/update metadata. For this example I created a saved search named 'History.Japanese' by first clicking on the genre Japanese in the tag browser to get a search into the search box, entering History.Japanese into the saved search box, then pushing the "save search" button (the green box with the white plus, on the right-hand side).

.. image:: images/sg_restrict.jpg
    :align: center

Once I have done that, then I can use this search as a restriction.

.. image:: images/sg_restrict2.jpg
    :align: center

