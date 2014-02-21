.. include:: global.rst

.. _edit:

Editing E-books 
========================

|app| has an integrated e-book editor that can be used to edit books in the
EPUB and AZW3 (Kindle) formats. The editor shows you the HTML and CSS that is
used internally inside the book files, with a live preview that updates as you
make changes. It also contains various automated tools to perform common
cleanup and fixing tasks.

You can use this editor by right clicking on any book in |app| and selecting
:guilabel:`Edit book`.

.. image:: images/edit-book.png
    :alt: The Edit Book tool
    :align: center
    :class: fit-img

.. contents:: Contents
  :depth: 2
  :local:


Basic workflow
---------------

When you first open a book with the Edit book tool, you will be presented with
a list of files on the left. These are the individual HTML files, stylesheets,
images, etc. that make up the content of the book. Simply double click on a
file to start editing it. Note that if you want to do anything more
sophisticated than making a few small tweaks, you will need to know `HTML
Tutorial <http://html.net/tutorials/html/>`_ and `CSS Tutorial
<http://html.net/tutorials/css/>`_.

As you make changes to the HTML or CSS in the editor, the changes will be
previewed, live, in the preview panel to the right. When you are happy with how
the changes you have made look, click the Save button or use
:guilabel:`File->Save` to save your changes into the ebook. 

One useful feature is :guilabel:`Checkpoints`. Before you embark on some
ambitious set of edits, you can create a checkpoint. The checkpoint
will preserve the current state of your book, then if in the future you decide
you dont like the changes you have made to you can go back to the state when
you created the checkpoint. To create a checkpoint, use :guilabel:`Edit->Create
checkpoint`. Checkpoints will also be automatically created for you whenever you
run any automated tool like global search and replace. The checkpointing
functionality is in addition to the normal Undo/redo mechanism when editing
individual files. Checkpoints are useful for when changes are spread over
multiple files in the book.

That is the basic work flow for editing books -- Open a file, make changes,
preview and save. The rest of this manual will discuss the various tools and
features present to allow you to perform specific tasks efficiently.

The Files Browser
------------------

.. image:: images/files_browser.png
    :alt: The Files Browser
    :class: float-left-img

The :guilabel:`Files Browser` gives you an overview of the various files inside
the book you are editing. The files are arranged by category, with text (HTML)
files at the top, followed by stylesheet (CSS) files, images and so on. Simply
double click on a file to start editing it. Editing is supported for HTML, CSS
and image files. The order of text files is the same order that they would be
displayed in, if you were reading the book. All other files are arranged
alphabetically.

By hovering your mouse over an entry, you can see its size, and also, at
the bottom of the screen, the full path to the file inside the book. Note that
files inside ebooks are compressed, so the size of the final book is not the
sum of the individual file sizes.

Many files have special meaning, in the book. These will typically have
an icon next to their names, indicating the special meaning. For example, in
the picture to the left, you can see that the files :guilabel:`cover_image.jpg`
and :guilabel:`titlepage.xhtml` have the ocon of a cover next to them, this
indicates they are the book cover image and titlepage. Similarly, the
:guilabel:`content.opf` file has a metadata icon next to it, indicating the
book metadata is present in it and the the :guilabel:`toc.ncx` file has a T
icon next to it, indicating it is the Table of Contents.

You can perform many actions on individual files, by right clicking them.

Renaming files
^^^^^^^^^^^^^^^

You can rename an individual file by right clicking it and selecting
:guilabel:`Rename`. Renaming a file automatically updates all links and
references to it throughout the book. So all you have to do is provide the new
name, |app| will take care of the rest.

You can also bulk rename many files at once. This is useful
if you want the files to have some simple name pattern. For example you might
want to rename all the HTML files to have names Chapter-1.html, Chapter-2.html
and so on. Select the files you want bulk renamed by holding down the Shift or
Ctrl key and clicking the files. Then right click and select :guilabel:`Bulk
rename`. Enter a prefix and what number you would like the automatic numbering
to start at, click OK and you are done.

