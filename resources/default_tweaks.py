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
# New series numbers assigned using this tweak are always integer values, except
# if a constant non-integer is specified.
# Possible values are:
# next - First available integer larger than the largest existing number
# first_free - First available integer larger than 0
# next_free - First available integer larger than the smallest existing number
# last_free - First available integer smaller than the largest existing number
#             Return largest existing + 1 if no free number is found
# const - Assign the number 1 always
# a number - Assign that number always. The number is not in quotes. Note that
#            0.0 can be used here.
# Examples:
# series_index_auto_increment = 'next'
# series_index_auto_increment = 'next_free'
# series_index_auto_increment = 16.5
series_index_auto_increment = 'next'


# The algorithm used to copy author to author_sort
# Possible values are:
#  invert: use "fn ln" -> "ln, fn" (the original algorithm)
#  copy  : copy author to author_sort without modification
#  comma : use 'copy' if there is a ',' in the name, otherwise use 'invert'
#  nocomma : "fn ln" -> "ln fn" (without the comma)
# When this tweak is changed, the author_sort values stored with each author
# must be recomputed by right-clicking on an author in the left-hand tags pane,
# selecting 'manage authors', and pressing 'Recalculate all author sort values'.
author_sort_copy_method = 'invert'

# Set which author field to display in the tags pane (the list of authors,
# series, publishers etc on the left hand side). The choices are author and
# author_sort. This tweak affects only what is displayed under the authors
# category in the tags pane and content server. Please note that if you set this
# to author_sort, it is very possible to see duplicate names in the list because
# although it is guaranteed that author names are unique, there is no such
# guarantee for author_sort values. Showing duplicates won't break anything, but
# it could lead to some confusion. When using 'author_sort', the tooltip will
# show the author's name.
# Examples:
#   categories_use_field_for_author_name = 'author'
#   categories_use_field_for_author_name = 'author_sort'
categories_use_field_for_author_name = 'author'


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

# Set the list of words that are to be considered 'articles' when computing the
# title sort strings. The list is a regular expression, with the articles
# separated by 'or' bars. Comparisons are case insensitive, and that cannot be
# changed. Changes to this tweak won't have an effect until the book is modified
# in some way. If you enter an invalid pattern, it is silently ignored.
# To disable use the expression: '^$'
# Default: '^(A|The|An)\s+'
title_sort_articles=r'^(A|The|An)\s+'


# Specify a folder that calibre should connect to at startup using
# connect_to_folder. This must be a full path to the folder. If the folder does
# not exist when calibre starts, it is ignored. If there are '\' characters in
# the path (such as in Windows paths), you must double them.
# Examples:
#     auto_connect_to_folder = 'C:\\Users\\someone\\Desktop\\testlib'
#     auto_connect_to_folder = '/home/dropbox/My Dropbox/someone/library'
auto_connect_to_folder = ''


# Specify renaming rules for sony collections. This tweak is only applicable if
# metadata management is set to automatic. Collections on Sonys are named
# depending upon whether the field is standard or custom. A collection derived
# from a standard field is named for the value in that field. For example, if
# the standard 'series' column contains the name 'Darkover', then the series
# will be named 'Darkover'. A collection derived from a custom field will have
# the name of the field added to the value. For example, if a custom series
# column named 'My Series' contains the name 'Darkover', then the collection
# will be named 'Darkover (My Series)'. If two books have fields that generate
# the same collection name, then both books will be in that collection. This
# tweak lets you specify for a standard or custom field the value to be put
# inside the parentheses. You can use it to add a parenthetical description to a
# standard field, for example 'Foo (Tag)' instead of the 'Foo'. You can also use
# it to force multiple fields to end up in the same collection. For example, you
# could force the values in 'series', '#my_series_1', and '#my_series_2' to
# appear in collections named 'some_value (Series)', thereby merging all of the
# fields into one set of collections. The syntax of this tweak is
# {'field_lookup_name':'name_to_use', 'lookup_name':'name', ...}
# Example 1: I want three series columns to be merged into one set of
# collections. If the column lookup names are 'series', '#series_1' and
# '#series_2', and if I want nothing in the parenthesis, then the value to use
# in the tweak value would be:
# sony_collection_renaming_rules={'series':'', '#series_1':'', '#series_2':''}
# Example 2: I want the word '(Series)' to appear on collections made from
# series, and the word '(Tag)' to appear on collections made from tags. Use:
# sony_collection_renaming_rules={'series':'Series', 'tags':'Tag'}
# Example 3: I want 'series' and '#myseries' to be merged, and for the
# collection name to have '(Series)' appended. The renaming rule is:
# sony_collection_renaming_rules={'series':'Series', '#myseries':'Series'}
sony_collection_renaming_rules={}


