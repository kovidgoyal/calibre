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

*Input Formats:* CBZ, CBR, CBC, CHM, EPUB, FB2, HTML, LIT, LRF, MOBI, ODT, PDF, PRC**, PDB, PML, RB, RTF, SNB, TCR, TXT

*Output Formats:* EPUB, FB2, OEB, LIT, LRF, MOBI, PDB, PML, RB, PDF, SNB, TCR, TXT

** PRC is a generic format, |app| supports PRC files with TextRead and MOBIBook headers

.. _best-source-formats:

What are the best source formats to convert?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In order of decreasing preference: LIT, MOBI, EPUB, HTML, PRC, RTF, PDB, TXT, PDF

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

.. _char-encoding-faq:

How do I convert my file containing non-English characters, or smart quotes?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There are two aspects to this problem:
  1. Knowing the encoding of the source file: |app| tries to guess what character encoding your source files use, but often, this is impossible, so you need to tell it what encoding to use. This can be done in the GUI via the :guilabel:`Input character encoding` field in the :guilabel:`Look & Feel` section. The command-line tools all have an :option:`--input-encoding` option.
  2. When adding HTML files to |app|, you may need to tell |app| what encoding the files are in. To do this go to :guilabel:`Preferences->Advanced->Plugins->File Type plugins` and customize the HTML2Zip plugin, telling it what encoding your HTML files are in. Now when you add HTML files to |app| they will be correctly processed. HTML files from different sources often have different encodings, so you may have to change this setting repeatedly. A common encoding for many files from the web is ``cp1252`` and I would suggest you try that first. Note that when converting HTML files, leave the input encoding setting mentioned above blank. This is because the HTML2ZIP plugin automatically converts the HTML files to a standard encoding (utf-8).
  3. Embedding fonts: If you are generating an LRF file to read on your SONY Reader, you are limited by the fact that the Reader only supports a few non-English characters in the fonts it comes pre-loaded with. You can work around this problem by embedding a unicode-aware font that supports the character set your file uses into the LRF file. You should embed atleast a serif and a sans-serif font. Be aware that embedding fonts significantly slows down page-turn speed on the reader.


How do I use some of the advanced features of the conversion tools?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 You can get help on any individual feature of the converters by mousing over it in the GUI or running ``ebook-convert dummy.html .epub -h`` at a terminal. A good place to start is to look at the following demo files that demonstrate some of the advanced features:
  * `html-demo.zip <http://calibre-ebook.com/downloads/html-demo.zip>`_


Device Integration
-------------------

.. contents:: Contents
  :depth: 1
  :local:

What devices does |app| support?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
At the moment |app| has full support for the SONY PRS line, Barnes & Noble Nook, Cybook Gen 3/Opus, Amazon Kindle line, Entourage Edge, Longshine ShineBook, Ectaco Jetbook, BeBook/BeBook Mini, Irex Illiad/DR1000, Foxit eSlick, PocketBook 360, Italica, eClicto, Iriver Story, Airis dBook, Hanvon N515, Binatone Readme, Teclast K3, SpringDesign Alex, Kobo Reader, various Android phones and the iPhone/iPad. In addition, using the :guilabel:`Save to disk` function you can use it with any ebook reader that exports itself as a USB disk.

How can I help get my device supported in |app|?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your device appears as a USB disk to the operating system, adding support for it to |app| is very easy.
We just need some information from you:

  * What e-book formats does your device support?
  * Is there a special directory on the device in which all e-book files should be placed?
  * We also need information about your device that |app| will collect automatically. First, if your
    device supports SD cards, insert them. Then connect your device. In calibre go to :guilabel:`Preferences->Advanced->Miscellaneous`
    and click the "Debug device detection" button. This will create some debug output. Copy it to a file
    and repeat the process, this time with your device disconnected.
  * Send both the above outputs to us with the other information and we will write a device driver for your
    device.

Once you send us the output for a particular operating system, support for the device in that operating system
will appear in the next release of |app|.

How does |app| manage collections on my SONY reader?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When |app| connects with the reader, it retrieves all collections for the books on the reader. The collections
of which books are members are shown on the device view.