Merging files
^^^^^^^^^^^^^^

Sometimes, you may want to merge two HTML files or two CSS files together. It
can sometimes be useful to have everything in a single file. Be wary, though,
putting a lot of content into a single file will cause performance problems
when viewing the book in a typical ebook reader.

To merge multiple files together, select them by holding the Ctrl key and
clicking on them (make sure you only select files of one type, either all HTML
files or all CSS files and so on). Then right click and select merge. That's
all, |app| will merge the files, automatically taking care of migrating all
links and references to the merged files. Note that merging files can sometimes
cause text styling to change, since the individual files could have used
different stylesheets.

Changing text file order
^^^^^^^^^^^^^^^^^^^^^^^^^^

You can re-arrange the order in which text (HTML) files are opened when reading
the book by simply dragging and dropping them in the Files browser. For the
technically inclined, this is called re-ordering the book spine.

Marking the cover
^^^^^^^^^^^^^^^^^^^^^^^^^^^

E-books typically have a cover image. This image is indicated in the Files
Browser by the icon of a brown book next to the image name. If you want to
designate some other image as the cover, you can do so by right clicking on the
file and choosing :guilabel:`Mark as cover`.

In addition, EPUB files has the concept of a *titlepage*. A title page is a
HTML file that acts as the title page/cover for th book. You can mark an HTML
file as the titlepage when editing EPUBs by right-clicking. Be careful that the
file you mark contains only the cover information. If it contains other
content, such as the first chapter, then that content will be lost if the user
ever converts the EPUB file in |app| to another format. This is because when
converting, |app| assumes that the marked title page contains only the cover
and no other content.

Deleting files
^^^^^^^^^^^^^^^^

You can delete files by either right clicking on them or by selecting them and
pressing the Delete key. Deleting a file removes all references to the file
from the OPF file, saving you that chore. However, references in other places
are not removed, you can use the Check Book tool to easily find and
remove/replace them.

Export of files
^^^^^^^^^^^^^^^^^^^^^^^^

You can export a file from inside the book to somewhere else on your computer.
This is useful if you want to work on the file in isolation, with specialised
tools. To do this, simply right click on the file and choose
:guilabel:`Export`. 

Once you are done working on the exported file, you can re-import it into the
book, by right clicking on the file again and choosing :guilabel:`Replace with
file...` which will allow you to replace the file in the book with
the previously exported file.

Adding new images/fonts/etc. or creating new blank files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can add a new image, font, stylesheet, etc. from your computer into the
book by clicking :guilabel:`File->New file`. This lets you either import a file
by clicking the :guilabel:`Import resource file` button or create a new blank html file
or stylesheet by simply entering the file name into the box for the new file.

You can also import multiple files into the book at once using File->Import
files into book.

Replacing files
^^^^^^^^^^^^^^^^

You can easily replace existing files int he book, by right clicking on the
file and choosing replace. This will automatically update all links and
references, in case the replacement file has a different name than the file
being replaced.

Linking stylesheets to HTML files efficiently
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As a convenience, you can select multiple HTML files in the Files Browser,
right click and choose Link stylesheets to have |app| automatically insert the
<link> tags for those stylesheets into all the selected HTML files.

Search & Replace
-------------------

Edit Book has a very powerful search and replace interface that allows you to
search and replace text in the current file, across all files and even in a
marked region of the current file. You can search using a normal search or
using regular expressions. To learn how to use regular expressions for advanced
searching, see :ref:`regexptutorial`.

.. image:: images/sr.png
    :alt: The Edit Book tool
    :align: center

Start the search and replace via the :guilabel:`Search->Find/replace` menu
entry (you must be editing an HTML or CSS file).  

Type the text you want to find into the Find box and its replacement into the
Replace box. You can the click the appropriate buttons to Find the next match,
replace the current match and replace all matches. 

Using the drop downs at the bottom of the box, you can have the search operate
over the current file, all text files, all style files or all files. You can
also choose the search mode to be a normal (string) search or a regular
expression search. 

