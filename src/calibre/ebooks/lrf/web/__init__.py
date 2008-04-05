__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.lrf.web.profiles.nytimes       import NYTimes
from calibre.ebooks.lrf.web.profiles.bbc           import BBC
from calibre.ebooks.lrf.web.profiles.newsweek      import Newsweek
from calibre.ebooks.lrf.web.profiles.economist     import Economist
from calibre.ebooks.lrf.web.profiles.newyorkreview import NewYorkReviewOfBooks
from calibre.ebooks.lrf.web.profiles.spiegelde     import SpiegelOnline
from calibre.ebooks.lrf.web.profiles.zeitde        import ZeitNachrichten
from calibre.ebooks.lrf.web.profiles.faznet        import FazNet
from calibre.ebooks.lrf.web.profiles.wsj           import WallStreetJournal
from calibre.ebooks.lrf.web.profiles.barrons       import Barrons
from calibre.ebooks.lrf.web.profiles.portfolio     import Portfolio
from calibre.ebooks.lrf.web.profiles.dilbert       import Dilbert  
from calibre.ebooks.lrf.web.profiles.cnn           import CNN
from calibre.ebooks.lrf.web.profiles.chr_mon       import ChristianScienceMonitor
from calibre.ebooks.lrf.web.profiles.jpost         import JerusalemPost
from calibre.ebooks.lrf.web.profiles.reuters       import Reuters
from calibre.ebooks.lrf.web.profiles.atlantic      import Atlantic 
from calibre.ebooks.lrf.web.profiles.ap            import AssociatedPress 
from calibre.ebooks.lrf.web.profiles.newyorker     import NewYorker 
from calibre.ebooks.lrf.web.profiles.jutarnji      import Jutarnji
from calibre.ebooks.lrf.web.profiles.usatoday      import USAToday
from calibre.ebooks.lrf.web.profiles.upi           import UnitedPressInternational 
from calibre.ebooks.lrf.web.profiles.wash_post     import WashingtonPost 
from calibre.ebooks.lrf.web.profiles.nasa          import NASA 


builtin_profiles   = [Atlantic, AssociatedPress, Barrons, BBC, 
                      ChristianScienceMonitor, CNN, Dilbert, Economist, FazNet, 
                      JerusalemPost, Jutarnji, NASA, Newsweek, NewYorker, 
                      NewYorkReviewOfBooks, NYTimes, UnitedPressInternational, USAToday,  
                      Portfolio, Reuters, SpiegelOnline, WallStreetJournal, 
                      WashingtonPost, ZeitNachrichten,   
                     ]

available_profiles = [i.__module__.rpartition('.')[2] for i in builtin_profiles]