When you send a book to the reader, |app| will add the book to collections based on the metadata for that book. By
default, collections are created from tags and series. You can control what metadata is used by going to
:guilabel:`Preferences->Advanced->Plugins->Device Interface plugins` and customizing the SONY device interface plugin. If you remove all
values, |app| will not add the book to any collection.

Collection management is largely controlled by the 'Metadata management' option found at
:guilabel:`Preferences->Import/Export->Sending books to devices`. If set to 'Manual' (the default), managing collections is left to
the user; |app| will not delete already existing collections for a book on your reader when you resend the
book to the reader, but |app| will add the book to collections if necessary.  To ensure that the collections
for a book are based only on current |app| metadata, first delete the books from the reader, then resend the
books.  You can edit collections directly on the device view by double-clicking or right-clicking in the
collections column.

If 'Metadata management' is set to 'Only on send', then |app| will manage collections more aggressively.
Collections will be built using |app| metadata exclusively.  Sending a book to the reader will correct the
collections for that book so its collections exactly match the book's metadata, adding and deleting
collections as necessary.  Editing collections on the device view is not permitted, because collections not in
the metadata will be removed automatically.

If 'Metadata management' is set to 'Automatic management', then |app| will update metadata and collections
both when the reader is connected and when books are sent. When calibre detects the reader and generates the
list of books on the reader, it will send metadata from the library to the reader for all books on the reader
that are in the library (On device is True), adding and removing books from collections as indicated by the
metadata and device customization. When a book is sent, |app| corrects the metadata for that book, adding and
deleting collections. Manual editing of metadata on the device view is not allowed. Note that this option
specifies sending metadata, not books. The book files on the reader are not changed.

In summary, choose 'manual management' if you want to manage collections yourself.  Collections for a book
will never be removed by |app|, but can be removed by you by editing on the device view.  Choose 'Only on
send' if you want |app| to manage collections when you send a book, adding books to and removing books from
collections as needed.  Choose 'Automatic management' if you want |app| to keep collections up to date
whenever the reader is connected.

If you use multiple installations of calibre to manage your reader, then option 'Automatic management' may not
be what you want.  Connecting the reader to one library will reset the metadata to what is in that library.
Connecting to the other library will reset the metadata to what is in that other library. Metadata in books
found in both libraries will be flopped back and forth.

Can I use both |app| and the SONY software to manage my reader?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Yes, you can use both, provided you do not run them at the same time. That is, you should use the following sequence:
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
your PC's file explorer and it will be recreated after disconnection.

With recent reader iterations, SONY, in all its wisdom has decided to try to force you to
use their software. If you install it, it auto-launches whenever you connect the reader.
If you don't want to uninstall it altogether, there are a couple of tricks you can use. The
simplest is to simply re-name the executable file that launches the library program. More detail
`in the forums <http://www.mobileread.com/forums/showthread.php?t=65809>`_.

Can I use the collections feature of the SONY reader?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| has full support for collections. When you add tags to a book's metadata, those tags are turned into collections when you upload the book to the SONY reader. Also, the series information is automatically
turned into a collection on the reader. Note that the PRS-500 does not support collections for books stored on the SD card. The PRS-505 does.

How do I use |app| with my iPad/iPhone/iTouch?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Over the air
^^^^^^^^^^^^^^

The easiest way to browse your |app| collection on your Apple device (iPad/iPhone/iPod) is by using the *free* Stanza app, available from the Apple app store. You need at least Stanza version 3.0. Stanza allows you to access your |app| collection wirelessly, over the air.

First perform the following steps in |app|

  * Set the Preferred Output Format in |app| to EPUB (The output format can be set under :guilabel:`Preferences->Interface->Behavior`)
  * Set the output profile to iPad (this will work for iPhone/iPods as well), under :guilabel:`Preferences->Conversion->Common Options->Page Setup`
  * Convert the books you want to read on your iPhone to EPUB format by selecting them and clicking the Convert button.
  * Turn on the Content Server in |app|'s preferences and leave |app| running.

Install the free Stanza reader app on your iPad/iPhone/iTouch using iTunes.