You can count all the matches for a search expression via
:guilabel:`Search->Count all`. The count will run over whatever files/regions
you have selected in the dropdown box.

You can also go to a specific line in the currently open editor via
:guilabel:`Search->Go to line`.

.. note:: 
    Remember, to harness the full power of search and replace, you will
    need to use regular expressions. See :ref:`regexptutorial`.

Automated tools
-------------------

Edit book has various tools to help with common tasks. These are
accessed via the :guilabel:`Tools` menu.

Edit the Table of Contents
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There is a dedicated tool to ease editing of the Table of Contents. Launch it
with :guilabel:`Tools->Table of Contents->Edit Table of Contents`. 

.. image:: images/tocedit.png
    :alt: The Edit Table of Contents tool
    :align: center

The Edit Table of Contents tool shows you the current Table of Contents (if
any) on the left. Simply double click on any entry to change its text. You can
also re-arrange entries by drag and drop or by using the buttons to the right.

For books that do not have a pre-existing Table of Contents, the tool gives you
various options to auto-generate a Table of Contents from the text. You can
generate from the headings in the document, from links, from individual files
and so on. 

You can edit individual entries by clicking on them and then clicking the
:guilabel:`Change the location this entry points to` button. This will open up
a mini-preview of the book, simply move the mouse cursor over the book view
panel, and click where you want the entry to point to. A thick green line
will show you the location. Click OK once you are happy with the location. 

.. image:: images/tocedit-location.png
    :alt: The Edit Table of Contents tool, how to change the location an entry points to
    :align: center

Check Book
^^^^^^^^^^^^^

The :guilabel:`Check Book` tool searches your book for problems that could
prevent it working as intended on actual reader devices. Activate it via
:guilabel:`Tools->Check Book`.

.. image:: images/check-book.png
    :alt: The Check Book tool
    :align: center

Any problems found are
reported in a nice, easy to use list. Clicking any entry in the list shows you
some help about that error as well as giving you the option to auto-fix that
error, if the error can be fixed automatically. You can also double click the
error to open the location of the error in an editor, so you can fix it
yourself.

Some of the checks performed are:

    * Malformed HTML markup. Any HTML markup that does not parse as well-formed
      XML is reported. Correcting it will ensure that your markup works as
      intended in all contexts. |app| can also auto-fix these errors, but
      auto-fixing can sometimes have unexpected effects, so use with care. As
      always, a checkpoint is created before auto-fixing so you can easily
      revert all changes. Auto-fixing works by parsing the markup using the
      HTML 5 algorithm, which is highly fault tolerant and then converting to
      well formed XML.

    * Malformed or unknown CSS styles. Any CSS that is not valid or that has
      properties not defined in the CSS 2.1 standard (plus a few from CSS 3)
      are reported. CSS is checked in all stylesheets, inline style attributes
      and <style> tags in HTML files.

    * Broken links. Links that point to files inside the book that are missing
      are reported.

    * Unreferenced files. Files in the book that are not referenced by any
      other file or are not in the spine are reported.

    * Various common problems in OPF files such as duplicate spine or manifest
      items, broken idrefs or meta cover tags, missing required sections and
      so on.

    * Various compatibility checks for known problems that can cause the book
      to malfunction on reader devices.

Embedding referenced fonts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Accessed via :guilabel:`Tools->Embed reference fonts`, this tool finds all
fonts referenced in the book and if they are not already embedded, searches
your computer for them and embeds them into the book, if found. Please make
sure that you have the necessary copyrights for embedding commercially licensed
fonts, before doing this.

Subsetting embedded fonts
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Accessed via :guilabel:`Tools->Subset embedded fonts`, this tool reduces all
the fonts in the book to only contain glyphs for the text actually present in
the book. This commonly reduces the size of the font files by ~ 50%. However,
be aware that once the fonts are subset, if you add new text whose characters
are not previously present in the subset font, the font will not work for the
new text. So do this only as the last step in your workflow.

Smartening punctuation
^^^^^^^^^^^^^^^^^^^^^^^^^

