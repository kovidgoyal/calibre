import re
from calibre.web.feeds.recipes import BasicNewsRecipe

class Physicstoday(BasicNewsRecipe):
    title          = u'Physicstoday'
    __author__     = 'Hypernova'
    description           = u'Physicstoday'
    language              = _('English')
    oldest_article = 30
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    needs_subscription = True
    remove_javascript     = True
    remove_tags_before = dict(name='h1')
    remove_tags_after   = [dict(name='div', attrs={'id':'footer'})]

    feeds          = [(u'All', u'http://www.physicstoday.org/feed.xml')]

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        if self.username is not None and self.password is not None:
            br.open('http://www.physicstoday.org/pt/sso_login.jsp')
            br.select_form(name='login')
            br['username'] = self.username
            br['password'] = self.password
            br.submit()
        return br
