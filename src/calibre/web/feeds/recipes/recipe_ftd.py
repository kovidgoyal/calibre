__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch FTD.
'''

from calibre.web.feeds.news import BasicNewsRecipe


class FTheiseDe(BasicNewsRecipe):
    
    title = 'FTD'
    description = 'Financial Times Deutschland'
    __author__ = 'Oliver Niesner'
    use_embedded_content   = False
    timefmt = ' [%d %b %Y]'
    language = 'de'

    max_articles_per_feed = 40
    no_stylesheets = True
    
    remove_tags = [dict(id='navi_top'),
		   dict(id='topbanner'),
		   dict(id='seitenkopf'),
		   dict(id='footer'),
		   dict(id='rating_open'),
		   dict(id='ADS_Top'),
		   dict(id='ADS_Middle1'),
		   #dict(id='IDMS_ajax_chart_price_information_table'),
		   dict(id='ivwimg'),
		   dict(name='span', attrs={'class':'rsaquo'}),
		   dict(name='p', attrs={'class':'zwischenhead'}),
		   dict(name='div', attrs={'class':'chartBox'}),
		   dict(name='span', attrs={'class':'vote_455857'}),
		   dict(name='div', attrs={'class':'relatedhalb'}),
		   dict(name='div', attrs={'class':'bpoll'}),
		   dict(name='div', attrs={'class':'pollokknopf'}),
		   dict(name='div', attrs={'class':'videohint'}),
		   dict(name='div', attrs={'class':'videoshadow'}),
		   dict(name='div', attrs={'class':'boxresp videorahmen'}),
		   dict(name='div', attrs={'class':'boxresp'}),
		   dict(name='div', attrs={'class':'abspielen'}),
		   dict(name='div', attrs={'class':'wertungoben'}),
		   dict(name='div', attrs={'class':'artikelfuss'}),
		   dict(name='div', attrs={'class':'artikelsplitfaq'})]
    remove_tags_after = [dict(name='div', attrs={'class':'artikelfuss'})]
    
    feeds =  [ ('FTD', 'http://www.ftd.de/static/ticker/ftd-topnews.rdf') ] 
    

