#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
politika.rs
'''
import string,re
from calibre.web.feeds.news import BasicNewsRecipe

class Politika(BasicNewsRecipe):
    title                 = u'Politika Online'
    __author__            = 'Darko Miletic'
    description           = 'Najstariji dnevni list na Balkanu'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    extra_css             = '.content_center_border {text-align: left;}' 
    use_embedded_content  = False
    timefmt               = ' [%A, %d %B, %Y]' 

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    remove_tags_before = dict(name='div', attrs={'class':'content_center_border'})
    remove_tags_after  = dict(name='div', attrs={'class':'datum_item_details'})

    feeds          = [  
                         (u'Politika'             , u'http://www.politika.rs/rubrike/Politika/index.1.lt.xml'             )
                        ,(u'Svet'                 , u'http://www.politika.rs/rubrike/Svet/index.1.lt.xml'                 )
                        ,(u'Redakcijski komentari', u'http://www.politika.rs/rubrike/redakcijski-komentari/index.1.lt.xml')
                        ,(u'Pogledi'              , u'http://www.politika.rs/pogledi/index.lt.xml'                        )
                        ,(u'Pogledi sa strane'    , u'http://www.politika.rs/rubrike/Pogledi-sa-strane/index.1.lt.xml'    )
                        ,(u'Tema dana'            , u'http://www.politika.rs/rubrike/tema-dana/index.1.lt.xml'            )
                        ,(u'Kultura'              , u'http://www.politika.rs/rubrike/Kultura/index.1.lt.xml'              )
                        ,(u'Zivot i stil'         , u'http://www.politika.rs/rubrike/zivot-i-stil/index.1.lt.xml'         )                        
                     ]
