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
  - On a touchscreen by tapping the top 1/3rd or the screen


The viewer has two modes, "paged" and "flow". In paged mode the book content
is presented as pages, similar to a paper book. In flow mode the text is
presented continuously, like in a web browser. You can switch between them
using the viewer Preferences under :guilabel:`Page layout` or by pressing the
:kbd:`ctrl+m` key.


Bookmarks
^^^^^^^^^^^^

When you are in the middle of a book and close the viewer, it will remember
where you stopped reading and return there the next time you open the book. You
can also set bookmarks in the book by using the :guilabel:`Bookmarks` button in
the viewer controls or pressing :kbd:`ctrl+b`.  When viewing EPUB format books,
these bookmarks are actually saved in the EPUB file itself. You can add
bookmarks, then send the file to a friend.  When they open the file, they will
be able to see your bookmarks. You can turn off this behavior in the
:guilabel:`Miscellaneous` section of the viewer preferences.


Table of Contents
^^^^^^^^^^^^^^^^^^^^

If the book you are reading defines a Table of Contents, you can access it by
pressing the :guilabel:`Table of Contents` button.  This will bring up a list
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

If you click on links inside the e-book to take you to different parts of the
book, such as an endnote, you can use the :guilabel:`Back` and
:guilabel:`Forward` buttons in the top left corner of the viewer controls.
These buttons behave just like those in a web browser.

Reference mode
^^^^^^^^^^^^^^^^^

calibre also has a very handy :guilabel:`Reference mode`.  You can turn it on
by clicking the :guilabel:`Reference mode` button in the viewer controls.  Once
you do this, every mouse over a paragraph, calibre will display a unique number
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
mode you can tap the :guilabel:`Adjust selection` button to change what text is
selected using touch screen friendly selection handles.  Drag
the handles to the top or bottom margins to scroll while selecting.

You can use the :guilabel:`Browse highlights` button in the viewer
controls to show a separate panel with a list of all highlights in the book.

You can browse *all highlights* in your entire calibre library by going to
:guilabel:`Preferences->Toolbars` in calibre and adding the :guilabel:`Browse
annotations` tool to the toolbar.


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

You can look up the meaning of words in the current book by opening the
:guilabel:`Lookup/search word panel` via the viewer controls. Then simply double
click on any word and its definition will be displayed in the Lookup panel.


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


Non re-flowable content
--------------------------

Some books have very wide content that content be broken up at page boundaries.
For example tables or :code:`<pre>` tags. In such cases, you should switch the
viewer to *flow mode* by pressing :kbd:`Ctrl+m` to read this content.
Alternately, you can also add the following CSS to the :guilabel:`Styles` section of the
viewer preferences to force the viewer to break up lines of text in
:code:`<pre>` tags::

    code, pre { white-space: pre-wrap }
