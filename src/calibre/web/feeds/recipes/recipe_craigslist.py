#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe

class CraigsList(BasicNewsRecipe):
     title          = u'craigslist - Best Of'
     oldest_article = 365
     max_articles_per_feed = 100
     language = _('English')
     __author__ = 'kiodane'

     feeds          = [(u'Best of craigslist',
 u'http://www.craigslist.org/about/best/all/index.rss'), (u'Ann Arbor',
 u'http://www.craigslist.org/about/best/aaa/index.rss'), (u'Asheville',
 u'http://www.craigslist.org/about/best/ash/index.rss'), (u'Austin',
 u'http://www.craigslist.org/about/best/aus/index.rss'), (u'Baltimore',
 u'http://www.craigslist.org/about/best/bal/index.rss'), (u'Birmingham',
 u'http://www.craigslist.org/about/best/bhm/index.rss'), (u'Boston',
 u'http://www.craigslist.org/about/best/bos/index.rss'), (u'Vermont',
 u'http://www.craigslist.org/about/best/brl/index.rss'), (u'Columbia',
 u'http://www.craigslist.org/about/best/cae/index.rss'), (u'Charlotte',
 u'http://www.craigslist.org/about/best/cha/index.rss'), (u'Chico',
 u'http://www.craigslist.org/about/best/chc/index.rss'), (u'Chicago',
 u'http://www.craigslist.org/about/best/chi/index.rss'), (u'Charleston',
 u'http://www.craigslist.org/about/best/chs/index.rss'), (u'Cleveland',
 u'http://www.craigslist.org/about/best/cle/index.rss'), (u'Calgary',
 u'http://www.craigslist.org/about/best/clg/index.rss'),
 (u'Colorado Springs', u'http://www.craigslist.org/about/best/cos/index.rss'),
 (u'Dallas', u'http://www.craigslist.org/about/best/dal/index.rss'),
 (u'Denver', u'http://www.craigslist.org/about/best/den/index.rss'),
 (u'Detroit Metro', u'http://www.craigslist.org/about/best/det/index.rss'),
 (u'Des Moines', u'http://www.craigslist.org/about/best/dsm/index.rss'),
 (u'Eau Claire', u'http://www.craigslist.org/about/best/eau/index.rss'),
 (u'Grand Rapids', u'http://www.craigslist.org/about/best/grr/index.rss'),
 (u'Hawaii', u'http://www.craigslist.org/about/best/hnl/index.rss'),
 (u'Jacksonville', u'http://www.craigslist.org/about/best/jax/index.rss'),
 (u'Knoxville', u'http://www.craigslist.org/about/best/knx/index.rss'),
 (u'Kansas City', u'http://www.craigslist.org/about/best/ksc/index.rss'),
 (u'South Florida', u'http://www.craigslist.org/about/best/mia/index.rss'),
(u'Minneapolis', u'http://www.craigslist.org/about/best/min/index.rss'),
 (u'Maine', u'http://www.craigslist.org/about/best/mne/index.rss'),
 (u'Montreal', u'http://www.craigslist.org/about/best/mon/index.rss'),
 (u'Nashville', u'http://www.craigslist.org/about/best/nsh/index.rss'),
 (u'New York', u'http://www.craigslist.org/about/best/nyc/index.rss'),
 (u'Orange County', u'http://www.craigslist.org/about/best/orc/index.rss'),
 (u'Portland', u'http://www.craigslist.org/about/best/pdx/index.rss'),
 (u'Phoenix', u'http://www.craigslist.org/about/best/phx/index.rss'),
 (u'Pittsburgh', u'http://www.craigslist.org/about/best/pit/index.rss'),
 (u'Rhode Island', u'http://www.craigslist.org/about/best/prv/index.rss'),
 (u'Raleigh', u'http://www.craigslist.org/about/best/ral/index.rss'),
 (u'Rochester', u'http://www.craigslist.org/about/best/rcs/index.rss'),
 (u'San Antonio', u'http://www.craigslist.org/about/best/sat/index.rss'),
 (u'Santa Barbara', u'http://www.craigslist.org/about/best/sba/index.rss'),
 (u'San Diego', u'http://www.craigslist.org/about/best/sdo/index.rss'),
 (u'Seattle-Tacoma', u'http://www.craigslist.org/about/best/sea/index.rss'),
 (u'Sf Bay Area', u'http://www.craigslist.org/about/best/sfo/index.rss'),
 (u'Salt Lake City',
 u'http://www.craigslist.org/about/best/slc/index.rss'), (u'Spokane',
 u'http://www.craigslist.org/about/best/spk/index.rss'), (u'St Louis',
 u'http://www.craigslist.org/about/best/stl/index.rss'), (u'Sydney',
 u'http://www.craigslist.org/about/best/syd/index.rss'), (u'Toronto',
 u'http://www.craigslist.org/about/best/tor/index.rss'), (u'Vancouver BC',
 u'http://www.craigslist.org/about/best/van/index.rss'), (u'Washington DC',
 u'http://www.craigslist.org/about/best/wdc/index.rss')]

