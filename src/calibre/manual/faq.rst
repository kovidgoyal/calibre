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
|app| supports the conversion of the following formats:

+----------------------------+------------------------------------------------------------------+
|                            |          **Output formats**                                      |
|                            +------------------+-----------------------+-----------------------+
|                            |      EPUB        |         LRF           |         MOBI          |
+===================+========+==================+=======================+=======================+
|                   |  MOBI  |       ✔          |          ✔            |          ✔            |
|                   |        |                  |                       |                       |
|                   |  LIT   |       ✔          |          ✔            |          ✔            |
|                   |        |                  |                       |                       |
|                   |  PRC** |       ✔          |          ✔            |          ✔            |
|                   |        |                  |                       |                       |
|                   |  EPUB  |       ✔          |          ✔            |          ✔            |
|                   |        |                  |                       |                       |
|                   |  ODT   |       ✔          |          ✔            |          ✔            |
|                   |        |                  |                       |                       |
|                   |  HTML  |       ✔          |          ✔            |          ✔            |
|                   |        |                  |                       |                       |
| **Input formats** |  CBR   |       ✔          |          ✔            |          ✔            |
|                   |        |                  |                       |                       |
|                   |  CBZ   |       ✔          |          ✔            |          ✔            |
|                   |        |                  |                       |                       |
|                   |  RTF   |       ✔          |          ✔            |          ✔            |
|                   |        |                  |                       |                       |
|                   |  TXT   |       ✔          |          ✔            |          ✔            |
|                   |        |                  |                       |                       |
|                   |  PDF   |       ✔          |          ✔            |          ✔            | 
|                   |        |                  |                       |                       |
|                   |  LRS   |                  |          ✔            |                       |
+-------------------+--------+------------------+-----------------------+-----------------------+

** PRC is a generic format, |app| supports PRC files with TextRead and MOBIBook headers


What are the best source formats to convert?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In order of decreasing preference: LIT, MOBI, EPUB, HTML, PRC, RTF, TXT, PDF 

Why does the PDF conversion lose some images/tables?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The PDF conversion tries to extract the text and images from the PDF file and convert them to and HTML based ebook. Some PDF files have images in a format that cannot be extracted (vector images). All tables
are also represented as vector diagrams, thus they cannot be extracted.

How do I convert a collection of HTML files in a specific order?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In order to convert a collection of HTML files in a specific oder, you have to create a table of contents file. That is, another HTML file that contains links to all the other files in the desired order. Such a file looks like::
 
   <html>
      <body>
        <h1>Table of Contents</h1>
        <p style="text-indent:0pt">
           <a href="file1.html">First File</a><br/>
           <a href="file2.html">Second File</a><br/>
           .
           .
           .
        </p>
      </body>
   </html>

Then just add this HTML file to the GUI and use the convert button to create your ebook.

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
At the moment |app| has full support for the SONY PRS 500/505/700, Cybook Gen 3, Amazon Kindle 1 and 2 as well as the iPhone. In addition, using the :guilabel:`Save to disk` function you can use it with any ebook reader that exports itself as a USB disk.

I used |app| to transfer some books to my reader, and now the SONY software hangs every time I connect the reader?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You should not use both |app| and Connect to transfer books to the reader. You can fix this problem by: 
  * Removing any storage cards from your reader. 
  * Deleting the file media.xml from the reader's main memory using windows explorer (search for the file to find all locations where it is present). Note that by doing this you will lose all your collections, bookmarks, history etc. 
  * Unplugging the reader and waiting till the list of books shows up again 
  * Re-connecting the reader and starting the SONY software

Can I use the collections feature of the SONY reader?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| has full support for collections. When you add tags to a book's metadata, those tags are turned into collections when you upload the book to the SONY reader. Also, the series information is automatically
turned into a collection on the reader. Note that the PRS-500 does not support collections for books stored on the SD card. The PRS-505 does. 

