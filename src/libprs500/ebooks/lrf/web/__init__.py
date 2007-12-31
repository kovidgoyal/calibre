##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from libprs500.ebooks.lrf.web.profiles.nytimes       import NYTimes
from libprs500.ebooks.lrf.web.profiles.bbc           import BBC
from libprs500.ebooks.lrf.web.profiles.newsweek      import Newsweek
from libprs500.ebooks.lrf.web.profiles.economist     import Economist
from libprs500.ebooks.lrf.web.profiles.newyorkreview import NewYorkReviewOfBooks
from libprs500.ebooks.lrf.web.profiles.spiegelde     import SpiegelOnline
from libprs500.ebooks.lrf.web.profiles.zeitde        import ZeitNachrichten
from libprs500.ebooks.lrf.web.profiles.faznet        import FazNet
from libprs500.ebooks.lrf.web.profiles.wsj           import WallStreetJournal
from libprs500.ebooks.lrf.web.profiles.barrons       import Barrons
from libprs500.ebooks.lrf.web.profiles.portfolio     import Portfolio  

builtin_profiles   = [Barrons, BBC, Economist, FazNet, Newsweek, NewYorkReviewOfBooks, NYTimes,  \
                      Portfolio, SpiegelOnline, WallStreetJournal, ZeitNachrichten,   \
                     ]

available_profiles = [i.__module__.rpartition('.')[2] for i in builtin_profiles]