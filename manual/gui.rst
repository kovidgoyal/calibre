.. include:: global.rst

.. _gui:

The Graphical User Interface
=============================

The Graphical User Interface *(GUI)* provides access to all
library management and ebook format conversion features. The basic workflow
for using |app| is to first add books to the library from your hard disk.
|app| will automatically try to read metadata from the books and add them
to its internal database. Once they are in the database, you can perform various
:ref:`actions` on them that include conversion from one format to another,
transfer to the reading device, viewing on your computer, and editing metadata.
The latter includes modifying the cover, description, and tags among other details.
Note that |app| creates copies of the files you add to it. Your original files are left untouched.

The interface is divided into various sections:

.. contents::
    :depth: 1
    :local:

.. _actions:

Actions
--------

.. image:: images/actions.png
    :alt: The Actions Toolbar
    :align: center

The actions toolbar provides convenient shortcuts to commonly used actions. If you right-click the buttons, you can perform variations on the default action.
Please note that the actions toolbar will look slightly different depending on whether you have an ebook reader attached to your computer.

.. contents::
    :depth: 1
    :local:

.. _add_books:

Add books
~~~~~~~~~~~~~~~~~~
.. |adbi| image:: images/add_books.png
    :class: float-right-img

|adbi| The :guilabel:`Add books` action has six variations accessed by doing a right-click on the button.


    1. **Add books from a single directory**: Opens a file chooser dialog and allows you to specify which books in a directory should be added. This action is *context sensitive*, i.e. it depends on which :ref:`catalog <catalogs>` you have selected. If you have selected the :guilabel:`Library`, books will be added to the library. If you have selected the ebook reader device, the books will be uploaded to the device, and so on.

    2. **Add books from directories, including sub-directories (One book per directory, assumes every ebook file is the same book in a different format)**: Allows you to choose a directory. The directory and all its sub-directories are scanned recursively, and any ebooks found are added to the library. |app| assumes that each directory contains a single book. All ebook files in a directory are assumed to be the same book in different formats. This action is the inverse of the :ref:`Save to disk <save_to_disk_multiple>` action, i.e. you can :guilabel:`Save to disk`, delete the books and re-add them with no lost information except for the date (this assumes you have not changed any of the setting for the Save to disk action).

    3. **Add books from directories, including sub-directories (Multiple books per directory, assumes every ebook file is a different book)**: Allows you to choose a directory. The directory and all its sub-directories are scanned recursively and any ebooks found are added to the library. |app| assumes that each directory contains many books. All ebook files with the same name in a directory are assumed to be the same book in different formats. Ebooks with different names are added as different books. 

    4. **Add empty book. (Book Entry with no formats)**: Allows you to create a blank book record. This can be used to then manually fill out the information about a book that you may not have yet in your collection.

    5. **Add from ISBN**: Allows you to add one or more books by entering their ISBNs.

    6. **Add files to selected book records**: Allows you to add or update the files associated with an existing book in your library.

The :guilabel:`Add books` action can read metadata from a wide variety of ebook formats. In addition, it tries to guess metadata from the filename.
See the :ref:`config_filename_metadata` section, to learn how to configure this.

To add an additional format for an existing book use the :ref:`edit_meta_information` action.

.. _edit_meta_information:

Edit metadata
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. |emii| image:: images/edit_meta_information.png
    :class: float-right-img

|emii| The :guilabel:`Edit metadata` action has four variations which can be accessed by doing a right-click on the button.

    1. **Edit metadata individually**: Allows you to edit the metadata of books one-by-one with the option of fetching metadata, including covers, from the Internet. It also allows you to add or remove particular ebook formats from a book.
    2. **Edit metadata in bulk**: Allows you to edit common metadata fields for large numbers of books simulataneously. It operates on all the books you have selected in the :ref:`Library view <search_sort>`.
    3. **Download metadata and covers**: Downloads metadata and covers (if available) for the books that are selected in the book list.
    4. **Merge book records**: Gives you the capability of merging the metadata and formats of two or more book records. You can choose to either delete or keep the records that were not clicked first.

For more details see :ref:`metadata`.

.. _convert_ebooks:

