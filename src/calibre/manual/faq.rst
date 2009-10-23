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
|app| supports the conversion of many input formats to many output formats.
It can convert every input format in the following list, to every output format.

*Input Formats:* CBZ, CBR, CBC, EPUB, FB2, HTML, LIT, LRF, MOBI, ODT, PDF, PRC**, PDB, PML, RB, RTF, TCR, TXT
*Output Formats:* EPUB, FB2, OEB, LIT, LRF, MOBI, PDB, PML, RB, PDF, TCR, TXT

** PRC is a generic format, |app| supports PRC files with TextRead and MOBIBook headers


What are the best source formats to convert?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In order of decreasing preference: LIT, MOBI, EPUB, HTML, PRC, RTF, TXT, PDF 

Why does the PDF conversion lose some images/tables?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The PDF conversion tries to extract the text and images from the PDF file and convert them to and HTML based ebook. Some PDF files have images in a format that cannot be extracted (vector images). All tables
are also represented as vector diagrams, thus they cannot be extracted.

How do I convert a collection of HTML files in a specific order?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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

How do I convert my file containing non-English characters, or smart quotes?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There are two aspects to this problem: 
  1. Knowing the encoding of the source file: |app| tries to guess what character encoding your source files use, but often, this is impossible, so you need to tell it what encoding to use. This can be done in the GUI via the :guilabel:`Input character encoding` field in the :guilabel:`Look & Feel` section. The command-line tools all have an :option:`--input-encoding` option.
  2. When adding HTML files to |app|, you may need to tell |app| what encoding the files are in. To do this go to Preferences->Plugins->File Type plugins and customize the HTML2Zip plugin, telling it what encoding your HTML files are in. Now when you add HTML files to |app| they will be correctly processed. HTML files from different sources often have different encodings, so you may have to change this setting repeatedly. A common encoding for many files from the web is ``cp1252`` and I would suggest you try that first.
  3. Embedding fonts: If you are generating an LRF file to read on your SONY Reader, you are limited by the fact that the Reader only supports a few non-English characters in the fonts it comes pre-loaded with. You can work around this problem by embedding a unicode-aware font that supports the character set your file uses into the LRF file. You should embed atleast a serif and a sans-serif font. Be aware that embedding fonts significantly slows down page-turn speed on the reader. 


How do I use some of the advanced features of the conversion tools?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 You can get help on any individual feature of the converters by mousing over it in the GUI or running ``ebook-convert dummy.html .epub -h`` at a terminal. A good place to start is to look at the following demo files that demonstrate some of the advanced features: 
  * `html-demo.zip <http://calibre.kovidgoyal.net/downloads/html-demo.zip>`_ 
  * `txt-demo.zip <http://calibre.kovidgoyal.net/downloads/txt-demo.zip>`_


Device Integration
-------------------

.. contents:: Contents
  :depth: 1
  :local:

What devices does |app| support?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
At the moment |app| has full support for the SONY PRS 300/500/505/600/700, Cybook Gen 3/Opus, Amazon Kindle 1/2/DX, Netronix EB600, Ectaco Jetbook, BeBook/BeBook Mini, Irex Illiad/DR1000, Foxit eSlick, Android phones and the iPhone. In addition, using the :guilabel:`Save to disk` function you can use it with any ebook reader that exports itself as a USB disk.

How can I help get my device supported in |app|?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your device appears as a USB disk to the operating system. Adding support for it to |app| is very easy.
We just need some information from you:

  * What e-book formats does your device support?
  * Is there a special directory on the device in which all e-book files should be placed?
  * We also need the output from running the following command in a terminal, both with the device
    connected and without::

        calibre-debug -d

  * If your device supports SD cards, run the above command with the cards inserted.

To run the above command, on Windows you should use the full path to calibre-debug.exe
On OSX, you should go to Preferences->Advanced and click "Install command line tools".

Once you send us the output for a particular operating system, support for the device
will appear in the next release of |app|.


Can I use both |app| and the SONY software to manage my reader?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Yes, you can use both, provided you don not run them at the same time. That is, you should use the following sequence:
Connect reader->Use one of the programs->Disconnect reader. Reconnect reader->Use the other program->disconnect reader.

The underlying reason is that the Reader uses a single file to keep track
of 'meta' information, such as collections, and this is written to by both
|app| and the Sony software when either updates something on the Reader.
The file will be saved when the Reader is (safely) disconnected, so using one
or the other is safe if there's a disconnection between them, but if
you're not the type to remember this, then the simple answer is to stick
to one or the other for the transfer and just export/import from/to the
other via the computers hard disk.

If you do need to reset your metadata due to problems caused by using both
at the same time, then just delete the media.xml file on the Reader using
your PC's file explorer and it'll be recreated after disconnection.


Can I use the collections feature of the SONY reader?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| has full support for collections. When you add tags to a book's metadata, those tags are turned into collections when you upload the book to the SONY reader. Also, the series information is automatically
turned into a collection on the reader. Note that the PRS-500 does not support collections for books stored on the SD card. The PRS-505 does. 

