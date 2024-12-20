.. _viewer:

The E-book viewer
=============================

calibre includes a built-in E-book viewer that can view all the major e-book formats.
The E-book viewer is highly customizable and has many advanced features.

.. contents::
    :depth: 1
    :local:

Starting the E-book viewer
-----------------------------

You can view any of the books in your calibre library by selecting the book and
pressing the :guilabel:`View` button. This will open up the book in the E-book
viewer. You can also launch the E-book viewer by itself from the Start menu in
Windows.  On macOS, you can pin it to the dock and launch it from there. On
Linux you can use its launcher in the desktop menus or run the command
:command:`ebook-viewer`.


Navigating around an e-book
-----------------------------

You can "turn pages" in a book by either:

  - Clicking in the left or right margin or the page with the mouse
  - Pressing the :kbd:`spacebar`, :kbd:`page up`, :kbd:`page down` or arrow keys
  - On a touchscreen tapping on the text or swiping left and right


You can access the viewer controls by either:

  - Right clicking on the text
  - Pressing the :kbd:`Esc` or :kbd:`Menu` keys
  - On a touchscreen by tapping the top 1/3rd of the screen


The viewer has two modes, "paged" and "flow". In paged mode the book content
is presented as pages, similar to a paper book. In flow mode the text is
presented continuously, like in a web browser. You can switch between them
using the viewer :guilabel:`Preferences` under :guilabel:`Page layout` or by pressing the
:kbd:`Ctrl+M` key.


Bookmarks
^^^^^^^^^^^^

When you are in the middle of a book and close the E-book viewer, it will remember
where you stopped reading and return there the next time you open the book. You
can also set bookmarks in the book by using the :guilabel:`Bookmarks` button in
the E-book viewer controls or pressing :kbd:`Ctrl+B`. When viewing EPUB format books,
these bookmarks are actually saved in the EPUB file itself. You can add
bookmarks, then send the file to a friend.  When they open the file, they will
be able to see your bookmarks. You can turn off this behavior in the
:guilabel:`Miscellaneous` section of the viewer preferences.


Table of Contents
^^^^^^^^^^^^^^^^^^^^

If the book you are reading defines a Table of Contents, you can access it by
pressing the :guilabel:`Table of Contents` button. This will bring up a list
of sections in the book. You can click on any of them to jump to that portion
of the book.


Navigating by location
^^^^^^^^^^^^^^^^^^^^^^^^

E-books, unlike paper books, have no concept of pages. You can refer to precise
locations in e-books using the :guilabel:`Go to->Location` functionality in the
viewer controls.

You can use this location information to unambiguously refer to parts of the
books when discussing it with friends or referring to it in other works. You
can enter these locations under :guilabel:`Go to->Location` in the viewer
controls.

There is a URL you can copy to the clipboard and paste into other programs
or documents. Clicking on this URL will open the book in the calibre E-book viewer at
the current location.

If you click on links inside the e-book to take you to different parts of the
book, such as an endnote, you can use the :guilabel:`Back` and
:guilabel:`Forward` buttons in the top left corner of the viewer controls.
These buttons behave just like those in a web browser.

Reference mode
^^^^^^^^^^^^^^^^^

calibre also has a very handy :guilabel:`Reference mode`. You can turn it on
by clicking the :guilabel:`Reference mode` button in the viewer controls.  Once
you do this, every paragraph will have a unique number displayed at the start,
made up of the section and paragraph numbers.

You can use this number to unambiguously refer to parts of the books when
discussing it with friends or referring to it in other works. You can enter
these numbers in the :guilabel:`Go to function` to navigate to a particular
reference location.


Highlighting text
----------------------

When you select text in the viewer, a little popup bar appears next to the
selection. You can click the highlight button in that bar to create a
highlight. You can add notes and change the color of the highlight. On a touch
screen, long tap a word to select it and show the popup bar. Once in highlight
mode you can change what text is selected, using touch screen friendly selection
handles. Drag the handles to the top or bottom margins to scroll while selecting.
You can also :kbd:`Shift+click` or :kbd:`right click` to extend the selection,
particularly useful for multi-page selections.

You can use the :guilabel:`Highlights` button in the viewer
controls to show a separate panel with a list of all highlights in the book,
sorted by chapter.

