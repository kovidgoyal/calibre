# Copyright (C) 2008 B.Scott Wxby [bswxby] &
# Copyright (C) 2007 David Chen SonyReader<at>DaveChen<dot>org
##
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
##
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
##
# Version 0.3-2008_2_28
# Based on WIRED.py by David Chen, 2007, and newsweek.py, bbc.py, nytimes.py by Kovid Goyal
##
# Usage:
# >web2lrf --user-profile nasa.py
# Comment out the RSS feeds you don't want in the last section below
##
# Output:
# NASA [YearMonthDate Time].lrf
##
'''
Custom User Profile to download RSS News Feeds and Articles from Wired.com
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe


class NASA(BasicNewsRecipe):

    title = 'NASA'
    timefmt = ' [%Y%b%d  %H%M]'
    language = 'en'

    description = 'News from NASA'
    __author__ = 'Scott Wxby & David Chen'
    no_stylesheets = True

    # Don't grab articles more than 30 days old
    oldest_article = 30

    preprocess_regexps = [(re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in
                          [
        # Fix the encoding to UTF-8
        (r'<meta http-equiv="Content-Type" content="text/html; charset=(\S+)"',
         lambda match: match.group().replace(match.group(1), 'UTF-8')),

        # Remove any banners/links/ads/cruft before the body of the article.
        (r'<body.*?((<div id="article_body">)|(<div id="st-page-maincontent">)|(<div id="containermain">)|(<p class="ap-story-p">)|(<!-- img_nav -->))', lambda match: '<body><div>'),  # noqa

        # Remove any links/ads/comments/cruft from the end of the body
        # of the article.
        (r'((<!-- end article content -->)|(<div id="st-custom-afterpagecontent">)|(<p class="ap-story-p">&copy;)|(<div class="entry-footer">)|(<div id="see_also">)|(<p>Via <a href=)|(<div id="ss_nav">)).*?</html>', lambda match: '</div></body></html>'),  # noqa

        # Correctly embed in-line images by removing the surrounding
        # javascript that will be ignored in the conversion
        (r'<a.*?onclick.*?>.*?(<img .*?>)', lambda match: match.group(1),),

        # This removes header and footer information from each print
        # version.
        (r'<!-- Top Header starts -->.*?<!-- Body starts -->',
         lambda match: '<New Stuff>'),
        (r'<hr align="center" width="200"><p align="center">.*?<!-- Press Release standard text ends -->',
         lambda match: '<New Stuff>'),
        (r'<!-- Top Header starts -->.*?<!---->', lambda match: '<New Stuff>'),

        # This removes the "download image" of various sizes from the Image of
        # the day.
        (r'<div id="download_image_box_print">.*?<div id="caption_region_print">',
         lambda match: '<New Stuff>'),

    ]
    ]

# NASA's print pages differ only by the ending "_prt.htm", so I've
# replaced them below.

    def print_version(self, url):
        return url.replace('.html', '_prt.htm')

# Comment out the feeds you don't want retrieved.
# Or add any new new RSS feed URL's here, sorted alphabetically when converted to LRF
# If you want one of these at the top, append a space in front of the name.
# Mars feed may not work, as it is now considered "legacy" by NASA.

    feeds = [
        (' Breaking News', 'https://www.nasa.gov/rss/dyn/breaking_news.rss'),
        ('Image of the Day', 'https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss'),
        ('Mars Exploration', 'https://marsmobile.jpl.nasa.gov/rss/?feed=news&category=all'),
        ('Shuttle and Station News', 'https://www.nasa.gov/rss/dyn/shuttle_station.rss'),
        ('Solar System and Beyond News', 'https://www.nasa.gov/rss/dyn/solar_system.rss'),
        ('Education News', 'https://www.nasa.gov/rss/dyn/educationnews.rss'),
        ('Earth News', 'https://www.nasa.gov/rss/dyn/earth.rss'),
        ('Aeronautics News', 'https://www.nasa.gov/rss/dyn/aeronautics.rss'),
    ]