Now you should be able to access your books on your iPhone by opening Stanza. Go to "Get Books" and then click the "Shared" tab. Under Shared you will see an entry "Books in calibre". If you don't, make sure your iPad/iPhone is connected using the WiFi network in your house, not 3G. If the |app| catalog is still not detected in Stanza, you can add it manually in Stanza. To do this, click the "Shared" tab, then click the "Edit" button and then click "Add book source" to add a new book source. In the Add Book Source screen enter whatever name you like and in the URL field, enter the following::

    http://192.168.1.2:8080/

Replace ``192.168.1.2`` with the local IP address of the computer running |app|. If you have changed the port the |app| content server is running on, you will have to change ``8080`` as well to the new port. The local IP address is the IP address you computer is assigned on your home network. A quick Google search will tell you how to find out your local IP address.   Now click "Save" and you are done.

If you get timeout errors while browsing the calibre catalog in Stanza, try increasing the connection timeout value in the stanza settings. Go to Info->Settings and increase the value of Download Timeout.

With the USB cable
^^^^^^^^^^^^^^^^^^^^^^^^^^^

As of |app| version 0.7.0, you can plug your iDevice into the computer using its charging cable, and |app| will detect it and show you a list of books on the device. You can then use the *Send to device button* to send books directly to iBooks on the device. Note that you must have at least iOS 4 installed on your iPhone/iTouch for this to work.

This method only works on Windows XP and higher and OS X 10.5 and higher. Linux is not supported (iTunes is not available in linux) and OS X 10.4 is not supported.
For more details on how this works, see `this forum post <http://www.mobileread.com/forums/showpost.php?p=944079&postcount=1>`_.

How do I use |app| with my Android phone?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First install the WordPlayer e-book reading app from the Android Marketplace onto you phone. Then simply plug your phone into the computer with a USB cable. |app| should automatically detect the phone and then you can transfer books to it by clicking the Send to Device button. |app| does not have support for every single androind device out there, so if you would like to have support for your device added, follow the instructions above for getting your device supported in |app|.

Can I access my |app| books using the web browser in my Kindle or other reading device?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

|app| has a *Content Server* that exports the books in |app| as a web page. You can turn it on under
:guilabel:`Preferences->Network->Sharing over the net`. Then just point the web browser on your device to the computer running
the Content Server and you will be able to browse your book collection. For example, if the computer running
the server has IP address 63.45.128.5, in the browser, you would type::

    http://63.45.128.5:8080

Some devices, like the Kindle (1/2/DX), do not allow you to access port 8080 (the default port on which the content
server runs. In that case, change the port in the |app| Preferences to 80. (On some operating systems,
you may not be able to run the server on a port number less than 1024 because of security settings. In
this case the simplest solution is to adjust your router to forward requests on port 80 to port 8080).

I get the error message "Failed to start content server: Port 8080 not free on '0.0.0.0'"?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most likely cause of this is your antivirus program. Try temporarily disabling it and see if it does the trick.

Why is my device not detected in linux?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

|app| needs your linux kernel to have been setup correctly to detect devices. If your devices are not detected, perform the following tests::

    grep SYSFS_DEPRECATED /boot/config-`uname -r`

You should see something like ``CONFIG_SYSFS_DEPRECATED_V2 is not set``.
Also, ::

    grep CONFIG_SCSI_MULTI_LUN /boot/config-`uname -r`

must return ``CONFIG_SCSI_MULTI_LUN=y``. If you don't see either, you have to recompile your kernel with the correct settings.

My device is getting mounted read-only in linux, so |app| cannot connect to it?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

linux kernels mount devices read-only when their filesystems have errors. You can repair the filesystem with::

    sudo fsck.vfat -y /dev/sdc

Replace /dev/sdc with the path to the device node of your device. You can find the device node of your device, which
will always be under /dev by examining the output of::

    mount


Why does |app| not support collection on the Kindle or shelves on the Nook?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Neither the Kindle nor the Nook provide any way to manipulate collections over a USB connection.
If you really care about using collections, I would urge you to sell your Kindle/Nook and get a SONY. 
Only SONY seems to understand that life is too short to be entering collections one by one on an
e-ink screen :)

