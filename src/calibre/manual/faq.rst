.. include:: global.rst

.. _faq:

Frequently Asked Questions
==========================

.. contents:: Contents
  :depth: 1
  :local: 

E-book Format Conversion
-------------------------
.. contents:: Contents
  :depth: 1
  :local:

What formats does |app| support conversion to/from?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| supports the conversion of the following formats to LRF: HTML, LIT, MOBI, PRC, EPUB, RTF, TXT, PDF and LRS. It also supports the conversion of LRF to LRS and HTML. Note that calibre does not support the conversion of DRMed ebooks.

What are the best formats to convert to LRF?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In order of decreasing preference: LIT, MOBI, HTML, PRC, RTF, TXT, PDF 

Why does the PDF conversion lose some images?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The PDF conversion tries to extract the text and images from the PDF file and convert them to and HTML based ebook. Some PDF files have images in a format that cannot be extracted (vector images).

There are no images in the LRF file after conversion from HTML?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you use the GUI to convert an HTML file, you have to create a zip file with the HTML file and any images it references and then convert that ZIP file to LRF.

How do I convert my file containing non-English characters?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There are two aspects to this problem: 
  1. Knowing the encoding of the source file: |app| tries to guess what character encoding your source files use, but often, this is impossible, so you need to tell it what encoding to use. This can be done in the GUI via the :guilabel:`Source encoding` field in the :guilabel:`Look & Feel` section. The command-line tools all have an :option:`--encoding` option. 
  2. Embedding fonts: If you are generating an LRF file to read on your SONY Reader, you are limited by the fact that the Reader only supports a few non-English characters in the fonts it comes pre-loaded with. You can work around this problem by embedding a unicode-aware font that supports the character set your file uses into the LRF file. You should embed atleast a serif and a sans-serif font. Be aware that embedding fonts significantly slows down page-turn speed on the reader. 


How do I use some of the advanced features of the conversion tools?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 You can get help on any individual feature of the converters by mousing over it in the GUI or running ``html2lrf --help`` at a terminal. A good place to start is to look at the following demo files that demonstrate some of the advanced features: 
  * `html-demo.zip <http://calibre.kovidgoyal.net/downloads/html-demo.zip>`_ 
  * `txt-demo.zip <http://calibre.kovidgoyal.net/downloads/txt-demo.zip>`_


Device Integration
-------------------

.. contents:: Contents
  :depth: 1
  :local:

What devices does |app| support?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
At the moment |app| has full support for the SONY PRS500 and PRS505. However, using the :guilabel:`Save to disk` function you can use it with any ebook reader that exports itself as a USB disk.

I used |app| to transfer some books to my reader, and now the SONY software hangs every time I connect the reader?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You should not use both |app| and Connect to transfer books to the reader. You can fix this problem by: 
  * Removing any storage cards from your reader. 
  * Deleting the file media.xml from the reader's main memory using windows explorer (search for the file to find all locations where it is present). Note that by doing this you will lose all your collections, bookmarks, history etc. 
  * Unplugging the reader and waiting till the list of books shows up again 
  * Re-connecting the reader and starting the SONY software

Library Management
------------------

.. contents:: Contents
  :depth: 1
  :local:

What formats does |app| read metadata from?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| reads metadata from the following formats: LRF, PDF, LIT, RTF, OPF, MOBI, PRC, EPUB. In addition it can write metadata to: LRF, RTF, OPF

Where are the book files stored?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
When you import books into the library, they are stored in a database. The database location can be found out by clicking the configuration button (The button with the icon of a hammer next to the search bar). 

Can I save my books to the disk?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You can save your books to the disk by selecting the books and clicking the "Save to disk" button. Your books will be saved in nicely organized folders.

Content From The Web
---------------------
.. contents:: Contents
  :depth: 1
  :local:

I obtained a recipe for a news site as a .py file from somewhere, how do I use it?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Start the :guilabel:`Add custom news sources` dialog (from the :guilabel:`Fetch news` menu) and click the :guilabel:`Switch to advanced mode` button. Delete everything in the box with the recipe source code and copy paste the contents of your .py file into the box. Click :guilabel:`Add/update recipe`.


I want |app| to download news from my favorite news website.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you are reasonably proficient with computers, you can teach |app| to download news from any website of your choosing. To learn how to do this see :ref:`news`.

Otherwise, you can register a request for a particular news site by adding a comment `here <http://calibre.kovidgoyal.net/ticket/405>`_.

Can I use web2lrf to download an arbitrary website?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``web2lrf --url http://mywebsite.com default``

Miscellaneous
--------------

.. contents:: Contents
  :depth: 1
  :local:

Why does |app| show only some of my fonts on OS X?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| embeds fonts in ebook files it creates. E-book files support embedding only TrueType (.ttf) fonts. Most fonts on OS X systems are in .dfont format, thus they cannot be embedded. |app| shows only TrueType fonts founf on your system. You can obtain many TrueType fonts on the web. Simply download the .ttf files and add them to the Library/Fonts directory in your home directory. 

The graphical user interface of |app| is not starting on Windows?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you've never used the graphical user interface before, try deleting the file library1.db (it will be somewhere under :file:`C:\\Documents and Settings` on Windows XP and :file:`C:\\Users` on Windows Vista. If that doesn't fix the problem, locate the file calibre.log (in the same places as library1.db) and post its contents in a help message on the `Forums <http://calibre.kovidgoyal.net/discussion>`_.

I want some feature added to |app|. What can I do?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You have two choices: 
 1. Create a patch by hacking on |app| and send it to me for review and inclusion. See `Development <http://calibre.kovidgoyal.net/wiki/Development>`_. 
 2. `Open a ticket <http://calibre.kovidgoyal.net/newticket>`_ (you have to register and login first) and hopefully I will find the time to implement your feature.
