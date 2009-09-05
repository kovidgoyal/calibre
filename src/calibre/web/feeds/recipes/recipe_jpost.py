from calibre.web.feeds.news import BasicNewsRecipe

class JerusalemPost(BasicNewsRecipe):

    title       = 'Jerusalem Post'
    description = 'News from Israel and the Middle East'
    use_embedded_content   = False
    language = 'en'

    __author__ = 'Kovid Goyal'
    max_articles_per_feed = 10
    no_stylesheets = True
    remove_tags_before = {'class':'byline'}
    remove_tags    = [
                      {'class':['artAdBlock clearboth', 'tbartop', 'divdot_vrttbox',
                                'slideshow']},
                       dict(id=['artFontButtons', 'artRelatedBlock']),
                     ]
    remove_tags_after = {'id':'artTxtBlock'}
    
    feeds =  [ ('Front Page', 'http://www.jpost.com/servlet/Satellite?pagename=JPost/Page/RSS&cid=1123495333346'),
               ('Israel News', 'http://www.jpost.com/servlet/Satellite?pagename=JPost/Page/RSS&cid=1178443463156'),
               ('Middle East News', 'http://www.jpost.com/servlet/Satellite?pagename=JPost/Page/RSS&cid=1123495333498'),
               ('International News', 'http://www.jpost.com/servlet/Satellite?pagename=JPost/Page/RSS&cid=1178443463144'),
               ('Editorials', 'http://www.jpost.com/servlet/Satellite?pagename=JPost/Page/RSS&cid=1123495333211'),
          ]
          
    def postprocess_html(self, soup, first):
        for tag in soup.findAll(name=['table', 'tr', 'td']):
            tag.name = 'div'
        return soup