Note that in the case of the Kindle, there is a way to manipulate collections via USB,
but it requires that the Kindle be rebooted *every time* it is disconnected from the computer, for the 
changes to the collections to be recognized. As such, it is unlikely that
any |app| developers will ever feel motivated enough to support it.

Library Management
------------------

.. contents:: Contents
  :depth: 1
  :local:

What formats does |app| read metadata from?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| reads metadata from the following formats: CHM, LRF, PDF, LIT, RTF, OPF, MOBI, PRC, EPUB, FB2, IMP, RB, HTML. In addition it can write metadata to: LRF, RTF, OPF, EPUB, PDF, MOBI

Where are the book files stored?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
When you first run |app|, it will ask you for a folder in which to store your books. Whenever you add a book to |app|, it will copy the book into that folder. Books in the folder are nicely arranged into sub-folders by Author and Title. Metadata about the books is stored in the file ``metadata.db`` (which is a sqlite database).

Why doesn't |app| let me store books in my own directory structure?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The whole point of |app|'s library management features is that they provide a search and sort based interface for locating books that is *much* more efficient than any possible directory scheme you could come up with for your collection. Indeed, once you become comfortable using |app|'s interface to find, sort and browse your collection, you wont ever feel the need to hunt through the files on your disk to find a book again. By managing books in its own directory struture of Author -> Title -> Book files, |app| is able to achieve a high level of reliability and standardization. To illustrate why a search/tagging based interface is superior to folders, consider the following. Suppose your book collection is nicely sorted into folders with the following scheme::

    Genre -> Author -> Series -> ReadStatus

Now this makes it very easy to find for example all science fiction books by Isaac Asimov in the Foundation series. But suppose you want to find all unread science fiction books. There's no easy way to do this with this folder scheme, you would instead need a folder scheme that looks like::

    ReadStatus -> Genre -> Author -> Series

In |app|, you would instead use tags to mark genre and read status and then just use a simple search query like ``tag:scifi and not tag:read``. |app| even has a nice graphical interface, so you don't need to learn its search language instead you can just click on tags to include or exclude them from the search.

Why doesn't |app| have a column for foo?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| is designed to have columns for the most frequently and widely used fields. In addition, you can add any columns you like. Columns can be added via :guilabel:`Preferences->Interface->Add your own columns`.
Watch the tutorial `UI Power tips <http://calibre-ebook.com/demo#tutorials>`_ to learn how to create your own columns.

You can also create "virtual columns" that contain combinations of the metadata from other columns. In the add column dialog choose the option "Column from other columns" and in the template enter the other column names. For example to create a virtual column containing formats or ISBN, enter ``{formats}`` for formats or ``{isbn}`` for ISBN. For more details, see :ref:`templatelangcalibre`.


Can I have a column showing the formats or the ISBN?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Yes, you can. Follow the instructions in the answer above for adding custom columns. 

How do I move my |app| library from one computer to another?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Simply copy the |app| library folder from the old to the new computer. You can find out what the library folder is by clicking the calibre icon in the toolbar. The very first item is the path to the library folder. Now on the new computer, start |app| for the first time. It will run the Welcome Wizard asking you for the location of the |app| library. Point it to the previously copied folder. If the computer you are transferring to already has a calibre installation, then the Welcome wizard wont run. In that case, click the calibre icon in the tooolbar and point it to the newly copied directory. You will now have two calibre libraries on your computer and you can switch between them by clicking the calibre icon on the toolbar.

Note that if you are transferring between different types of computers (for example Windows to OS X) then after doing the above you should also go to :guilabel:`Preferences->Advanced->Miscellaneous` and click the "Check database integrity button". It will warn you about missing files, if any, which you should then transfer by hand.


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

Otherwise, you can register a request for a particular news site by adding a comment `to this ticket <http://bugs.calibre-ebook.com/ticket/405>`_.

Can I use web2disk to download an arbitrary website?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``web2disk http://mywebsite.com``

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
|app| embeds fonts in ebook files it creates. E-book files support embedding only TrueType (.ttf) fonts. Most fonts on OS X systems are in .dfont format, thus they cannot be embedded. |app| shows only TrueType fonts found on your system. You can obtain many TrueType fonts on the web. Simply download the .ttf files and add them to the Library/Fonts directory in your home directory.

