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
from libprs500.ebooks.lrf.web.profiles.dilbert       import Dilbert  
from libprs500.ebooks.lrf.web.profiles.cnn           import CNN
from libprs500.ebooks.lrf.web.profiles.chr_mon       import ChristianScienceMonitor
from libprs500.ebooks.lrf.web.profiles.jpost         import JerusalemPost
from libprs500.ebooks.lrf.web.profiles.reuters       import Reuters
from libprs500.ebooks.lrf.web.profiles.atlantic      import Atlantic 
from libprs500.ebooks.lrf.web.profiles.ap            import AssociatedPress 
from libprs500.ebooks.lrf.web.profiles.newyorker     import NewYorker 
from libprs500.ebooks.lrf.web.profiles.jutarnji      import Jutarnji
from libprs500.ebooks.lrf.web.profiles.usatoday      import USAToday

builtin_profiles   = [Atlantic, AssociatedPress, Barrons, BBC, 
                      ChristianScienceMonitor, CNN, Dilbert, Economist, FazNet, 
                      JerusalemPost, Jutarnji, Newsweek, NewYorker, 
                      NewYorkReviewOfBooks, NYTimes, USAToday,  
                      Portfolio, Reuters, SpiegelOnline, WallStreetJournal, 
                      ZeitNachrichten,   
                     ]

available_profiles = [i.__module__.rpartition('.')[2] for i in builtin_profiles]