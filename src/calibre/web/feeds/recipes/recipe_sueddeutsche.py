__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch sueddeutsche.
'''

from calibre.web.feeds.news import BasicNewsRecipe


class Sueddeutsche(BasicNewsRecipe):
    
    title = u'Sueddeutsche'
    description = 'News from Germany'
    __author__ = 'Oliver Niesner'
    use_embedded_content   = False
    timefmt = ' [%d %b %Y]'
    max_articles_per_feed = 40
    no_stylesheets = True
    encoding = 'latin1'
    remove_tags_after = [dict(name='div', attrs={'class':'artikelBox navigatorBox'})]
                        #dict(name='table', attrs={'class':'bgf2f2f2 absatz print100'})]
                         
    remove_tags = [dict(name='div', attrs={'class':'bannerSuperBanner'}),
                   dict(name='div', attrs={'class':'bannerSky'}),
                   dict(name='div', attrs={'class':'footerLinks'}),
                   dict(name='div', attrs={'class':'seitenanfang'}),
                   dict(name='td', attrs={'class':'mar5'}),
                   dict(name='table', attrs={'class':'pageAktiv'}),
                   dict(name='table', attrs={'class':'xartable'}),
                   dict(name='table', attrs={'class':'wpnavi'}),
                   dict(name='table', attrs={'class':'bgcontent absatz'}),
                   dict(name='table', attrs={'class':'footer'}),
                   dict(name='table', attrs={'class':'artikelBox'}),
                   dict(name='table', attrs={'class':'kommentare'}),
                   dict(name='table', attrs={'class':'pageBoxBot'}),
                   dict(name='div', attrs={'class':'artikelBox navigatorBox'}),
                   dict(name='div', attrs={'class':'similar-article-box'}),
                   dict(name='div', attrs={'class':'videoBigHack'}),
                   dict(name='td', attrs={'class':'artikelDruckenRight'}),
                   dict(name='span', attrs={'class':'hidePrint'}),
                   dict(id='headerLBox'),
                   dict(id='rechteSpalte'),
                   dict(id='newsticker-list-small'),
                   dict(id='ntop5'),
                   dict(id='ntop5send'),
                   dict(id='ntop5commented'),
                   dict(id='nnav-bgheader'),
                   dict(id='nnav-headerteaser'),
                   dict(id='nnav-head'),
                   dict(id='nnav-top'),
                   dict(id='nnav-logodiv'),
                   dict(id='nnav-logo'),
                   dict(id='nnav-oly'),
                   dict(id='readcomment')]
    
    feeds =  [ (u'Sueddeutsche', u'http://www.sueddeutsche.de/app/service/rss/alles/rss.xml') ] 

