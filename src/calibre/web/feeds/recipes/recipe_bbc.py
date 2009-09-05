#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
bbc.co.uk
'''

from calibre.web.feeds.news import BasicNewsRecipe

class BBC(BasicNewsRecipe):
    title          = u'The BBC'
    __author__     = 'Kovid Goyal ans Sujata Raman'
    description    = 'Global news and current affairs from the British Broadcasting Corporation'
    language = 'en'

    no_stylesheets = True
    remove_tags    = [dict(name='div', attrs={'class':'footer'}),
                      {'id' : ['popstory','blq-footer']},
                      {'class' : ['arrup','links','relatedbbcsites','arr','promobottombg','bbccom_visibility_hidden', 'sharesb', 'sib606', 'mvtb', 'storyextra', 'sidebar1', 'bbccom_text','promotopbg', 'gppromo','promotopbg','bbccom_display_none']},
                        	]

    keep_only_tags = [dict(name='div', attrs={'class':'mainwrapper'})]

    extra_css      = '''
                        body{font-family:Arial,Helvetica,sans-serif; font-size:small; align:left}
                        h1{font-size:large;}
                        .sh{font-size:large; font-weight:bold}
                        .cap{font-size:xx-small; }
                        .lu{font-size:xx-small; }
                        .ds{font-size:xx-small; }
                        .mvb{font-size:xx-small;}
                        .by1{font-size:x-small;  color:#666666}
                        .byd{font-size:x-small;}
                     '''

    feeds          = [
                      ('News Front Page', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/front_page/rss.xml'),
                      ('Science/Nature', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/science/nature/rss.xml'),
                      ('Technology', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/technology/rss.xml'),
                      ('Entertainment', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/entertainment/rss.xml'),
                      ('Magazine', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/uk_news/magazine/rss.xml'),
                      ('Business', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/business/rss.xml'),
                      ('Health', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/health/rss.xml'),
                      ('Americas', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/americas/rss.xml'),
                      ('Europe', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/europe/rss.xml'),
                      ('South Asia', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/south_asia/rss.xml'),
                      ('UK', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/uk_news/rss.xml'),
                      ('Asia-Pacific', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/asia-pacific/rss.xml'),
                      ('Africa', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/africa/rss.xml'),
                    ]

    def postprocess_html(self, soup, first):

            for tag in soup.findAll(name= 'img', alt=""):
                    tag.extract()

            for item in soup.findAll(align = "right"):
                del item['align']

            for tag in soup.findAll(name=['table', 'tr', 'td']):
                tag.name = 'div'

            return soup



  #  def print_version(self, url):
  #      return url.replace('http://', 'http://newsvote.bbc.co.uk/mpapps/pagetools/print/')