Convert books
~~~~~~~~~~~~~~~~~~~~~~
.. |cei| image:: images/convert_ebooks.png
    :class: float-right-img

|cei| Ebooks can be converted from a number of formats into whatever format your ebook reader prefers.
Many ebooks available for purchase will be protected by `Digital Rights Management <http://drmfree.calibre-ebook.com/about#drm>`_ *(DRM)* technology.
|app| will not convert these ebooks. It is easy to remove the DRM from many formats, but as this may be illegal,
you will have to find tools to liberate your books yourself and then use |app| to convert them.

For most people, conversion should be a simple one-click affair. If you want to learn more about the conversion process, see :ref:`conversion`.

The :guilabel:`Convert books` action has three variations, accessed by doing a right-click on the button.

    1. **Convert individually**: Allows you to specify conversion options to customize the conversion of each selected ebook.

    2. **Bulk convert**: Allows you to specify options only once to convert a number of ebooks in bulk.

    3. **Create a catalog of the books in your calibre library**: Allows you to generate a complete listing of the books in your library, including all metadata,
       in several formats such as XML, CSV, BiBTeX, EPUB and MOBI. The catalog will contain all the books currently showing in the library view.
       This allows you to use the search features to limit the books to be catalogued. In addition, if you select multiple books using the mouse,
       only those books will be added to the catalog. If you generate the catalog in an ebook format such as EPUB, MOBI or AZW3,
       the next time you connect your ebook reader the catalog will be automatically sent to the device.
       For more information on how catalogs work, read the :ref:`catalog_tut`.

.. _view:

View
~~~~~~~~~~~
.. |vi| image:: images/view.png
    :class: float-right-img

|vi| The :guilabel:`View` action displays the book in an ebook viewer program. |app| has a built-in viewer for many ebook formats.
For other formats it uses the default operating system application. You can configure which formats should open with the internal viewer via
Preferences->Behavior. If a book has more than one format, you can view a particular format by doing a right-click on the button.


.. _send_to_device:

Send to device
~~~~~~~~~~~~~~~~~~~~~~~~
.. |stdi| image:: images/send_to_device.png
    :class: float-right-img

|stdi| The :guilabel:`Send to device` action has eight variations, accessed by doing a right-click on the button.

    1. **Send to main memory**: The selected books are transferred to the main memory of the ebook reader.
    2. **Send to card (A)**: The selected books are transferred to the storage card (A) on the ebook reader.
    3. **Send to card (B)**: The selected books are transferred to the storage card (B) on the ebook reader.
    4. **Send specific format to**: The selected books are transferred to the selected storage location on the device, in the format that you specify.
    5. **Eject device**: Detaches the device from |app|.
    6. **Set default send to device action**: Allows you to specify which of the options, 1 through 5 above or 7 below, will be the default action when you click the main button.
    7. **Send and delete from library**: The selected books are transferred to the selected storage location on the device and then **deleted** from the Library.
    8. **Fetch Annotations (experimental)**: Transfers annotations you may have made on an ebook on your device to the comments metadata of the book in the |app| library.

You can control the file name and folder structure of files sent to the device by setting up a template in
:guilabel:`Preferences->Import/Export->Sending books to devices`. Also see :ref:`templatelangcalibre`.

.. _fetch_news:

Fetch news
~~~~~~~~~~~~~~~~~
.. |fni| image:: images/fetch_news.png
    :class: float-right-img

|fni| The :guilabel:`Fetch news` action downloads news from various websites and converts it into an ebook that can be read on your ebook reader. Normally, the newly created ebook is added to your ebook library, but if an ebook reader is connected at the time the download finishes, the news is also uploaded to the reader automatically.

The :guilabel:`Fetch news` action uses simple recipes (10-15 lines of code) for each news site. To learn how to create recipes for your own news sources, see :ref:`news`.

The :guilabel:`Fetch news` action has three variations, accessed by doing a right-click on the button.

    1. **Schedule news download**: Allows you to schedule the download of of your selected news sources from a list of hundreds available.  Scheduling can be set individually for each news source you select and the scheduling is flexible allowing you to select specific days of the week or a frequency of days between downloads.
    2. **Add a custom news source**: Allows you to create a simple recipe for downloading news from a custom news site that you wish to access.  Creating the recipe can be as simple as specifying an RSS news feed URL, or you can be more prescriptive by creating Python-based code for the task. For more information see :ref:`news`.
    3. **Download all scheduled news sources**: Causes |app| to immediately begin downloading all news sources that you have scheduled.


