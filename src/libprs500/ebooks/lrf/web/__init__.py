__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

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
from libprs500.ebooks.lrf.web.profiles.upi           import UnitedPressInternational 
from libprs500.ebooks.lrf.web.profiles.wash_post     import WashingtonPost 
from libprs500.ebooks.lrf.web.profiles.nasa          import NASA 


builtin_profiles   = [Atlantic, AssociatedPress, Barrons, BBC, 
                      ChristianScienceMonitor, CNN, Dilbert, Economist, FazNet, 
                      JerusalemPost, Jutarnji, NASA, Newsweek, NewYorker, 
                      NewYorkReviewOfBooks, NYTimes, UnitedPressInternational, USAToday,  
                      Portfolio, Reuters, SpiegelOnline, WallStreetJournal, 
                      WashingtonPost, ZeitNachrichten,   
                     ]

available_profiles = [i.__module__.rpartition('.')[2] for i in builtin_profiles]