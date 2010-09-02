#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Contains various tweaks that affect calibre behavior. Only edit this file if
you know what you are doing. If you delete this file, it will be recreated from
defaults.
'''


# The algorithm used to assign a new book in an existing series a series number.
# Possible values are:
# next - Next available number
# const - Assign the number 1 always
series_index_auto_increment = 'next'



# The algorithm used to copy author to author_sort
# Possible values are:
#  invert: use "fn ln" -> "ln, fn" (the original algorithm)
#  copy  : copy author to author_sort without modification
#  comma : use 'copy' if there is a ',' in the name, otherwise use 'invert'
#  nocomma : "fn ln" -> "ln fn" (without the comma)
author_sort_copy_method = 'invert'


# Set whether boolean custom columns are two- or three-valued.
#  Two-values for true booleans
#  three-values for yes/no/unknown
# Set to 'yes' for three-values, 'no' for two-values
bool_custom_columns_are_tristate = 'yes'


# Provide a set of columns to be sorted on when calibre starts
#  The argument is None if saved sort history is to be used
#  otherwise it is a list of column,order pairs. Column is the
#  lookup/search name, found using the tooltip for the column
#  Order is 0 for ascending, 1 for descending
# For example, set it to [('authors',0),('title',0)] to sort by
# title within authors.
sort_columns_at_startup = None

# Format to be used for publication date and the timestamp (date).
#  A string controlling how the publication date is displayed in the GUI
#  d    the day as number without a leading zero (1 to 31)
#  dd    the day as number with a leading zero (01 to 31)
#  ddd    the abbreviated localized day name (e.g. 'Mon' to 'Sun').
#  dddd    the long localized day name (e.g. 'Monday' to 'Qt::Sunday').
#  M    the month as number without a leading zero (1-12)
#  MM    the month as number with a leading zero (01-12)
#  MMM    the abbreviated localized month name (e.g. 'Jan' to 'Dec').
#  MMMM    the long localized month name (e.g. 'January' to 'December').
#  yy    the year as two digit number (00-99)
#  yyyy    the year as four digit number
#  For example, given the date of 9 Jan 2010, the following formats show
#  MMM yyyy ==> Jan 2010    yyyy ==> 2010       dd MMM yyyy ==> 09 Jan 2010
#  MM/yyyy ==> 01/2010      d/M/yy ==> 9/1/10   yy ==> 10
# publication default if not set: MMM yyyy
# timestamp default if not set: dd MMM yyyy
gui_pubdate_display_format = 'MMM yyyy'
gui_timestamp_display_format = 'dd MMM yyyy'

# Control title and series sorting in the library view.
# If set to 'library_order', Leading articles such as The and A will be ignored.
# If set to 'strictly_alphabetic', the titles will be sorted without processing
# For example, with library_order, The Client will sort under 'C'. With
# strictly_alphabetic, the book will sort under 'T'.
# This flag affects Calibre's library display. It has no effect on devices. In
# addition, titles for books added before changing the flag will retain their
# order until the title is edited. Double-clicking on a title and hitting return
# without changing anything is sufficient to change the sort.
title_series_sorting = 'library_order'

# Control how title and series names are formatted when saving to disk/sending
# to device. If set to library_order, leading articles such as The and A will
# be put at the end
# If set to 'strictly_alphabetic', the titles will be sorted without processing
# For example, with library_order, "The Client" will become "Client, The". With
# strictly_alphabetic, it would remain "The Client".
save_template_title_series_sorting = 'library_order'

# Specify a folder that calibre should connect to at startup using
# connect_to_folder. This must be a full path to the folder. If the folder does
# not exist when calibre starts, it is ignored. If there are '\' characters in
# the path (such as in Windows paths), you must double them.
# Examples:
#     auto_connect_to_folder = 'C:\\Users\\someone\\Desktop\\testlib'
#     auto_connect_to_folder = '/home/dropbox/My Dropbox/someone/library'
auto_connect_to_folder = ''


# Create search terms to apply a query across several built-in search terms.
# Syntax: {'new term':['existing term 1', 'term 2', ...], 'new':['old'...] ...}
# Example: create the term 'myseries' that when used as myseries:foo would
# search all of the search categories 'series', '#myseries', and '#myseries2':
# grouped_search_terms={'myseries':['series','#myseries', '#myseries2']}
# Example: two search terms 'a' and 'b' both that search 'tags' and '#mytags':
# grouped_search_terms={'a':['tags','#mytags'], 'b':['tags','#mytags']}
# Note: You cannot create a search term that is a duplicate of an existing term.
# Such duplicates will be silently ignored. Also note that search terms ignore
# case. 'MySearch' and 'mysearch' are the same term.
grouped_search_terms = {}


# Set this to True (not 'True') to ensure that tags in 'Tags to add when adding
# a book' are added when copying books to another library
add_new_book_tags_when_importing_books = False

