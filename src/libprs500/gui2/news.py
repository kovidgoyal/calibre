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

from PyQt4.QtCore import QObject, SIGNAL
from PyQt4.QtGui import QMenu, QIcon, QDialog

from libprs500.gui2.dialogs.password import PasswordDialog

class NewsMenu(QMenu):
    
    def add_menu_item(self, title, func, icon=':/images/news.svg'):
        self.addAction(QIcon(icon), title)
        QObject.connect(self.actions()[-1], SIGNAL('triggered(bool)'), func) 
    
    def __init__(self):
        QMenu.__init__(self)
        self.add_menu_item('Barrons', self.fetch_news_barrons)
        self.add_menu_item('BBC', self.fetch_news_bbc, ':/images/news/bbc.png')
        self.add_menu_item('Economist', self.fetch_news_economist, ':/images/news/economist.png')
        self.add_menu_item('Faz.net', self.fetch_news_faznet, ':/images/news/faznet.png')
        self.add_menu_item('Newsweek', self.fetch_news_newsweek, ':/images/news/newsweek.png')
        self.add_menu_item('New York Review of Books', self.fetch_news_nyreview, ':/images/book.svg')
        self.add_menu_item('New York Times', self.fetch_news_nytimes, ':/images/news/nytimes.png')
        self.add_menu_item('Portfolio.com', self.fetch_news_portfolio)
        self.add_menu_item('Spiegel Online', self.fetch_news_spiegelde, ':/images/news/spiegelonline.png')
        self.add_menu_item('Wall Street Journal', self.fetch_news_wsj)
        self.add_menu_item('Zeit Nachrichten', self.fetch_news_zeitde, ':/images/news/diezeit.png')
        
    def fetch_news(self, profile, title, username=None, password=None):
        data = dict(profile=profile, title=title, username=username, password=password)
        self.emit(SIGNAL('fetch_news(PyQt_PyObject)'), data)
    
    def fetch_news_portfolio(self, checked):
        self.fetch_news('portfolio', 'Portfolio.com')
    
    def fetch_news_spiegelde(self, checked):
        self.fetch_news('spiegelde', 'Spiegel Online')
        
    def fetch_news_zeitde(self, checked):
        self.fetch_news('zeitde', 'Zeit Nachrichten')
        
    def fetch_news_faznet(self, checked):
        self.fetch_news('faznet', 'Faz.net')
    
    def fetch_news_bbc(self, checked):
        self.fetch_news('bbc', 'BBC')
    
    def fetch_news_newsweek(self, checked):
        self.fetch_news('newsweek', 'Newsweek')
        
    def fetch_news_economist(self, checked):
        self.fetch_news('economist', 'The Economist')
    
    def fetch_news_nyreview(self, checked):
        self.fetch_news('newyorkreview', 'New York Review of Books')
    
    def fetch_news_nytimes(self, checked):
        d = PasswordDialog(self, 'nytimes info dialog', 
                           '<p>Please enter your username and password for nytimes.com<br>If you do not have an account, you can <a href="http://www.nytimes.com/gst/regi.html">register</a> for free.<br>Without a registration, some articles will not be downloaded correctly. Click OK to proceed.')
        d.exec_()
        if d.result() == QDialog.Accepted:
            un, pw = d.username(), d.password()
            self.fetch_news('nytimes', 'New York Times', username=un, password=pw)
            
    def fetch_news_wsj(self, checked):
        d = PasswordDialog(self, 'wsj info dialog', 
                           '<p>Please enter your username and password for wsj.com<br>Click OK to proceed.')
        d.exec_()
        if d.result() == QDialog.Accepted:
            un, pw = d.username(), d.password()
            self.fetch_news('wsj', 'Wall Street Journal', username=un, password=pw)
            
    def fetch_news_barrons(self, checked):
        d = PasswordDialog(self, 'barrons info dialog', 
                           '<p>Please enter your username and password for barrons.com<br>Click OK to proceed.')
        d.exec_()
        if d.result() == QDialog.Accepted:
            un, pw = d.username(), d.password()
            self.fetch_news('barrons', 'Barrons', username=un, password=pw)