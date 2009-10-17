from calibre.web.feeds.recipes import BasicNewsRecipe

class TheRegister(BasicNewsRecipe):
    title          = u'The Register'
    __author__     = 'vgrama'
    language = 'en'

    oldest_article = 1
    max_articles_per_feed = 100
    use_embedded_content = False
          
    feeds          = [(u'Register', u'http://www.theregister.co.uk/headlines.atom')]
       
    remove_tags    = [
            dict(name='div', attrs={'id':'leader'}), 
            dict(name='div', attrs={'id':'footer'}),  
            dict(name='div', attrs={'id':'masthead'})]
      
    def print_version(self, url):
        return '%s/print.html' % url