How do I use |app| with my iPhone?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
First install the Stanza reader on your iPhone using iTunes.

  * Set the Preferred Output Format in |app| to EPUB (The output format can be set under Preferences->General) 
  * Convert the books you want to read on your iPhone to EPUB format by selecting them and clicking the Convert button.
  * Turn on the Content Server in |app|'s preferences and leave |app| running.

Now you should be able to access your books on your iPhone by opening Stanza and going to "Shared Books". Under Shared Books you will see an entry "Book in calibre". If you don't, make sure your iPhone is connected using the WiFi network in your house, not 3G. If the |app| catalog is still not detected in Stanza, you can add it manually in Stanza, by clicking "Online Catalog" and the clicking the plus icon in the lower right corner to add a new catalog. In the Add Catalog screen enter whatever name you like and in the URL field, enter the following::

    http://192.168.1.2:8080/

Replace ``192.168.1.2`` with the local IP address of the computer running |app|. If you have changed the port the |app| content server is running on, you will have to change ``8080`` as well to the new port. The local IP address is the IP address you computer is assigned on your home network. A quick Google search will tell you how to find out your local IP address.  

How do I use |app| with my Android phone?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First install the WordPlayer e-book reading app from the Android Marketplace onto you phone. Then simply plug your phone into the computer with a USB cable. |app| should automatically detect the phone and then you can transfer books to it by clicking the Send to Device button. |app| does not have support for every single androind device out there, so if you would like to have support for your device added, follow the instructions above for getting your device supported in |app|.

I get the error message "Failed to start content server: Port 8080 not free on '0.0.0.0'"?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most likely cause of this is your antivirus program. Try temporarily disabling it and see if it does the trick.

Why is my device not detected in linux?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

|app| uses something called SYSFS to detect devices in linux. The linux kernel can export two version of SYSFS, one of which is deprecated. Some linux distributions still ship with kernels that support the deprecated version of SYSFS, even though it was deprecated a long time ago. In this case, device detection in |app| will not work. You can check what version of SYSFS is exported by your kernel with the following command::
    
    grep SYSFS_DEPRECATED /boot/config-`uname -r`

You should see something like ``CONFIG_SYSFS_DEPRECATED_V2 is not set``. 

Library Management
------------------

.. contents:: Contents
  :depth: 1
  :local:

What formats does |app| read metadata from?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| reads metadata from the following formats: LRF, PDF, LIT, RTF, OPF, MOBI, PRC, EPUB, FB2, IMP, RB, HTML. In addition it can write metadata to: LRF, RTF, OPF, EPUB, PDF, MOBI

Where are the book files stored?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
When you first run |app|, it will ask you for a folder in which to store your books. Whenever you add a book to |app|, it will copy the book into that folder. Books in the folder are nicely arranged into sub-folders by Author and Title. Metadata about the books is stored in the file ``metadata.db`` (which is a sqlite database).

Why doesn't |app| let me store books in my own directory structure?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The whole point of |app|'s library management features is that they provide an interface for locating books that is *much* more efficient than any possible directory scheme you could come up with for your collection. Indeed, once you become comfortable using |app|'s interface to find, sort and browse your collection, you wont ever feel the need to hunt through the files on your disk to find a book again. By managing books in its own directory struture of Author -> Title -> Book files, |app| is able to achieve a high level of reliability and standardization.  

Why doesn't |app| have a column for foo?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| is designed to have columns for the most frequently and widely used fields. If it does not have a coulmn for your favorite field, you can always add a tag to the book for that piece of information. |app| also supports a general purpose "comments" fields for longer items.

How do I move my |app| library from one computer to another?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Simply copy the |app| library folder from the old to the new computer. You can find out what the library folder is by clicking Preferences. The very first item is the path to the library folder. Now on the new computer, start |app| for the first time. It will run the Welcome Wizard asking you for the location of the |app| library. Point it to the previously copied folder. 

Note that if you are transferring between different types of computers (for example Windows to OS X) then after doing the above you should also go to Preferences->Advanced and click the Check database integrity button. It will warn you about missing files, if any, which you should then transfer by hand.


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
    
My antivirus programs claims |app| is a virus/trojan?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Your antivirus program is wrong. |app| is a completely open source product. You can actually browse the source code yourself (or hire someone to do it for you) to verify that it is not a virus. Please report the false identification to whatever company you buy your antivirus software from. If the antivirus program is preventing you from downloading/installing |app|, disable it temporarily, install |app| and then re-enable it.

How do I use purchased EPUB books with |app|?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Most purchased EPUB books have `DRM <http://wiki.mobileread.com/wiki/DRM>`_. This prevents |app| from opening them. You can still use |app| to store and transfer them to your SONY Reader. First, you must authorize your reader on a windows machine with Adobe Digital Editions. Once this is done, EPUB books transferred with |app| will work fine on your reader. Sometimes, the EPUB file itself is corrupted, in which case you should notify the e-book vendor.


I want some feature added to |app|. What can I do?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You have two choices: 
 1. Create a patch by hacking on |app| and send it to me for review and inclusion. See `Development <http://calibre.kovidgoyal.net/wiki/Development>`_. 
 2. `Open a ticket <http://calibre.kovidgoyal.net/newticket>`_ (you have to register and login first) and hopefully I will find the time to implement your feature.
