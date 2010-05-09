#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Contains various tweaks that affect calibre behavior. Only edit this file if
you know what you are dong. If you delete this file, it will be recreated from
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
author_sort_copy_method = 'invert'


# Set whether boolean custom columns are two- or three-valued.
#  Two-values for true booleans
#  three-values for yes/no/unknown
# Set to 'yes' for three-values, 'no' for two-values
bool_custom_columns_are_tristate = 'yes'


# Provide a set of columns to be sorted on when calibre starts
#  The argument is None of saved sort history is to be used
#  otherwise it is a list of column,order pairs. Column is the
#  lookup/search name, found using the tooltip for the column
#  Order is 0 for ascending, 1 for descending
# For example, set it to [('authors',0),('title',0)] to sort by
# title within authors.
sort_columns_at_startup = None

# Format to be used for publication date
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
# default if not set: MMM yyyy
gui_pubdate_display_format = 'MMM yyyy'

