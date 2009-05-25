#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'



from calibre.web.feeds.news import BasicNewsRecipe

class LeTemps(BasicNewsRecipe):
     title          = u'Le Temps'
     oldest_article = 7
     max_articles_per_feed = 100
     no_stylesheets = True
     remove_tags    = [dict(name='div', attrs={'id':'footer'})]
     remove_tags    = [dict(name='div', attrs={'class':'box links'})]
     remove_tags    = [dict(name='script')]
     extra_css      = '''.heading {font-size: 13px; line-height: 15px;
 margin: 20px 0;} \n h2 {font-size: 24px; line-height: 25px; margin-bottom:
 14px;} \n .author {font-size: 11px; margin: 0 0 5px 0;} \n .lead {font-
 weight: 700; margin: 10px 0;} \n p {margin: 0 0 10px 0;}'''

     feeds          = [
                              ('Actualité',
 'http://www.letemps.ch/rss/site/'),
                              ('Monde',
 'http://www.letemps.ch/rss/site/actualite/monde'),
                              ('Suisse & Régions',
 'http://www.letemps.ch/rss/site/actualite/suisse_regions'),
                              ('Sciences & Environnement',
 'http://www.letemps.ch/rss/site/actualite/sciences_environnement'),
                              ('Société',
 'http://www.letemps.ch/rss/site/actualite/societe'),
                              ('Economie & Finance',
 'http://www.letemps.ch/rss/site/economie_finance'),
                              ('Economie & Finance - Finance',
 'http://www.letemps.ch/rss/site/economie_finance/finance'),
                              ('Economie & Finance - Fonds de placement',
 'http://www.letemps.ch/rss/site/economie_finance/fonds_placement'),
                              ('Economie & Finance - Carrières',
 'http://www.letemps.ch/rss/site/economie_finance/carrieres'),
                             ('Culture',
 'http://www.letemps.ch/rss/site/culture'),
                              ('Culture - Cinéma',
 'http://www.letemps.ch/rss/site/culture/cinema'),
                              ('Culture - Musiques',
 'http://www.letemps.ch/rss/site/culture/musiques'),
                              ('Culture - Scènes',
 'http://www.letemps.ch/rss/site/culture/scenes'),
                              ('Culture - Arts plastiques',
 'http://www.letemps.ch/rss/site/culture/arts_plastiques'),
                              ('Livres',
 'http://www.letemps.ch/rss/site/culture/livres'),
                              ('Opinions',
 'http://www.letemps.ch/rss/site/opinions'),
                              ('Opinions - Editoriaux',
 'http://www.letemps.ch/rss/site/opinions/editoriaux'),
                              ('Opinions - Invités',
 'http://www.letemps.ch/rss/site/opinions/invites'),
                              ('Opinions - Chroniques',
 'http://www.letemps.ch/rss/site/opinions/chroniques'),
                              ('LifeStyle',
 'http://www.letemps.ch/rss/site/lifestyle'),
                              ('LifeStyle - Luxe',
 'http://www.letemps.ch/rss/site/lifestyle/luxe'),
                              ('LifeStyle - Horlogerie & Joaillerie',
 'http://www.letemps.ch/rss/site/lifestyle/horlogerie_joaillerie'),
                              ('LifeStyle - Design',
 'http://www.letemps.ch/rss/site/lifestyle/design'),
                              ('LifeStyle - Voyages',
 'http://www.letemps.ch/rss/site/lifestyle/voyages'),
                              ('LifeStyle - Gastronomie',
 'http://www.letemps.ch/rss/site/lifestyle/gastronomie'),
                              ('LifeStyle - Architecture & Immobilier',
 'http://www.letemps.ch/rss/site/lifestyle/architecture_immobilier'),
                              ('LifeStyle - Automobile',
 'http://www.letemps.ch/rss/site/lifestyle/automobile'),
                              ('Sports',
 'http://www.letemps.ch/rss/site/actualite/sports'),
                             ]

     def print_version(self, url):
            return url.replace('Page', 'Facet/print')


