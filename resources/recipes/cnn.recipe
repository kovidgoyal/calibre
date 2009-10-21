__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Profile to download CNN
'''
from calibre.web.feeds.news import BasicNewsRecipe

class CNN(BasicNewsRecipe):

    title = 'CNN'
    description = 'Global news'
    timefmt  = ' [%d %b %Y]'
    __author__ = 'Kovid Goyal and Sujata Raman'
    language = 'en'

    no_stylesheets = True
    use_embedded_content   = False
    oldest_article        = 15

    extra_css = '''
                h1{font-family :Arial,Helvetica,sans-serif; font-size:large}
                h2{font-family :Arial,Helvetica,sans-serif; font-size:x-small}
                .cnnTxtCmpnt{font-family :Arial,Helvetica,sans-serif; font-size:x-small}
                .cnnTMcontent{font-family :Arial,Helvetica,sans-serif; font-size:xx-small;color:#575757}
                .storytext{font-family :Arial,Helvetica,sans-serif; font-size:x-small}
                .storybyline{font-family :Arial,Helvetica,sans-serif; font-size:xx-small; color:#575757}
                .credit{font-family :Arial,Helvetica,sans-serif; font-size:xx-small; color:#575757}
                .storyBrandingBanner{font-family :Arial,Helvetica,sans-serif; font-size:xx-small; color:#575757}
                .storytimestamp{font-family :Arial,Helvetica,sans-serif; font-size:xx-small; color:#575757}
                .timestamp{font-family :Arial,Helvetica,sans-serif; font-size:xx-small; color:#575757}
                .subhead p{font-family :Arial,Helvetica,sans-serif; font-size:xx-small;}
                .cnnStoryContent{font-family :Arial,Helvetica,sans-serif; font-size:xx-small}
                .cnnContentContainer{font-family :Arial,Helvetica,sans-serif; font-size:xx-small}
                .col1{font-family :Arial,Helvetica,sans-serif; font-size:x-small; color:#666666;}
                .col3{color:#333333; font-family :Arial,Helvetica,sans-serif; font-size:x-small;font-weight:bold;}
                .cnnInlineT1Caption{font-family :Arial,Helvetica,sans-serif; font-size:xx-small;font-weight:bold;}
                .cnnInlineT1Credit{font-family :Arial,Helvetica,sans-serif; font-size:xx-small;color:#333333;}
                .col10{color:#5A637E}
                .cnnTimeStamp{font-family :Arial,Helvetica,sans-serif; font-size:xx-small;color:#333333;}
                .galleryhedDek{font-family :Arial,Helvetica,sans-serif; font-size:xx-small;color:#575757;}
                .galleryWidgetHeader{font-family :Arial,Helvetica,sans-serif; font-size:xx-small;color:#004276;}
                .article-content{font-family :Arial,Helvetica,sans-serif; font-size:xx-small}
                .cnnRecapStory{font-family :Arial,Helvetica,sans-serif; font-size:xx-small}
                '''
    keep_only_tags = [
                        dict(name='div', attrs={'class':["cnnWCBoxContent","cnnContent","cnnMainBodySecs"]}),
                         dict(name='div', attrs={'id':["contentBody","content"]}),
                         dict(name='td', attrs={'id':["cnnRecapStory"]}),]
    remove_tags =   [
                        dict(name='div', attrs={'class':["storyLink","article-tools clearfix","widget video related-video vList","cnnFooterBox","scrollArrows","boxHeading","cnnInlineMailbag","mainCol_lastBlock","cnn_bookmarks","cnnFooterBox","cnnEndOfStory","cnnInlineSL","cnnStoryHighlights","cnnFooterClick","cnnSnapShotHeader","cnnStoryToolsFooter","cnnWsnr","cnnUGCBox","cnnTopNewsModule","cnnStoryElementBox","cnnStoryPhotoBoxNavigation"]}),
                        dict(name='span', attrs={'class':["cnnEmbeddedMosLnk"]}),
                        dict(name='div', attrs={'id':["cnnIncldHlder","articleCommentsContainer","featuredContent","superstarsWidget","shareMenuContainer","rssMenuContainer","storyBrandingBanner","cnnRightCol","siteFeatures","quigo628","rightColumn","clickIncludeBox","cnnHeaderRightCol","cnnSCFontLabel","cnnSnapShotBottomRight","cnnSCFontButtons","rightColumn"]}),
                        dict(name='p', attrs={'class':["cnnTopics"]}),
                        dict(name='td', attrs={'class':["cnnRightRail"]}),
                        dict(name='table', attrs={'class':["cnnTMbox"]}),
                        dict(name='ul', attrs={'id':["cnnTopNav","cnnBotNav","cnnSBNav"]}),
                        ]

   # def print_version(self, url):
   #     return 'http://www.printthis.clickability.com/pt/printThis?clickMap=printThis&fb=Y&url=' + url

    feeds =  [
             ('Top News', 'http://rss.cnn.com/rss/cnn_topstories.rss'),
             ('World', 'http://rss.cnn.com/rss/cnn_world.rss'),
             ('U.S.', 'http://rss.cnn.com/rss/cnn_us.rss'),
             ('Sports', 'http://rss.cnn.com/rss/si_topstories.rss'),
             ('Business', 'http://rss.cnn.com/rss/money_latest.rss'),
             ('Politics', 'http://rss.cnn.com/rss/cnn_allpolitics.rss'),
             ('Law', 'http://rss.cnn.com/rss/cnn_law.rss'),
             ('Technology', 'http://rss.cnn.com/rss/cnn_tech.rss'),
             ('Science & Space', 'http://rss.cnn.com/rss/cnn_space.rss'),
             ('Health', 'http://rss.cnn.com/rss/cnn_health.rss'),
             ('Entertainment', 'http://rss.cnn.com/rss/cnn_showbiz.rss'),
             ('Education', 'http://rss.cnn.com/rss/cnn_education.rss'),
             ('Offbeat', 'http://rss.cnn.com/rss/cnn_offbeat.rss'),
             ('Most Popular', 'http://rss.cnn.com/rss/cnn_mostpopular.rss')
             ]