.. _library:

Library
~~~~~~~~~~~~~~~~~
.. |lii| image:: images/library.png
    :class: float-right-img

|lii| The :guilabel:`Library` action allows you to create, switch between, rename or remove a Library.  |app| allows you to create as many libraries as you wish. You could, for instance, create a fiction library, a non-fiction library, a foreign language library, a project library, or any structure that suits your needs. Libraries are the highest organizational structure within |app|. Each library has its own set of books, tags, categories and base storage location.

    1. **Switch/create library...**: Allows you to; a) connect to a pre-existing |app| library at another location, b) create an empty library at a new location or, c) move the current library to a newly specified location.
    2. **Quick switch**: Allows you to switch between libraries that have been registered or created within |app|.
    3. **Rename library**: Allows you to rename a Library.
    4. **Delete library**: Allows you to unregister a library from |app|.
    5. **<library name>**: Actions 5, 6 etc... give you immediate switch access between multiple libraries that you have created or attached to. This list contains only the 5 most frequently used libraries. For the complete list, use the Quick Switch menu.
    6. **Library maintenance**: Allows you to check the current library for data consistency issues and restore the current library's database from backups.

.. note:: Metadata about your ebooks, e.g. title, author, and tags, is stored in a single file in your |app| library folder called metadata.db. If this file gets corrupted (a very rare event), you can lose the metadata. Fortunately, |app| automatically backs up the metadata for every individual book in the book's folder as an OPF file. By using the Restore Library action under Library Maintenance described above, you can have |app| rebuild the metadata.db file from the individual OPF files for you.

You can copy or move books between different libraries (once you have more than one library setup) by right clicking on the book and selecting the action :guilabel:`Copy to library`.

.. _device:

Device
~~~~~~~~~~~~~~~~~
.. |dvi| image:: images/device.png
    :class: float-right-img

|dvi| The :guilabel:`Device` action allows you to view the books in the main memory or storage cards of your device, or to eject the device (detach it from |app|).
This icon shows up automatically on the main |app| toolbar when you connect a supported device. You can click on it to see the books on your device. You can also drag and drop books from your |app| library onto the icon to transfer them to your device. Conversely, you can drag and drop books from your device onto the library icon on the toolbar to transfer books from your device to the |app| library.


.. _save_to_disk:

Save to disk
~~~~~~~~~~~~~~~~~~~~~~~~~
.. |svdi| image:: images/save_to_disk.png
    :class: float-right-img

|svdi| The :guilabel:`Save to disk` action has five variations, accessed by doing a right-click on the button.

.. _save_to_disk_multiple:

    1. **Save to disk**: Saves the selected books to disk organized in directories. The directory structure looks like::

            Author_(sort)
                Title
                    Book Files

    You can control the file name and folder structure of files saved to disk by setting up a template in
    :guilabel:`Preferences->Import/Export->Saving books to disk`. Also see :ref:`templatelangcalibre`.

.. _save_to_disk_single:

    2. **Save to disk in a single directory**: Saves the selected books to disk in a single directory.

    For 1. and 2., all available formats, as well as metadata, are stored to disk for each selected book. Metadata is stored in an OPF file. Saved books can be re-imported to the library without any loss of information by using the :ref:`Add books <add_books>` action.

    3. **Save only *<your preferred>* format to disk**: Saves the selected books to disk in the directory structure as shown in (1.) but only in your preferred ebook format. You can set your preferred format in :guilabel:`Preferences->Behaviour->Preferred output format`

    4. **Save only *<your preferred>* format to disk in a single directory**: Saves the selected books to disk in a single directory but only in your preferred ebook format. You can set your preferred format in :guilabel:`Preferences->Behaviour->Preferred output format`

    5. **Save single format to disk...**: Saves the selected books to disk in the directory structure as shown in (1.) but only in the format you select from the pop-out list.