Convert plain text dashes, ellipsis, quotes, multiple hyphens, etc. into their
typographically correct equivalents.
Note that the algorithm can sometimes generate incorrect results, especially
when single quotes at the start of contractions are involved. Accessed via
:guilabel:`Tools->Smarten punctuation`.

Removing unused CSS rules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Remove all unused CSS rules from stylesheets and <style> tags. Some books
created from production templates can have a large number of extra CSS rules
that dont match any actual content. These extra rules can slow down readers
that need to process them all. Accessed via :guilabel:`Tools->Remove unused CSS`.


Fix HTML
^^^^^^^^^^^

This tool simply converts HTML that cannot be parsed as XML into well-formed
XML. It is very common in ebooks to have non-well-formed XML, so this tool
simply automates the process of fixing such HTML. The tool works by parsing the
HTML using the HTML 5 algorithm (the algorithm used in all modern browsers) and
then converting the result into XML. Be aware that auto-fixing can sometimes
have counter-intuitive results. If you prefer, you can use the Check Book tool
discussed above to find and manually correct problems in the HTML. Accessed via
:guilabel:`Tools->Fix HTML`.

Beautifying files
^^^^^^^^^^^^^^^^^^^

This tool is used to auto-format all HTML and CSS files so that they "look
pretty". The code is auto-indented so that it lines up nicely, blank lines are
inserted where appropriate and so on. Note that beautifying also auto-fixes
broken HTML/CSS. Therefore, if you dont want any auto-fixing to be performed,
first use the Check Book tool to correct all problems and only then run
beautify.  Accessed via :guilabel:`Tools->Beautify all files`.


Insert inline Table of Contents
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Normally in ebooks, the Table of Contents is separate from the main text and is
typically accessed via a special Table of Contents button/menu in the ebook
reading device. You can also have |app| automatically generate an *inline*
Table of Contents that becomes part of the text of the book. It is
generated based on the currently defined Table of Contents. 

If you use this tool multiple times, each invocation will cause the previously
created inline Table of Contents to be replaced. The tool can be accessed via
:guilabel:`Tools->Table of Contents->Insert inline Table of Contents`.

.. _checkpoints:

Checkpoints
------------------------

:guilabel:`Checkpoints` are a way to mark the current state of the book as "special". You
can then go on to do whatever changes you want to the book and if you dont like
the results, return to the checkpointed state. Checkpoints are automatically
created every time you run any of the automated tools described in the
previous section.

You can create a checkpoint via :guilabel:`Edit->Create checkpoint`. And go back
to a previous checkpoint with :guilabel:`Edit->Revert to ...`

The checkpointing functionality is in addition to the normal Undo/redo
mechanism when editing individual files. Checkpoints are particularly useful
for when changes are spread over multiple files in the book or when you wish to
be able to revert a large group of related changes as a whole.

You can see a list of available checkpoints via :guilabel:`View->Checkpoints`.
You can compare the current state of the book to a specified checkpoint
using the :ref:`diff` tool -- by selecting the checkpoint of interest and clicking
the :guilabel:`Compare` button. The :guilabel:`Revert to` button restores the
book to the selected checkpoint, undoing all changes since that checkpoint was
created.

The Live Preview panel
------------------------

.. image:: images/live-preview.png
    :alt: The Live Preview Panel
    :class: float-left-img

The :guilabel:`File Preview` gives you an overview of the various files inside
The live preview panel shows you the changes you are making live (with a second
or two of delay). As you edit HTML or CSS files, the preview panel is updated
automatically to reflect your changes. As you move the cursor around in the
editor, the preview panel will track its location, showing you the
corresponding location in the book. Clicking in the preview panel, will cause
the cursor in the editor to be positioned over the element you clicked. If you
click a link pointing to another file in the book, that file will be opened in
the edit and the preview panel, automatically.

You can turn off the automatic syncing of position and live preview of changes
-- by buttons under the preview panel. The live update of the preview
panel only happens when you are not actively typing in the editor, so as not to
be distracting or slow you down, waiting for the preview to render.