How do I use |app| with my iPhone?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
First install the Stanza reader on your iPhone from http://www.lexcycle.com . Then,
  * Set the output format for calibre to EPUB (this can be done in the configuration dialog accessed by the little hammer icon next to the search bar)
  * Convert the books you want to read on your iPhone to EPUB format by selecting them and clicking the Convert button.
  * Turn on the Content Server in the configurations dialog and leave |app| running.
  * In the Stanza reader on your iPhone, add a new catalog. The URL of the catalog is of the form 
    ``http://10.34.56.89:8080/stanza``,  where you should replace the IP address ``10.34.56.89`` 
    with the IP address of your computer. Stanza will the use the |app| content server to access all the
    EPUB books in your |app| database.

Library Management
------------------

.. contents:: Contents
  :depth: 1
  :local:

What formats does |app| read metadata from?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| reads metadata from the following formats: LRF, PDF, LIT, RTF, OPF, MOBI, PRC, EPUB, FB2, IMP, RB, HTML. In addition it can write metadata to: LRF, RTF, OPF

Where are the book files stored?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
When you first run |app|, it will ask you for a folder in which to store your books. Whenever you add a book to |app|, it will copy the book into that folder. Books in the folder are nicely arranged into sub-folders by Author and Title. Metadata about the books is stored in the file ``metadata.db`` (which is a sqlite database).

Why doesn't |app| let me store books in my own directory structure?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The whole point of |app|'s library management features is that they provide an interface for locating books that is *much* more efficient than any possible directory scheme you could come up with for your collection. Indeed, once you become comfortable using |app|'s interface to find, sort and browse your collection, you wont ever feel the need to hunt through the files on your disk to find a book again. By managing books in its own directory struture of Author -> Title -> Book files, |app| is able to achieve a high level of reliability and standardization.  

Why doesn't |app| have a column for foo?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| is designed to have columns for the most frequently and widely used fields. If it does not have a coulmn for your favorite field, you can always add a tag to the book for that piece of information. |app| also supports a general purpose "comments" fields for longer items.


Content From The Web
---------------------
.. contents:: Contents
  :depth: 1
  :local:

My downloaded news content causes the reader to reset. 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This is a bug in the SONY firmware. The problem can be mitigated by switching the output format to EPUB
in the configuration dialog. Alternatively, you can use the LRF output format and use the SONY software 
to transfer the files to the reader. The SONY software pre-paginates the LRF file, 
thereby reducing the number of resets.

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

Why the name calibre?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Take your pick:
  * Convertor And LIBRary for E-books
  * A high *calibre* product
  * A tribute to the SONY Librie which was the first e-ink based e-book reader
  * My wife chose it ;-)

Why does |app| show only some of my fonts on OS X?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| embeds fonts in ebook files it creates. E-book files support embedding only TrueType (.ttf) fonts. Most fonts on OS X systems are in .dfont format, thus they cannot be embedded. |app| shows only TrueType fonts founf on your system. You can obtain many TrueType fonts on the web. Simply download the .ttf files and add them to the Library/Fonts directory in your home directory. 

The graphical user interface of |app| is not starting on Windows?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There can be several causes for this:

    * **Any windows version**: Try running it as Administrator (Right click on the icon ans select "Run as Administrator")
    * **Any windows version**: If this happens during an initial run of calibre, try deleting the folder you chose for your ebooks and restarting calibre.
    * **Windows Vista**: If the folder :file:`C:\\Users\\Your User Name\\AppData\\Local\\VirtualStore\\Program Files\\calibre` exists, delete it. Uninstall |app|. Reboot. Re-install.
    * **Any windows version**: Search your computer for a folder named :file:`_ipython`. Delete it and try again.
    * **Any windows version**: Try disabling any antivirus program you have running and see if that fixes it. Also try diabling any firewall software that prevents connections to the local computer.

If it still wont launch, start a command prompt (press the windows key and R; then type :command:`cmd.exe` in the Run dialog that appears). At the command prompt type the following command and press Enter::

    calibre-debug -g

Post any output you see in a help message on the `Forum <http://www.mobileread.com/forums/forumdisplay.php?f=166>`_.
    

I want some feature added to |app|. What can I do?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You have two choices: 
 1. Create a patch by hacking on |app| and send it to me for review and inclusion. See `Development <http://calibre.kovidgoyal.net/wiki/Development>`_. 
 2. `Open a ticket <http://calibre.kovidgoyal.net/newticket>`_ (you have to register and login first) and hopefully I will find the time to implement your feature.
