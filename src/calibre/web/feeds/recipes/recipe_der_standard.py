
''' http://www.derstandard.at - Austrian Newspaper '''
import re
from calibre.web.feeds.news import BasicNewsRecipe

class DerStandardRecipe(BasicNewsRecipe):
    title          = u'derStandard'
    __author__  = 'Gerhard Aigner'

    oldest_article = 1
    max_articles_per_feed = 100
    feeds          = [(u'International', u'http://derstandard.at/?page=rss&ressort=internationalpolitik'),
        (u'Inland', u'http://derstandard.at/?page=rss&ressort=innenpolitik'),
        (u'Wirtschaft', u'http://derstandard.at/?page=rss&ressort=investor'),
        (u'Web', u'http://derstandard.at/?page=rss&ressort=webstandard'),
        (u'Sport', u'http://derstandard.at/?page=rss&ressort=sport'),
        (u'Panorama', u'http://derstandard.at/?page=rss&ressort=panorama'),
        (u'Etat', u'http://derstandard.at/?page=rss&ressort=etat'),
        (u'Kultur', u'http://derstandard.at/?page=rss&ressort=kultur'),
        (u'Wissenschaft', u'http://derstandard.at/?page=rss&ressort=wissenschaft'),
        (u'Gesundheit', u'http://derstandard.at/?page=rss&ressort=gesundheit'),
        (u'Bildung', u'http://derstandard.at/?page=rss&ressort=subildung')]

    encoding = 'utf-8'
    language = _('German')
    recursions = 0
    remove_tags = [dict(name='div'), dict(name='a'), dict(name='link'), dict(name='meta'),
        dict(name='form',attrs={'name':'sitesearch'}), dict(name='hr')]
    preprocess_regexps = [
        (re.compile(r'\[[\d*]\]', re.DOTALL|re.IGNORECASE), lambda match: ''),
        (re.compile(r'bgcolor="#\w{3,6}"', re.DOTALL|re.IGNORECASE), lambda match: '')
    ]

    def print_version(self, url):
        return url.replace('?id=', 'txt/?id=')

    def get_article_url(self, article):
        '''if the article links to a index page (ressort) or a picture gallery
           (ansichtssache), don't add it'''
        if (article.link.count('ressort') > 0 or article.title.lower().count('ansichtssache') > 0):
            return None
        return article.link
