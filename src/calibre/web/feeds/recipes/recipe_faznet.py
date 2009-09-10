__license__   = 'GPL v3'
__copyright__ = '2008-2009, Kovid Goyal <kovid at kovidgoyal.net>, Darko Miletic <darko at gmail.com>'
'''
Profile to download FAZ.net
'''

from calibre.web.feeds.news import BasicNewsRecipe
 
class FazNet(BasicNewsRecipe): 
    title                 = 'FAZ NET'
    __author__            = 'Kovid Goyal, Darko Miletic'
    description           = 'Frankfurter Allgemeine Zeitung'
    publisher             = 'FAZ Electronic Media GmbH'
    category              = 'news, politics, Germany'
    use_embedded_content  = False
    language = 'de'
 
    max_articles_per_feed = 30 
    no_stylesheets        = True
    encoding              = 'utf-8'
    remove_javascript     = True

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
    
    keep_only_tags = [dict(name='div', attrs={'class':'Article'})]

    remove_tags = [
                     dict(name=['object','link','embed','base'])
                    ,dict(name='div', attrs={'class':['LinkBoxModulSmall','ModulVerlagsInfo']})
                  ]
    

    feeds = [ ('FAZ.NET', 'http://www.faz.net/s/Rub/Tpl~Epartner~SRss_.xml') ] 

    def print_version(self, url):
        article, sep, rest = url.partition('?')    
        return article.replace('.html', '~Afor~Eprint.html') 

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>'
        soup.head.insert(0,mtag)        
        del soup.body['onload']
        for item in soup.findAll(style=True):
            del item['style']
        return soup