|app| is not starting on Windows?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There can be several causes for this:

    * If you get an error about calibre not being able to open a file because it is in use by another program, do the following:

       * Uninstall calibre
       * Reboot your computer
       * Re-install calibre. But do not start calibre from the installation wizard.
       * Temporarily disable your antivirus program (disconnect from the internet before doing so, to be safe)
       * Look inside the folder you chose for your calibre library. If you see a file named metadata.db, delete it.
       * Start calibre
       * From now on you should be able to start calibre normally. 

    * If you get an error about a Python function terminating unexpectedly after upgrading calibre, first uninstall calibre, then delete the folders (if they exists)
      :file:`C:\\Program Files\\Calibre` and :file:`C:\\Program Files\\Calibre2`. Now re-install and you should be fine.
    * If you get an error in the welcome wizard on an initial run of calibre, try choosing a folder like :file:`C:\\library` as the calibre library (calibre sometimes
      has trouble with library locations if the path contains non-English characters, or only numbers, etc.)
    * Try running it as Administrator (Right click on the icon and select "Run as Administrator")
    * **Windows Vista**: If the folder :file:`C:\\Users\\Your User Name\\AppData\\Local\\VirtualStore\\Program Files\\calibre` exists, delete it. Uninstall |app|. Reboot. Re-install.
    * **Any windows version**: Try disabling any antivirus program you have running and see if that fixes it. Also try disabling any firewall software that prevents connections to the local computer.

If it still wont launch, start a command prompt (press the windows key and R; then type :command:`cmd.exe` in the Run dialog that appears). At the command prompt type the following command and press Enter::

    calibre-debug -g

Post any output you see in a help message on the `Forum <http://www.mobileread.com/forums/forumdisplay.php?f=166>`_.

|app| is not starting on OS X?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One common cause of failures on OS X is the use of accessibility technologies that are incompatible with the graphics toolkit |app| uses.
Try turning off VoiceOver if you have it on. Also go to System Preferences->System->Universal Access and turn off the setting for enabling
access for assistive devices in all the tabs.

You can obtain debug output about why |app| is not starting by running `Console.app`. Debug output will
be printed to it. If the debug output contains a line that looks like::

    Qt: internal: -108: Error ATSUMeasureTextImage text/qfontengine_mac.mm

then the problem is probably a corrupted font cache. You can clear the cache by following these
`instructions <http://www.macworld.com/article/139383/2009/03/fontcacheclear.html>`_. If that doesn't
solve it, look for a corrupted font file on your system, in ~/Library/Fonts or the like. An easy way to
check for corrupted fonts in OS X is to start the "Font Book" application, select all fonts and then in the File
menu, choose "Validate fonts".


I downloaded the installer, but it is not working?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Downloading from the internet can sometimes result in a corrupted download. If the |app| installer you downloaded is not opening, try downloading it again. If re-downloading it does not work, download it from `an alternate location <http://sourceforge.net/projects/calibre/files/>`_. If the installer still doesn't work, then something on your computer is preventing it from running. Best place to ask for more help is in the `forums <http://www.mobileread.com/forums/usercp.php>`_.

My antivirus program claims |app| is a virus/trojan?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Your antivirus program is wrong. |app| is a completely open source product. You can actually browse the source code yourself (or hire someone to do it for you) to verify that it is not a virus. Please report the false identification to whatever company you buy your antivirus software from. If the antivirus program is preventing you from downloading/installing |app|, disable it temporarily, install |app| and then re-enable it.

How do I use purchased EPUB books with |app|?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Most purchased EPUB books have `DRM <http://wiki.mobileread.com/wiki/DRM>`_. This prevents |app| from opening them. You can still use |app| to store and transfer them to your e-book reader. First, you must authorize your reader on a windows machine with Adobe Digital Editions. Once this is done, EPUB books transferred with |app| will work fine on your reader. When you purchase an epub book from a website, you will get an ".acsm" file. This file should be opened with Adobe Digital Editions, which will then download the actual ".epub" e-book. The e-book file will be stored in the folder "My Digital Editions", from where you can add it to |app|.

