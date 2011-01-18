#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
    These templates control the content of titles displayed in the various sections

    Available fields:
    {title}          Title of the book
    {series}         Series name
    {series_index}   Number of the book in the series
    {rating}         Rating
    {rating_parens}  Rating, in parentheses
    {pubyear}        Year the book was published
    {pubyear_parens} Year the book was published, in parentheses

'''
# Books by Author
by_authors_normal_title_template = '{title} {pubyear_parens}'
by_authors_series_title_template = '[{series_index}] {title} {pubyear_parens}'

# Books by Title
by_titles_normal_title_template = '{title}'
by_titles_series_title_template = '{title} ({series} [{series_index}])'

# Books by Series
by_series_title_template = '[{series_index}] {title} {pubyear_parens}'

# Books by Genre
by_genres_normal_title_template = '{title} {pubyear_parens}'
by_genres_series_title_template = '{series_index}. {title} {pubyear_parens}'

# Recently Added
by_recently_added_normal_title_template = '{title}'
by_recently_added_series_title_template = '{title} ({series} [{series_index}])'

# By Month added
by_month_added_normal_title_template = '{title} {pubyear_parens}'
by_month_added_series_title_template = '[{series_index}] {title} {pubyear_parens}'