The preview panel shows you how the text will look when viewed. However, the
preview panel is not a substitute for actually testing your book an actual
reader device. It is both more, and less capable than an actual reader. It will
tolerate errors and sloppy markup much better than most reader devices. It will
also not show you page margins, page breaks and embedded fonts that use font
name aliasing. Use the preview panel while you are working on the book, but
once you are done, review it in an actual reader device or software emulator.

.. note::
    The preview panel does not support embedded fonts if the name of the font
    inside the font file does not match the name in the CSS @font-face rule.
    You can use the Check Book tool to quickly find and fix any such
    problem fonts.

Splitting HTML files
^^^^^^^^^^^^^^^^^^^^^^

.. |spmb| image:: images/split-button.png

One, perhaps non-obvious, use of the preview panel is to split long HTML files.
While viewing the file you want to split, click the :guilabel:`split mode`
button under the preview panel |spmb|. Then simply move your mouse to the place
where you want to split the file and click. A thick green line will show you
exactly where the split will happen as you move your mouse. Once you have found
the location you want, simply click and the split will be performed. 

Splitting the file will automatically update all links and references that
pointed into the bottom half of the file and will open the newly split file in
an editor. 

You can also split a single HTML file at multiple locations automatically, by
right clicking inside the file in the editor and choosing :guilabel:`Split at
multiple locations`. This will allow you to easily split a large file at all
heading tags or all tags having a certain class and so on.


Miscellaneous Tools
----------------------

There are a few more tools that can be useful while you edit the book. 

The Table of Contents View
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Table of Contents view shows you the current table of contents in the book.
Double clicking on any entry opens the place that entry points to in an editor.
You can right click to edit the Table of Contents, refresh the view or
expand/collapse all items. Access this view via :guilabel:`Views->Table of
Contents`.

Inserting special characters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can insert characters that are difficult to type by using the
:guilabel:`Edit->Insert special character` tool. This shows you all unicode
characters, simply click on the character you want to type. If you hold Ctrl
while clicking, the window will close itself after inserting the selected
character. This tool can be used to insert special characters into the main
text or into any other area of the user interface, such as the Search and
replace tool.

Because there are a lot of characters, you can define your own :guilabel:`Favorite`
characters, that will be shown first. Simply right click on a character to mark
it as favorite. You can also right click on a character in favorites to remove
it from favorites. Finally, you can re-arrange the order of characters in
favorites by clicking the :guilabel:`Re-arrange favorties` button and then drag
and dropping the characters in favorites around.

You can also directly type in special characters using the keyboard. To do
this, you type the unicode code for the character (in hexadecimal) and then
press the :guilabel:`Alt+X` key which will convert the previously typed code
into the corresponding character. For example, to type ÿ you would type ff and
then Alt+X. To type a non-breaking space you would use a0 and then
:guilabel:`Alt+X`, to type the horizontal ellipsis you would use 2026 and
:guilabel:`Alt+X` and so on.

Finally, you can type in special characters by using HTML named entities. For
example, typing &nbsp; will be replaced by a non breaking space when you type the
semi-colon. The replacement happens only when typing the semi-colon.

The code inspector view
^^^^^^^^^^^^^^^^^^^^^^^^^^

This view shows you the HTML coding and CSS that applies to the current element
of interest. You open it by right clicking a location in the preview panel and
choosing :guilabel:`Inspect`. It allows you to see the HTML coding for that
element and more importantly, the CSS styles that apply to it. You can even
dynamically edit the styles and see what effect your changes have instantly.
Note that editing the styles does not actually make changes to the book
contents, it only allows for quick experimentation. The ability to live edit
inside the Inspector is under development.

Arrange files into folders by type
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Often when editing EPUB files that you get from somewhere, you will find that
the files inside the EPUB are arranged haphazardly, in different sub-folders.
This tool allows you to automatically move all files into sub-folders based on
their types. Access it via :guilabel:`Tools->Arrange into folders`. Note that
this tool only changes how the files are arranged inside the EPUB, it does not
change how they are displayed in the Files Browser.