.. _connect_share:

Connect/Share
~~~~~~~~~~~~~~~~~
.. |csi| image:: images/connect_share.png
    :class: float-right-img

|csi| The :guilabel:`Connect/Share` action allows you to manually connect to a device or folder on your computer. It also allows you to set up you |app| library for access via a web browser or email.

    The :guilabel:`Connect/Share` action has four variations, accessed by doing a right-click on the button.

    1. **Connect to folder**: Allows you to connect to any folder on your computer as though it were a device and use all the facilities |app| has for devices with that folder. Useful if your device cannot be supported by |app| but is available as a USB disk.

    2. **Connect to iTunes**: Allows you to connect to your iTunes books database as though it were a device. Once the books are sent to iTunes, you can use iTunes to make them available to your various iDevices.

    3. **Start Content Server**: Starts |app|'s built-in web server.  When started, your |app| library will be accessible via a web browser from the Internet (if you choose). You can configure how the web server is accessed by setting preferences at :guilabel:`Preferences->Sharing->Sharing over the net`

    4. **Setup email based sharing of books**: Allows sharing of books and news feeds by email.  After setting up email addresses for this option, |app| will send news updates and book updates to the entered email addresses. You can configure how |app| sends email by setting preferences at :guilabel:`Preferences->Sharing->Sharing books by email`. Once you have set up one or more email addresses, this menu entry will be replaced by menu entries to send books to the configured email addresses.

.. _remove_books:

Remove books
~~~~~~~~~~~~~~~~~~~~~
.. |rbi| image:: images/remove_books.png
    :class: float-right-img

|rbi| The :guilabel:`Remove books` action **deletes books permanently**, so use it with care. It is *context sensitive*, i.e. it depends on which :ref:`catalog <catalogs>` you have selected. If you have selected the :guilabel:`Library`, books will be removed from the library. If you have selected the ebook reader device, books will be removed from the device. To remove only a particular format for a given book use the :ref:`edit_meta_information` action.  Remove books also has five variations which can be accessed by doing a right-click on the button.

    1. **Remove selected books**: Allows you to **permanently** remove all books that are selected in the book list.

    2. **Remove files of a specific format from selected books...**: Allows you to **permanently** remove ebook files of a specified format from books that are selected in the book list.

    3. **Remove all formats from selected books, except...**: Allows you to **permanently** remove ebook files of any format except a specified format from books that are selected in the book list.

    3. **Remove all formats from selected books**: Allows you to **permanently** remove all ebook files from books that are selected in the book list. Only the metadata will remain.

    4. **Remove covers from selected books**: Allows you to **permanently** remove cover image files from books that are selected in the book list.

    5. **Remove matching books from device**: Allows you to remove ebook files from a connected device that match the books that are selected in the book list.

.. note::
    Note that when you use Remove books to delete books from your |app| library, the book record is permanently deleted, but on Windows and OS X the files are placed into the recycle bin. This allows you to recover them if you change your mind.

.. _configuration:

Preferences
---------------
.. |cbi| image:: images/preferences.png
    :class: float-right-img

|cbi| The :guilabel:`Preferences` action allows you to change the way various aspects of |app| work. It has four variations, accessed by doing a right-click on the button.

    1. **Preferences**: Allows you to change the way various aspects of |app| work. Clicking the button also performs this action.
    2. **Run welcome wizard**: Allows you to start the Welcome Wizard which appeared the first time you started |app|.
    3. **Get plugins to enhance |app|**: Opens a new windows that shows plugins for |app|. These plugins are developed by third parties to extend |app|'s functionality.
    4. **Restart in debug mode**: Allows you to enable a debugging mode that can assist the |app| developers in solving problems you encounter with the program. For most users this should remain disabled unless instructed by a developer to enable it.

.. _catalogs:

Catalogs
----------
.. image:: images/catalogs.png
    :align: center

A *catalog* is a collection of books. |app| can manage two types of different catalogs:

    1. **Library**: This is a collection of books stored in your |app| library on your computer.

    2. **Device**:  This is a collection of books stored in your ebook reader. It will be available when you connect the reader to your computer.

