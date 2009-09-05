__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch sueddeutsche.
'''
from calibre.web.feeds.news import BasicNewsRecipe


class Sueddeutsche(BasicNewsRecipe):

    title = u'S\xfcddeutsche'
    description = 'News from Germany'
    __author__ = 'Oliver Niesner'
    use_embedded_content   = False
    timefmt = ' [%d %b %Y]'
    oldest_article = 7
    max_articles_per_feed = 50
    no_stylesheets = True
    language = 'de'

    encoding = 'iso-8859-15'
    remove_javascript = True


    remove_tags_after = [dict(name='p', attrs={'class':'mttt'}),
                         dict(name='p', attrs={'class':'artikelFliestext'})]






    remove_tags = [dict(name='span', attrs={'class':'r10000000'}),
                   dict(name='td', attrs={'class':'artikelDruckenRight'}),
                   dict(name='td', attrs={'class':'bgc4c4c4'}),
                   dict(name='div', attrs={'class':'footerCopy padleft5'}),
                   dict(name='div', attrs={'class':'articleDistractor'}),
                   dict(name='div', attrs={'class':'footerLinks'}),
                   dict(name='div', attrs={'class':'nnav-headimagebottom'}),
                   dict(name='div', attrs={'class':'nnavlink'}),
                   dict(name='div', attrs={'class':'nnavlinkhome'}),
                   dict(name='div', attrs={'class':'SpecialGrafik'}),
                   dict(name='div', attrs={'class':'similar-article-box'}),
                   dict(name='div', attrs={'class':'tiefethemen'}),
                   dict(name='table', attrs={'class':'footer'}),
                   dict(name='ul', attrs={'class':'breadcrumb'}),
                   dict(name='a', attrs={'class':'List'}),
                   dict(name='span', attrs={'class':'icVers'}),
                   dict(id='nnav-head'),
                   dict(id='nnav-top'),
                   dict(id='nnav-logo'),
                   dict(id='nnav-logodiv'),
                   dict(id='nnav-bottom'),
                   dict(id='nnav-headimagebottom'),
                   dict(id='headerLBox'),
                   dict(id='logout'),
                   dict(id='nnav-headerteaser'),
                   dict(id='nnav-oly'),
                   dict(id='bookmarklist1'),
                   dict(id='bookmarklist2'),
                   dict(id='navlist-personnames'),
                   dict(id='artikelfoot'),
                   dict(id='nnav-bgheader'),
                   dict(id='rechteSpalte'),
                   dict(id=''),
                   dict(name='td', attrs={'class':'artikelDruckenCenter'})]



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
             (u'Reise', u'http://suche.sueddeutsche.de/query/reise/nav/%C2%A7ressort%3AReise/sort/-docdatetime?output=rss')]



    def print_version(self, url):
        return url.replace('/text/', '/text/print.html')