Can I have the comment metadata show up on my reader?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Most readers do not support this. You should complain to the manufacturer about it and hopefully if enough people complain, things will change. In the meantime, you can insert the metadata, including comments into a "Jacket page" at the start of the ebook, by using the option to "Insert metadata as page at start of book" during conversion. The option is found in the :guilabel:`Structure Detection` section of the conversion settings. Note that for this to have effect you have to *convert* the book. If your book is already in a format that does not need conversion, you can convert from that format to the same format. 

Another alternative is to create a catalog in ebook form containing a listing of all the books in your calibre library, with their metadata. Click the arrow next to the convert button to access the catalog creation tool. And before you ask, no you cannot have the catalog "link directly to" books on your reader. 

I want some feature added to |app|. What can I do?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You have two choices:
 1. Create a patch by hacking on |app| and send it to me for review and inclusion. See `Development <http://calibre-ebook.com/get-involved>`_.
 2. `Open a ticket <http://bugs.calibre-ebook.com/newticket>`_ (you have to register and login first) and hopefully I will find the time to implement your feature.

Can I include |app| on a CD to be distributed with my product/magazine?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| is licensed under the GNU General Public License v3 (an open source license). This means that you are free to redistribute |app| as long as you make the source code available. So if you want to put |app| on a CD with your product, you must also put the |app| source code on the CD. The source code is available for download `from googlecode <http://code.google.com/p/calibre-ebook/downloads/list>`_.

How do I run calibre from my USB stick?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A portable version of calibre is available at: `portableapps.com <http://portableapps.com/node/20518>`_. However, this is usually out of date. You can also setup your own portable calibre install by following :ref:`these instructions <portablecalibre>`.

Why are there so many calibre-parallel processes on my system?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

|app| maintains two separate worker process pools. One is used for adding books/saving to disk and the other for conversions. You can control the number of worker processes via :guilabel:`Preferences->Advanced->Miscellaneous`. So if you set it to 6 that means a maximum of 3 conversions will run simultaneously. And that is why you will see the number of worker processes changes by two when you use the up and down arrows. On windows, you can set the priority that these processes run with. This can be useful on older, single CPU machines, if you find them slowing down to a crawl when conversions are running. 

In addition to this some conversion plugins run tasks in their own pool of processes, so for example if you bulk convert comics, each comic conversion will use three separate processes to render the images. The job manager knows this so it will run only a single comic conversion simultaneously.

And since I'm sure someone will ask: The reason adding/saving books are in separate processes is because of PDF. PDF processing libraries can crash on reading PDFs and I dont want the crash to take down all of calibre. Also when adding EPUB books, in order to extract the cover you have to sometimes render the HTML of the first page, which means that it either has to run the GUI thread of the main process or in a separate process.

Finally, the reason calibre keep workers alive and idle instead of launching on demand is to workaround the slow startup time of python processes.

How do I run parts of |app| like news download and the content server on my own linux server?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First, you must install |app| onto your linux server. If your server is using a modern linux distro, you should have no problems installing |app| onto it.

.. note:: 
    If you bought into the notion that a real server must run a decade old version of Debian, then you will have to jump through a few hoops. First, compile a newer version of glibc (>= 2.10) on your server from source. Then get the |app| linux binary tarball from the |app| google code page for your server architecture. Extract it into :file:`/opt/calibre`. Put your previously compiled glibc into :file:`/opt/calibre` as :file:`libc.so.6`. You can now run the calibre binaries from :file:`/opt/calibre`.

You can run the |app| server via the command::

    /opt/calibre/calibre-server --with-library /path/to/the/library/you/want/to/share

You can download news and convert it into an ebook with the command::

   /opt/calibre/ebook-convert "Title of news source.recipe" outputfile.epub

If you want to generate MOBI, use outputfile.mobi instead. 

You can email downloaded news with the command::
    
    /opt/calibre/calibre-smtp

I leave figuring out the exact command line as an exercise for the reader.

Finally, you can add downloaded news to the |app| library with::

   /opt/calibre/calibredb add --with-library /path/to/library outfile.epub

Remember to read the command line documentation section of the |app| User Manual to learn more about these, and other commands.

.. note:: Some parts of calibre require a X server. If you're lucky, nothing you do will fall into this category, if not, you will have to look into using xvfb.