Many operations, such as adding books, deleting, viewing, etc., are context sensitive. So, for example, if you click the View button when you have the **Device** catalog selected, |app| will open the files on the device to view. If you have the **Library** catalog selected, files in your |app| library will be opened instead.

.. _search_sort:

Search & Sort
---------------
.. image:: images/search_sort.png
    :align: center

The Search & Sort section allows you to perform several powerful actions on your book collections.

    * You can sort them by title, author, date, rating, etc. by clicking on the column titles. You can also sub-sort, i.e. sort on multiple columns. For example, if you click on the title column and then the author column, the book will be sorted by author and then all the entries for the same author will be sorted by title.

    * You can search for a particular book or set of books using the search bar. More on that below.

    * You can quickly and conveniently edit metadata by double-clicking the entry you want changed in the list.

    * You can perform :ref:`actions` on sets to books. To select multiple books you can either:

        - Keep the :kbd:`Ctrl` key pressed and click on the books you want selected.

        - Keep the :kbd:`Shift` key pressed and click on the starting and ending book of a range of books you want selected.

    * You can configure which fields you want displayed by using the :ref:`configuration` dialog.

.. _search_interface:

The Search Interface
---------------------
You can search all the metadata by entering search terms in the search bar. Searches are case insensitive. For example::

    Asimov Foundation format:lrf

This will match all books in your library that have ``Asimov`` and ``Foundation`` in their metadata and
are available in the LRF format. Some more examples::

    author:Asimov and not series:Foundation
    title:"The Ring" or "This book is about a ring"
    format:epub publisher:feedbooks.com

Searches are by default 'contains'. An item matches if the search string appears anywhere in the indicated metadata.
Two other kinds of searches are available: equality search and search using `regular expressions <http://en.wikipedia.org/wiki/Regular_expression>`_.

