__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch zdnet.
'''

from calibre.web.feeds.news import BasicNewsRecipe
import re


class cdnet(BasicNewsRecipe):
    
    title = 'zdnet'
    description = 'zdnet security'
    __author__ = 'Oliver Niesner'
    use_embedded_content   = False
    timefmt = ' [%d %b %Y]'
    max_articles_per_feed = 40
    no_stylesheets = True
    encoding = 'iso-8859-1'

    #preprocess_regexps = \
#	[(re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in
#		[
#		(r'<84>', lambda match: ''),
#		(r'<93>', lambda match: ''),
#		]
#	]
    
    remove_tags = [dict(id='eyebrows'),
		   dict(id='header'),
		   dict(id='search'),
		   dict(id='nav'),
		   dict(id=''),
		   dict(name='div', attrs={'class':'banner'}),
		   dict(name='p', attrs={'class':'tags'}),
		   dict(name='div', attrs={'class':'special1'})]
    remove_tags_after = [dict(name='div', attrs={'class':'bloggerDesc clear'})]
    
    feeds =  [ ('zdnet', 'http://feeds.feedburner.com/zdnet/security') ] 
    




