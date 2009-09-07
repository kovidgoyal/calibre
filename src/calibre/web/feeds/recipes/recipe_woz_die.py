from calibre.web.feeds.news import BasicNewsRecipe

class WozDie(BasicNewsRecipe):
     title          = u'WOZ Die Wochenzeitung'
     oldest_article = 7
     max_articles_per_feed = 100
     language = 'de'

     no_stylesheets = True
     remove_tags    = [dict(name='p', attrs={'class':'arrow_top'})]
     remove_tags    = [dict(name='p', attrs={'class':'bottom_right'})]
     remove_tags    = [dict(name='script')]
     extra_css      = '''#print_titel{vertical-align: bottom; text-align:
 left; color: #666666; background-color: white; padding-top: 30px; padding-
 bottom: 10px; border-bottom: 1px solid #999999;} #title{text-align:
 left; font-size: large; font-weight: 600; padding-top: 0px; padding-
 bottom: 6px;}  h3 {text-align: left; font-size: large; font-weight: 600;
 padding-top: 0px; padding-bottom: 6px;}  #lead{font-weight: 600;
 padding-bottom: 6px;}  h2{font-weight: 600; padding-bottom: 6px;}
 #author{color: #666666; padding-top: 0px; padding-bottom: 0px;}
 h4{color: #666666; padding-top: 0px; padding-bottom: 0px;}  #author2
 {color: #666666; padding-top: 0px; padding-bottom: 0px;}  .dotted_line
 {padding-top: 0px; margin-bottom: 18px; border-bottom: 1px dotted
 #666666;}  .intro{margin: 0 auto; font-weight: 600; padding-bottom:
 18px;}  h5{margin: 0 auto; font-weight: 600; padding-bottom: 18px;}
 .intro2{margin: 0 auto;  font-weight: 600;}  .text{padding-bottom:
 18px;}  .subtitle{margin: 0 auto; font-weight: 600; padding-bottom:
 10px;}  .articletitle{margin: 0 auto; font-weight: 600; padding-bottom:
 10px;}  #content_infobox{margin-top: 20px; margin-left: 0px; margin-
 right: 0px; margin-bottom: 10px; text-align: left; border-bottom: 1px
 solid #999999;}  .content_infobox_titel{padding-top: 6px; padding-
 bottom: 8px; padding-left: 8px; padding-right: 8px; font-weight: 600;
 border-top: 1px solid #999999; border-bottom: 1px dotted #999999;}
 .content_infobox_text{padding-top: 6px; padding-bottom: 12px; padding-
 left: 8px; padding-right: 8px;}  .box_gray{padding-top: 4px; padding-
 left:  7px; padding-right:  7px; padding-bottom:  4px;}  .box_white {
 padding-top: 4px; padding-left:  7px; padding-right:  7px; padding-bottom:
 4px;}  .content_infobox_mehr{margin-top: 20px; margin-left: 0px; margin-
 right: 0px; margin-bottom: 10px; text-align: left; width: 600px; border-
 bottom: 1px solid #999999;}'''

     feeds          = [('WOZ Die Wochenzeitung - Headlines',
 'http://www.woz.ch/inhalt/headlinesRSS.php'),]

     def print_version(self, url):
            return url.replace('rss/', 'print_')