Equality searches are indicated by prefixing the search string with an equals sign (=). For example, the query
``tag:"=science"`` will match "science", but not "science fiction" or "hard science". Regular expression searches are
indicated by prefixing the search string with a tilde (~). Any `python-compatible regular expression <http://docs.python.org/library/re.html>`_ can
be used. Note that backslashes used to escape special characters in reqular expressions must be doubled because single backslashes will be removed during query parsing. For example, to match a literal parenthesis you must enter ``\\(``. Regular expression searches are 'contains' searches unless the expression contains anchors.

Should you need to search for a string with a leading equals or tilde, prefix the string with a backslash.

Enclose search strings with quotes (") if the string contains parenthesis or spaces. For example, to search
for the tag ``Science Fiction`` you would need to search for ``tag:"=science fiction"``. If you search for
``tag:=science fiction`` you will find all books with the tag 'science' and containing the word 'fiction' in any
metadata.

You can build advanced search queries easily using the :guilabel:`Advanced Search Dialog` accessed by
clicking the button |sbi|.

Available fields for searching are: ``tag, title, author, publisher, series, series_index, rating, cover,
comments, format, identifiers, date, pubdate, search, size`` and custom columns. If a device is plugged in, the ``ondevice`` field becomes available, when searching the calibre library view. To find the search name (actually called the `lookup name`) for a custom column, hover your mouse over the column header in the library view.

The syntax for searching for dates is::

    pubdate:>2000-1 Will find all books published after Jan, 2000
    date:<=2000-1-3 Will find all books added to calibre before 3 Jan, 2000
    pubdate:=2009 Will find all books published in 2009

If the date is ambiguous, the current locale is used for date comparison. For example, in an mm/dd/yyyy
locale 2/1/2009 is interpreted as 1 Feb 2009. In a dd/mm/yyyy locale it is interpreted as 2 Jan 2009.  Some
special date strings are available. The string ``today`` translates to today's date, whatever it is. The
strings ``yesterday`` and ``thismonth`` (or the translated equivalent in the current language) also work.
In addition, the string ``daysago`` (also translated) can be used to compare to a date some number of days ago.
For example::

    date:>10daysago
    date:<=45daysago

You can search for books that have a format of a certain size like this::

    size:>1.1M Will find books with a format larger than 1.1MB
    size:<=1K  Will find books with a format smaller than 1KB

Dates and numeric fields support the relational operators ``=`` (equals), ``>`` (greater than), ``>=``
(greater than or equal to), ``<`` (less than), ``<=`` (less than or equal to), and ``!=`` (not equal to).
Rating fields are considered to be numeric. For example, the search ``rating:>=3`` will find all books rated 3
or higher.

You can search for the number of items in multiple-valued fields such as tags. These searches begin with the character ``#``, then use the same syntax as numeric fields. For example, to find all books with more than 4 tags use ``tags:#>4``. To find all books with exactly 10 tags use ``tags:#=10``.

Series indices are searchable. For the standard series, the search name is 'series_index'. For
custom series columns, use the column search name followed by _index. For example, to search the indices for a
custom series column named ``#my_series``, you would use the search name ``#my_series_index``.
Series indices are numbers, so you can use the relational operators described above.

The special field ``search`` is used for saved searches. So if you save a search with the name
"My spouse's books" you can enter ``search:"My spouse's books"`` in the search bar to reuse the saved
search. More about saving searches below.

You can search for the absence or presence of a field using the special "true" and "false" values. For example::

    cover:false will give you all books without a cover
    series:true will give you all books that belong to a series
    comments:false will give you all books with an empty comment
    format:false will give you all books with no actual files (empty records)

Yes/no custom columns are searchable. Searching for ``false``, ``empty``, or ``blank`` will find all books
with undefined values in the column. Searching for ``true`` will find all books that do not have undefined
values in the column. Searching for ``yes`` or ``checked`` will find all books with ``Yes`` in the column.
Searching for ``no`` or ``unchecked`` will find all books with ``No`` in the column. Note that the words ``yes``, ``no``, ``blank``, ``empty``, ``checked`` and ``unchecked`` are translated; you must use the current language's equivalent word. The words ``true`` and ``false`` and the special values ``_yes`` and ``_no`` are not translated.

Hierarchical items (e.g. A.B.C) use an extended syntax to match initial parts of the hierarchy. This is done by adding a period between the exact match indicator (=) and the text. For example, the query ``tags:=.A`` will find the tags `A` and `A.B`, but will not find the tags `AA` or `AA.B`. The query ``tags:=.A.B`` will find the tags `A.B` and `A.B.C`, but not the tag `A`.

Identifiers (e.g., isbn, doi, lccn etc) also use an extended syntax. First, note that an identifier has the form ``type:value``, as in ``isbn:123456789``. The extended syntax permits you to specify independently which type and value to search for. Both the type and the value parts of the query can use `equality`, `contains`, or `regular expression` matches. Examples:

    * ``identifiers:true`` will find books with any identifier.
    * ``identifiers:false`` will find books with no identifier.
    * ``identifiers:123`` will search for books with any type having a value containing `123`.
    * ``identifiers:=123456789`` will search for books with any type having a value equal to `123456789`.
    * ``identifiers:=isbn:`` and ``identifiers:isbn:true`` will find books with a type equal to isbn having any value
    * ``identifiers:=isbn:false`` will find books with no type equal to isbn.
    * ``identifiers:=isbn:123`` will find books with a type equal to isbn having a value containing `123`.
    * ``identifiers:=isbn:=123456789`` will find books with a type equal to isbn having a value equal to `123456789`.
    * ``identifiers:i:1`` will find books with a type containing an `i` having a value containing a `1`.


.. |sbi| image:: images/search_button.png
    :align: middle

.. figure:: images/search.png
    :align: center

    :guilabel:`Advanced Search Dialog`

Saving searches
-----------------

|app| allows you to save a frequently used search under a special name and then reuse that search with a single click. To do this, create your search either by typing it in the search bar or using the Tag Browser. Then type the name you would like to give to the search in the Saved Searches box next to the search bar. Click the plus icon next to the saved searches box to save the search.

Now you can access your saved search in the Tag Browser under "Searches". A single click will allow you to reuse any arbitrarily complex search easily, without needing to re-create it.

.. _config_filename_metadata:

Guessing metadata from file names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In the :guilabel:`Add/Save` section of the configuration dialog, you can specify a regular expression that |app| will use to try and guess metadata from the names of ebook files
that you add to the library. The default regular expression is::

    title - author

i.e., it assumes that all characters up to the first ``-`` are the title of the book and subsequent characters are the author of the book. For example, the filename::

    Foundation and Earth - Isaac Asimov.txt

will be interpreted to have the title: Foundation and Earth and author: Isaac Asimov

.. tip::
    If the filename does not contain the hyphen, the regular expression will fail.

.. _book_details:

Book Details
-------------
.. image:: images/book_details.png
    :align: center

The Book Details display shows extra information and the cover for the currently selected book.

.. _jobs:

.. _tag_browser:

Tag Browser
-------------
.. image:: images/tag_browser.png
   :class: float-left-img

The Tag Browser allows you to easily browse your collection by Author/Tags/Series/etc. If you click on any item in the Tag Browser, for example the author name Isaac Asimov, then the list of books to the right is restricted to showing books by that author. You can click on category names as well. For example, clicking on "Series" will show you all books in any series.

The first click on an item will restrict the list of books to those that contain or match the item. Continuing the above example, clicking on Isaac Asimov will show books by that author. Clicking again on the item will change what is shown, depending on whether the item has children (see sub-categories and hierarchical items below). Continuing the Isaac Asimov example, clicking again on Isaac Asimov will restrict the list of books to those not by Isaac Asimov. A third click will remove the restriction, showing all books. If you hold down the Ctrl or Shift keys and click on multiple items, then restrictions based on multiple items are created. For example you could hold Ctrl and click on the tags History and Europe for finding books on European history. The Tag Browser works by constructing search expressions that are automatically entered into the Search bar. Looking at what the Tag Browser generates is a good way to learn how to construct basic search expressions.

Items in the Tag browser have their icons partially colored. The amount of color depends on the average rating of the books in that category. So for example if the books by Isaac Asimov have an average of four stars, the icon for Isaac Asimov in the Tag Browser will be 4/5th colored. You can hover your mouse over the icon to see the average rating.

The outer-level items in the tag browser, such as Authors and Series, are called categories. You can create your own categories, called User Categories, which are useful for organizing items. For example, you can use the User Categories Editor (click the Manage User Categories button) to create a user category called Favorite Authors, then put the items for your favorites into the category. User categories can have sub-categories. For example, the user category Favorites.Authors is a sub-category of Favorites. You might also have Favorites.Series, in which case there will be two sub-categories under Favorites. Sub-categories can be created by right-clicking on a user category, choosing "Add sub-category to ...", and entering the sub-category name; or by using the User Categories Editor by entering names like the Favorites example above.

You can search user categories in the same way as built-in categories, by clicking on them. There are four different searches cycled through by clicking:
    1. "everything matching an item in the category" indicated by a single green plus sign.
    2. "everything matching an item in the category or its sub-categories" indicated by two green plus signs.
    3. "everything not matching an item in the category" shown by a single red minus sign.
    4. "everything not matching an item in the category or its sub-categories" shown by two red minus signs.

It is also possible to create hierarchies inside some of the text categories such as tags, series, and custom columns. These hierarchies show with the small triangle, permitting the sub-items to be hidden. To use hierarchies of items in a category, you must first go to Preferences->Look & Feel and enter the category name(s) into the "Categories with hierarchical items" box. Once this is done, items in that category that contain periods will be shown using the small triangle. For example, assume you create a custom column called "Genre" and indicate that it contains hierarchical items. Once done, items such as Mystery.Thriller and Mystery.English will display as Mystery with the small triangle next to it. Clicking on the triangle will show Thriller and English as sub-items. See :ref:`Managing subgroups of books, for example "genre" <subgroups-tutorial>` for more information.

Hierarchical items (items with children) use the same four 'click-on' searches as user categories. Items that do not have children use two of the searches: "everything matching" and "everything not matching".

You can drag and drop items in the Tag browser onto user categories to add them to that category. If the source is a user category, holding the shift key while dragging will move the item to the new category. You can also drag and drop books from the book list onto items in the Tag Browser; dropping a book on an item causes that item to be automatically applied to the dropped books. For example, dragging a book onto Isaac Asimov will set the author of that book to Isaac Asimov. Dropping it onto the tag History will add the tag History to the book's tags.

There is a search bar at the top of the Tag Browser that allows you to easily find any item in the Tag Browser. In addition, you can right click on any item and choose one of several operations. Some examples are to hide the it, rename it, or open a "Manage x" dialog that allows you to manage items of that kind. For example, the "Manage Authors" dialog allows you to rename authors and control how their names are sorted.

You can control how items are sorted in the Tag browser via the box at the bottom of the Tag Browser. You can choose to sort by name, average rating or popularity (popularity is the number of books with an item in your library; for example, the popularity of Isaac Asimov is the number of books in your library by Isaac Asimov).

Jobs
-----
.. image:: images/jobs.png
    :class: float-left-img

The Jobs panel shows the number of currently running jobs. Jobs are tasks that run in a separate process. They include converting ebooks and talking to your reader device. You can click on the jobs panel to access the list of jobs. Once a job has completed you can see a detailed log from that job by double-clicking it in the list. This is useful to debug jobs that may not have completed successfully.

Keyboard Shortcuts
---------------------

Calibre has several keyboard shortcuts to save you time and mouse movement. These shortcuts are active in the book list view (when you're not editing the details of a particular book), and most of them affect the title you have selected. The |app| ebook viewer has its own shortcuts which can be customised by clicking the Preferences button in the viewer.

.. note::

    Note: The Calibre keyboard shortcuts do not require a modifier key (Command, Option, Control, etc.), unless specifically noted. You only need to press the letter key, e.g. E to edit.

.. list-table:: Keyboard Shortcuts
    :widths: 10 100
    :header-rows: 1

    * - Keyboard Shortcut
      - Action
    * - :kbd:`F2 (Enter in OS X)`
      - Edit the metadata of the currently selected field in the book list.
    * - :kbd:`A`
      - Add Books
    * - :kbd:`Shift+A`
      - Add Formats to the selected books
    * - :kbd:`C`
      - Convert selected Books
    * - :kbd:`D`
      - Send to device
    * - :kbd:`Del`
      - Remove selected Books
    * - :kbd:`E`
      - Edit metadata of selected books
    * - :kbd:`G`
      - Get Books
    * - :kbd:`I`
      - Show book details
    * - :kbd:`M`
      - Merge selected records
    * - :kbd:`Alt+M`
      - Merge selected records, keeping originals
    * - :kbd:`O`
      - Open containing folder
    * - :kbd:`P`
      - Polish books
    * - :kbd:`S`
      - Save to Disk
    * - :kbd:`V`
      - View
    * - :kbd:`Alt+V/Cmd+V in OS X`
      - View specific format
    * - :kbd:`Alt+Shift+J`
      - Toggle jobs list
    * - :kbd:`Alt+Shift+B`
      - Toggle Cover Browser
    * - :kbd:`Alt+Shift+D`
      - Toggle Book Details panel
    * - :kbd:`Alt+Shift+T`
      - Toggle Tag Browser
    * - :kbd:`Alt+A`
      - Show books by the same author as the current book
    * - :kbd:`Alt+T`
      - Show books with the same tags as current book
    * - :kbd:`Alt+P`
      - Show books by the same publisher as current book
    * - :kbd:`Alt+Shift+S`
      - Show books in the same series as current book
    * - :kbd:`/, Ctrl+F`
      - Focus the search bar
    * - :kbd:`Shift+Ctrl+F`
      - Open the advanced search dialog
    * - :kbd:`Esc`
      - Clear the current search
    * - :kbd:`N or F3`
      - Find the next book that matches the current search (only works if the highlight checkbox next to the search bar is checked)
    * - :kbd:`Shift+N or Shift+F3`
      - Find the next book that matches the current search (only works if the highlight checkbox next to the search bar is checked)
    * - :kbd:`Ctrl+D`
      - Download metadata and shortcuts
    * - :kbd:`Ctrl+R`
      - Restart calibre
    * - :kbd:`Ctrl+Shift+R`
      - Restart calibre in debug mode
    * - :kbd:`Shift+Ctrl+E`
      - Add empty books to calibre
    * - :kbd:`Ctrl+Q`
      - Quit calibre