# Specify how sony collections are sorted. This tweak is only applicable if
# metadata management is set to automatic. You can indicate which metadata is to
# be used to sort on a collection-by-collection basis. The format of the tweak
# is a list of metadata fields from which collections are made, followed by the
# name of the metadata field containing the sort value.
# Example: The following indicates that collections built from pubdate and tags
# are to be sorted by the value in the custom column '#mydate', that collections
# built from 'series' are to be sorted by 'series_index', and that all other
# collections are to be sorted by title. If a collection metadata field is not
# named, then if it is a series- based collection it is sorted by series order,
# otherwise it is sorted by title order.
# [(['pubdate', 'tags'],'#mydate'), (['series'],'series_index'), (['*'], 'title')]
# Note that the bracketing and parentheses are required. The syntax is
# [ ( [list of fields], sort field ) , ( [ list of fields ] , sort field ) ]
# Default: empty (no rules), so no collection attributes are named.
sony_collection_sorting_rules = []

# Specify whether special collections are to be made. This option is primarily
# of use on a Sony. The two available are all_by_author and all_by_title. These
# collections work around various device idiosyncrasies regarding sorting of
# lists, especially the sony *50 models. The author collection is sorted by
# author(s) then title. The title collection is sorted by title then authors(s)
# Enable a collection by entering a collection name in the variable. That
# collection name must be unique.
# Examples:
# device_special_collections = {'title':'', 'author':'%All by author'}
#    create a collection named '%All by author' of all books sorted by author
# device_special_collections = {'title':'%All by title', 'author':''}
#    create a collection named '%All by title' of books sorted by title,
#    respecting the order tweaks
# device_special_collections = {'title':'%All by title', 'author':'%All by author'}
#    make both collections
# sony_all_books_by_author_collection = {'title':'', 'author':''}
#    disable both collections
device_special_collections = {'title':'', 'author':''}


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


# Set the maximum number of tags to show per book in the content server
max_content_server_tags_shown=5

# Set custom metadata fields that the content server will or will not display.
# content_server_will_display is a list of custom fields to be displayed.
# content_server_wont_display is a list of custom fields not to be displayed.
# wont_display has priority over will_display.
# The special value '*' means all custom fields. The value [] means no entries.
# Defaults:
#    content_server_will_display = ['*']
#    content_server_wont_display = []
# Examples:
# To display only the custom fields #mytags and #genre:
#   content_server_will_display = ['#mytags', '#genre']
#   content_server_wont_display = []
# To display all fields except #mycomments:
#   content_server_will_display = ['*']
#   content_server_wont_display['#mycomments']
content_server_will_display = ['*']
content_server_wont_display = []

# Same as above (content server) but for the book details pane. Same syntax.
# As above, this tweak affects only display of custom fields. The standard
# fields are not affected
book_details_will_display = ['*']
book_details_wont_display = []


# Set the maximum number of sort 'levels' that calibre will use to resort the
# library after certain operations such as searches or device insertion. Each
# sort level adds a performance penalty. If the database is large (thousands of
# books) the penalty might be noticeable. If you are not concerned about multi-
# level sorts, and if you are seeing a slowdown, reduce the value of this tweak.
maximum_resort_levels = 5

# Absolute path to a TTF font file to use as the font for the title and author
# when generating a default cover. Useful if the default font (Liberation
# Serif) does not contain glyphs for the language of the books in your library.
generate_cover_title_font = None

# Absolute path to a TTF font file to use as the font for the footer in the
# default cover
generate_cover_foot_font = None


# Behavior of doubleclick on the books list. Choices:
# open_viewer, do_nothing, edit_cell. Default: open_viewer.
# Example: doubleclick_on_library_view = 'do_nothing'
doubleclick_on_library_view = 'open_viewer'


# Language to use when sorting. Setting this tweak will force sorting to use the
# collating order for the specified language. This might be useful if you run
# calibre in English but want sorting to work in the language where you live.
# Set the tweak to the desired ISO 639-1 language code, in lower case.
# You can find the list of supported locales at
# http://publib.boulder.ibm.com/infocenter/iseries/v5r3/topic/nls/rbagsicusortsequencetables.htm
# Default: locale_for_sorting = '' -- use the language calibre displays in
# Example: locale_for_sorting = 'fr' -- sort using French rules.
# Example: locale_for_sorting = 'nb' -- sort using Norwegian rules.
locale_for_sorting =  ''


# Set whether to use one or two columns for custom metadata when editing
# metadata  one book at a time. If True, then the fields are laid out using two
# columns. If False, one column is used.
metadata_single_use_2_cols_for_custom_fields = True