You can browse *all highlights* in your entire calibre library by right
clicking the :guilabel:`View` button and choosing :guilabel:`Browse
annotations`.

Finally, if you use the calibre Content server's in browser viewer, you can
have the viewer sync its annotations with the browser viewer by going to
:guilabel:`Preferences->Miscellaneous` in the viewer preferences and entering
the username of the Content server viewer to sync with. Use the special value
``*`` to sync with anonymous users.


Read aloud
------------

The viewer can read book text aloud. To use it you can simply click the
:guilabel:`Read aloud` button in the viewer controls to start reading book text
aloud. The word or sentence being currently read is highlighted. Speech is
synthesized from the text using either the `Piper
<https://github.com/rhasspy/piper>`__ neural text-to-speech engine or your
operating system services for text-to-speech. You can change the backend and
the voice being used by clicking the gear icon in the bar that is displayed
while :guilabel:`Read aloud` is active.

You can also read aloud highlighted passages by adding the :guilabel:`Read aloud` button to
the selection bar in the viewer preferences under :guilabel:`Selection
behavior`.


.. note:: Support for text-to-speech in browsers is very incomplete and
   bug-ridden so how well :guilabel:`Read aloud` will work in the in-browser
   viewer is dependent on how well the underlying browser supports
   text-to-speech.

Searching the text
--------------------------

The viewer has very powerful search capabilities. Press the :kbd:`Ctrl+F` key
or access the viewer controls and click search. The simplest form of searching is
to just search for whatever text you enter in the text box. The different forms
of searching are chosen by the search mode box below the search input.
Available modes are:

#. :guilabel:`Contains` - The simplest default mode. The text entered in the search box
   is searched for anywhere. All punctuation, accents and spaces are ignored.
   For example, the search: ``Pena`` will match all of the following:
   ``penal, pen a, pen.a and Peña``. If you select the :guilabel:`Case sensitive` box
   then accents, spaces and punctuation are no longer ignored.

#. :guilabel:`Whole words` - Searches for whole words. So for example, the search
   ``pena`` will match the word ``Peña`` but not the word ``Penal``. As with
   :guilabel:`Contains` searches above, accents and punctuation are ignored
   unless the :guilabel:`Case sensitive` box is checked.

#. :guilabel:`Nearby words` - Searches for whole words that are near each other. So for example,
   the search ``calibre cool`` will match places where the words ``calibre``
   and ``cool`` occur within sixty characters of each other. To change the
   number of characters add the new number to the end of the list of words. For
   instance, ``calibre cool awesome 120`` will match places where the three
   words occur within 120 characters of each other. Note that punctuation and
   accents are *not* ignored for these searches.

#. :guilabel:`Regex` - Interprets the search text as a *regular expression*.
   To learn more about using regular expressions, see :doc:`the tutorial
   <regexp>`.


Following links using only the keyboard
-----------------------------------------------

The E-book viewer has a :guilabel:`Hints mode` that allows you to click links
in the text without using the mouse. Press the :kbd:`Alt+F` key and all links
in the current screen will be highlighted with a number or letter over them.
Press the letter on your keyboard to click the link. Pressing the :kbd:`Esc`
key will abort the :guilabel:`Hints mode` without selecting any link.

If more than thirty five links are on-screen then some of them will have
multiple letters, in which case type the first and second, or the first and
press :kbd:`Enter` to activate. You can also use the :kbd:`Backspace` key to
undo a mistake in typing.


Customizing the look and feel of your reading experience
------------------------------------------------------------

You can change font sizes on the fly by using :guilabel:`Font size` in the viewer controls or
:kbd:`Ctrl++` or :kbd:`Ctrl+-` or holding the :kbd:`Ctrl` key and using the
mouse wheel.

Colors can be changed in the :guilabel:`Colors` section of the viewer
preferences.

You can change the number of pages displayed on the screen as well as page
margins in :guilabel:`Page layout` in the viewer preferences.

You can display custom headers and footers such as time left to read, current
chapter title, book position, etc. via the :guilabel:`Headers and footers`
section of the viewer preferences.

More advanced customization can be achieved by the :guilabel:`Styles` settings.
Here you can specify a background image to display under the text and also a
stylesheet you can set that will be applied to every book. Using it you can do
things like change paragraph styles, text justification, etc.  For examples of
custom stylesheets used by calibre's users, see `the forums
<https://www.mobileread.com/forums/showthread.php?t=51500>`_.

