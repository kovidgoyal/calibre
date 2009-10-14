__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch sueddeutsche.
'''
from calibre.web.feeds.news import BasicNewsRecipe


class Sueddeutsche(BasicNewsRecipe):

    title = u'S\xfcddeutsche'
    description = 'News from Germany'
    __author__ = 'Oliver Niesner and Sujata Raman'
    use_embedded_content   = False
    timefmt = ' [%d %b %Y]'
    oldest_article = 7
    max_articles_per_feed = 50
    no_stylesheets = True
    language = 'de'

    encoding = 'iso-8859-15'
    remove_javascript = True

    keep_only_tags = [
                        dict(name='div', attrs={'id':["artikel","contentTable"]}) ,
                         ]
    remove_tags = [ dict(name='link'), dict(name='iframe'),
                    dict(name='div', attrs={'id':["themenbox","artikelfoot","CAD_AD","rechteSpalte"]}),
                    dict(name='div', attrs={'class':["similar-article-box","artikelliste","nteaser301bg","pages closed"]}),
                    dict(name='p', attrs={'class':["ressortartikeln",]}),
                    dict(name='table', attrs={'class':["kommentare","footer","pageBoxBot","pageAktiv","bgcontent"]}),
                    dict(name='ul', attrs={'class':["breadcrumb","articles","activities"]}),
                    dict(name='p', text = "ANZEIGE")
                     ]

    extra_css = '''
                    h2{font-family:Arial,Helvetica,sans-serif; font-size: x-small; color: #003399;}
                    a{font-family:Arial,Helvetica,sans-serif; font-size: x-small; font-style:italic;}
                    .dachzeile p{font-family:Arial,Helvetica,sans-serif; font-size: x-small; }
                    h1{ font-family:Arial,Helvetica,sans-serif;  font-size:x-large; font-weight:bold;}
                    .artikelTeaser{font-family:Arial,Helvetica,sans-serif; font-size: x-small; font-weight:bold; }
                    body{font-family:Arial,Helvetica,sans-serif; }
                    .photo {font-family:Arial,Helvetica,sans-serif; font-size: x-small; color: #666666;}                 '''

    #feeds = [(u'Topthemen', u'http://suche.sueddeutsche.de/query/politik/-docdatetime/drilldown/%C2%A7documenttype%3AArtikel?output=rss')]

    feeds = [(u'Wissen', u'http://suche.sueddeutsche.de/query/wissen/nav/%C2%A7ressort%3AWissen/sort/-docdatetime?output=rss'),
             (u'Politik', u'http://suche.sueddeutsche.de/query/politik/nav/%C2%A7ressort%3APolitik/sort/-docdatetime?output=rss'),
             (u'Wirtschaft', u'http://suche.sueddeutsche.de/query/wirtschaft/nav/%C2%A7ressort%3AWirtschaft/sort/-docdatetime?output=rss'),
             (u'Finanzen', u'http://suche.sueddeutsche.de/query/finanzen/nav/%C2%A7ressort%3AGeld/sort/-docdatetime?output=rss'),
             (u'Kultur', u'http://suche.sueddeutsche.de/query/kultur/nav/%C2%A7ressort%3AKultur/sort/-docdatetime?output=rss'),
             (u'Sport', u'http://suche.sueddeutsche.de/query/sport/nav/%C2%A7ressort%3ASport/sort/-docdatetime?output=rss'),
             (u'Bayern', u'http://suche.sueddeutsche.de/query/bayern/nav/%C2%A7ressort%3ABayern/sort/-docdatetime?output=rss'),
             (u'Panorama', u'http://suche.sueddeutsche.de/query/panorama/sort/-docdatetime?output=rss'),
             (u'Leben&Stil', u'http://suche.sueddeutsche.de/query/stil/nav/%C2%A7ressort%3A%22Leben%20%26%20Stil%22/sort/-docdatetime?output=rss'),
             (u'Gesundheit', u'http://suche.sueddeutsche.de/query/gesundheit/nav/%C2%A7ressort%3AGesundheit/sort/-docdatetime?output=rss'),
             (u'Auto&Reise', u'http://suche.sueddeutsche.de/query/automobil/nav/%C2%A7ressort%3A%22Auto%20%26%20Mobil%22/sort/-docdatetime?output=rss'),
             (u'Computer', u'http://suche.sueddeutsche.de/query/computer/nav/%C2%A7ressort%3AComputer/sort/-docdatetime?output=rss'),
             (u'Job&Karriere', u'http://suche.sueddeutsche.de/query/job/nav/%C2%A7ressort%3A%22Job%20%26%20Karriere%22/sort/-docdatetime?output=rss'),
             (u'Reise', u'http://suche.sueddeutsche.de/query/reise/nav/%C2%A7ressort%3AReise/sort/-docdatetime?output=rss')
             ]

   # def print_version(self, url):
   #     return url.replace('/text/', '/text/print.html')



