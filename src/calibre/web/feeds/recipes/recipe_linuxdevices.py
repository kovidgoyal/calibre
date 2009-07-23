__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch Linuxdevices.
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe


class Sueddeutsche(BasicNewsRecipe):

    title = u'Linuxdevices'
    description = 'News about Linux driven Hardware'
    __author__ = 'Oliver Niesner'
    use_embedded_content   = False
    timefmt = ' [%a %d %b %Y]'
    max_articles_per_feed = 50
    language = _('English')
    no_stylesheets = True
    html2epub_options = 'linearize_tables = True\nbase_font_size2=14'
    html2lrf_options = ['--ignore-tables']
    encoding = 'latin1'


    remove_tags_after = [dict(id='nointelliTXT')]
    filter_regexps = [r'ad\.doubleclick\.net']

    remove_tags = [dict(name='div', attrs={'class':'bannerSuperBanner'}),
                   dict(name='div', attrs={'class':'bannerSky'}),
                   dict(name='div', attrs={'class':'footerLinks'}),
                   dict(name='div', attrs={'class':'seitenanfang'}),
                   dict(name='td', attrs={'class':'mar5'}),
                   dict(name='td', attrs={'class':'mar5'}),
                   dict(name='table', attrs={'class':'pageAktiv'}),
                   dict(name='table', attrs={'class':'xartable'}),
                   dict(name='table', attrs={'class':'wpnavi'}),
                   dict(name='table', attrs={'class':'bgcontent absatz'}),
                   dict(name='table', attrs={'class':'footer'}),
                   dict(name='table', attrs={'class':'artikelBox'}),
                   dict(name='table', attrs={'class':'kommentare'}),
                   dict(name='table', attrs={'class':'pageBoxBot'}),
                   dict(name='td', attrs={'nowrap':'nowrap'}),
                   dict(name='td', attrs={'valign':'middle'}),
                   dict(name='td', attrs={'align':'left'}),
                   dict(name='td', attrs={'align':'center'}),
                   dict(name='td', attrs={'height':'5'}),
                   dict(name='div', attrs={'class':'artikelBox navigatorBox'}),
                   dict(name='div', attrs={'class':'similar-article-box'}),
                   dict(name='div', attrs={'class':'videoBigHack'}),
                   dict(name='td', attrs={'class':'artikelDruckenRight'}),
                   dict(name='td', attrs={'class':'width="200"'}),
                   dict(name='a', attrs={'href':'/news'}),
                   dict(name='a', attrs={'href':'/'}),
                   dict(name='a', attrs={'href':'/articles'}),
                   dict(name='a', attrs={'href':'/cgi-bin/survey/survey.cgi'}),
                   dict(name='a', attrs={'href':'/cgi-bin/board/UltraBoard.pl'}),
                   dict(name='iframe'),
                   dict(name='form'),
                   dict(name='span', attrs={'class':'hidePrint'}),
                   dict(id='headerLBox'),
                   dict(id='nointelliTXT'),
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



    feeds =  [ (u'Linuxdevices', u'http://www.linuxdevices.com/backend/headlines.rss') ]

    def preprocess_html(self, soup):
        for item in soup.findAll(re.compile('^a')):
            item.extract()
        match = re.compile(r"^Related")
        for item in soup.findAll('b', text=match):
            item.extract()
        for item in soup.findAll(re.compile('^li')):
            item.extract()
        for item in soup.findAll(re.compile('^ul')):
            item.extract()
        for item in soup.find(re.compile('^br')):
            item.extract()
        for item in soup.findAll('br', limit=10):
            item.extract()
        return soup


    def postprocess_html(self, soup, first):
        for tag in soup.findAll(name=['table', 'tr', 'td']):
            tag.name = 'div'
        return soup