Dictionary lookup
-------------------

You can look up the meaning of words in the current book by double clicking
or long tapping the word you want to lookup and then clicking the lookup button
that looks like a library.


Copying text and images
-------------------------

You can select text and images by dragging the content with your mouse and then
right clicking and selecting :guilabel:`Copy` to copy to the clipboard.  The copied
material can be pasted into another application as plain text and images.


Zooming in on images
----------------------------

You can zoom in to show an image at full size in a separate window by either
double clicking or long tapping on it. You can also right click on it and
choose :guilabel:`View image`.


Syncing with a paper edition of the current book
----------------------------------------------------

Some e-books, that have corresponding print editions, include metadata that
marks the start of each paper page. For such e-books, the viewer allows you to
jump to a particular paper edition page via the :guilabel:`Go to` button in the
viewer controls. You can also optionally display the paper page corresponding
to the current location in the book's headers or footers via the viewer
settings, by adding :guilabel:`Pages from paper edition` to either the header
or the footer.

.. _viewer_shortcuts:

Keyboard shortcuts
-----------------------

The viewer has extensive keyboard shortcuts, like the rest of calibre. They can
be customised in the viewer :guilabel:`Preferences`. The default shortcuts are listed below:


.. list-table:: Keyboard shortcuts for the calibre E-book viewer
    :widths: 10 100
    :header-rows: 1

    * - Keyboard shortcut
      - Action
    * - :kbd:`Home, Ctrl+ArrowUp, Ctrl+ArrowLeft`
      - Scroll to the start of the current file in a multi file book
    * - :kbd:`Ctrl+Home`
      - Scroll to the beginning of the book
    * - :kbd:`Ctrl+End`
      - Scroll to the end of the book
    * - :kbd:`End, Ctrl+ArrowDown, Ctrl+ArrowRight`
      - Scroll to the end of the current file in a multi file book
    * - :kbd:`ArrowUp`
      - Scroll backwards, smoothly in flow mode and by screen fulls in paged mode
    * - :kbd:`ArrowDown`
      - Scroll forwards, smoothly in flow mode and by screen fulls in paged mode
    * - :kbd:`ArrowLeft`
      - Scroll leftwards by a little in flow mode and by a page in paged mode
    * - :kbd:`ArrowRight`
      - Scroll rightwards by a little in flow mode and by a page in paged mode
    * - :kbd:`PageUp, Shift+Spacebar`
      - Scroll backwards by screen-fulls
    * - :kbd:`PageDown, Spacebar`
      - Scroll forwards by screen-fulls
    * - :kbd:`Ctrl+PageUp`
      - Scroll to the previous section
    * - :kbd:`Ctrl+PageDown`
      - Scroll to the next section
    * - :kbd:`Alt+ArrowLeft`
      - Back
    * - :kbd:`Alt+ArrowRight`
      - Forward
    * - :kbd:`Ctrl+T`
      - Toggle Table of Contents
    * - :kbd:`Ctrl+S`
      - Read aloud
    * - :kbd:`Alt+P`
      - Change settings quickly by creating and switching to :guilabel:`profiles`
    * - :kbd:`Alt+f`
      - Follow links with the keyboard
    * - :kbd:`Ctrl+C`
      - Copy to clipboard
    * - :kbd:`Alt+C`
      - Copy current location to clipboard
    * - :kbd:`Ctrl+Shift+C`
      - Copy current location as calibre:// URL to clipboard
    * - :kbd:`/, Ctrl+f, Cmd+f`
      - Start search
    * - :kbd:`F3, Enter`
      - Find next
    * - :kbd:`Shift+F3, Shift+Enter`
      - Find previous
    * - :kbd:`Ctrl+Plus, Meta+Plus`
      - Increase font size
    * - :kbd:`Ctrl+Minus, Meta+Minus`
      - Decrease font size
    * - :kbd:`Ctrl+0`
      - Restore default font size
    * - :kbd:`Ctrl+]`
      - Increase number of pages per screen
    * - :kbd:`Ctrl+[`
      - Decrease number of pages per screen
    * - :kbd:`Ctrl+Alt+C`
      - Make number of pages per screen automatic
    * - :kbd:`F11, Ctrl+Shift+F`
      - Toggle full screen
    * - :kbd:`Ctrl+M`
      - Toggle between Paged mode and Flow mode for text layout
    * - :kbd:`Ctrl+W`
      - Toggle the scrollbar
    * - :kbd:`Ctrl+X`
      - Toggle the Reference mode
    * - :kbd:`Ctrl+B`
      - Show/hide bookmarks
    * - :kbd:`Ctrl+Alt+B`
      - New bookmark
    * - :kbd:`Ctrl+N, Ctrl+E`
      - Show the book metadata
    * - :kbd:`Ctrl+Alt+F5, Ctrl+Alt+R`
      - Reload book
    * - :kbd:`Ctrl+Shift+ArrowRight`
      - Alter the current selection forward by a word
    * - :kbd:`Ctrl+Shift+ArrowLeft`
      - Alter the current selection backwards by a word
    * - :kbd:`Shift+ArrowRight`
      - Alter the current selection forward by a character
    * - :kbd:`Shift+ArrowLeft`
      - Alter the current selection backwards by a character
    * - :kbd:`Shift+ArrowDown`
      -  Alter the current selection forward by a line
    * - :kbd:`Shift+Home`
      -  Extend the current selection to the start of the line
    * - :kbd:`Shift+End`
      - Extend the current selection to the end of the line
    * - :kbd:`Ctrl+A`
      - Select all
    * - :kbd:`Shift+ArrowUp`
      - Alter the current selection backwards by a line
    * - :kbd:`Ctrl+Shift+ArrowDown`
      - Alter the current selection forward by a paragraph
    * - :kbd:`Ctrl+Shift+ArrowUp`
      - Alter the current selection backwards by a paragraph
    * - :kbd:`Esc, MenuKey`
      - Show the E-book viewer controls
    * - :kbd:`Ctrl+Comma, Ctrl+Esc, Meta+Esc, Meta+Comma`
      - Show E-book viewer preferences
    * - :kbd:`Ctrl+G, ;, :`
      - Go to a specified book location or position
    * - :kbd:`Ctrl+Spacebar`
      - Toggle auto-scroll
    * - :kbd:`Alt+ArrowUp`
      - Auto scroll faster
    * - :kbd:`Alt+ArrowDown`
      - Auto scroll slower
    * - :kbd:`Ctrl+I`
      - Show/hide Inspector
    * - :kbd:`Ctrl+L`
      -  Show/hide the word lookup panel
    * - :kbd:`Ctrl+Q (Cmd+Q on macOS)`
      - Quit
    * - :kbd:`Ctrl+P`
      - Print book to PDF
    * - :kbd:`Ctrl+F11`
      - Toggle the toolbar
    * - :kbd:`Ctrl+H`
      - Toggle the highlights panel
    * - :kbd:`Ctrl+D`
      - Edit this book

Non re-flowable content
--------------------------

Some books have very wide content that cannot be broken up at page boundaries.
For example tables or :code:`<pre>` tags. In such cases, you should switch the
viewer to *flow mode* by pressing :kbd:`Ctrl+M` to read this content.
Alternately, you can also add the following CSS to the :guilabel:`Styles` section of the
viewer preferences to force the viewer to break up lines of text in
:code:`<pre>` tags::

    code, pre { white-space: pre-wrap }


Designing your book to work well with the calibre E-book viewer
-----------------------------------------------------------------

The calibre E-book viewer will set the ``is-calibre-viewer`` class on the root
element. So you can write CSS rules that apply only for it. Additionally,
the viewer will set the following classes on the ``body`` element:

``body.calibre-viewer-dark-colors``
    Set when using a dark color scheme

``body.calibre-viewer-light-colors``
    Set when using a light color scheme

``body.calibre-viewer-paginated``
    Set when in paged mode

``body.calibre-viewer-scrolling``
    Set when in flow (non-paginated) mode

``body.calibre-footnote-container``
    Set when displaying a popup footnote

Finally, you can use the calibre color scheme colors via `CSS variables
<https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties>`_.
The calibre E-book viewer defines the following variables:
``--calibre-viewer-background-color``, ``--calibre-viewer-foreground-color``
and optionally ``--calibre-viewer-link-color`` in color themes that define
a link color.
