#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
nytimes.com
'''
import re
from calibre import entity_to_unicode
from calibre.web.feeds.recipes import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class NYTimes(BasicNewsRecipe):

    title       = 'New York Times Top Stories'
    __author__  = 'GRiker'
    language = _('English')
    description = 'Top Stories from the New York Times'
    
    # List of sections typically included in Top Stories.  Use a keyword from the
    # right column in the excludeSectionKeywords[] list to skip downloading that section
    sections = {
                 'arts'             :   'Arts',
                 'business'         :   'Business',
                 'diningwine'       :   'Dining & Wine',
                 'editorials'       :   'Editorials',
                 'health'           :   'Health',
                 'magazine'         :   'Magazine',
                 'mediaadvertising' :   'Media & Advertising',
                 'newyorkregion'    :   'New York/Region',
                 'oped'             :   'Op-Ed',
                 'politics'         :   'Politics',
                 'science'          :   'Science',
                 'sports'           :   'Sports',
                 'technology'       :   'Technology',
                 'topstories'       :   'Top Stories',
                 'travel'           :   'Travel',
                 'us'               :   'U.S.',
                 'world'            :   'World'
               }

    # By default, no sections are skipped.  
    excludeSectionKeywords = []

    # To skip sections containing the word 'Sports' or 'Dining', use:
    # excludeSectionKeywords = ['Sports', 'Dining']

    # Fetch only Business and Technology
    #excludeSectionKeywords = ['Arts','Dining','Editorials','Health','Magazine','Media','Region','Op-Ed','Politics','Science','Sports','Top Stories','Travel','U.S.','World']

    # Fetch only Top Stories
    #excludeSectionKeywords = ['Arts','Business','Dining','Editorials','Health','Magazine','Media','Region','Op-Ed','Politics','Science','Sports','Technology','Travel','U.S.','World']
    
    # The maximum number of articles that will be downloaded
    max_articles_per_feed = 50

    timefmt = ''
    needs_subscription = True
    remove_tags_after  = dict(attrs={'id':['comments']})
    remove_tags = [dict(attrs={'class':['articleTools', 'post-tools', 'side_tool', 'nextArticleLink', 
                               'clearfix', 'nextArticleLink clearfix','inlineSearchControl',
                               'columnGroup','entry-meta','entry-response module','jumpLink','nav',
                               'columnGroup advertisementColumnGroup', 'kicker entry-category']}),
                   dict(id=['footer', 'toolsRight', 'articleInline', 'navigation', 'archive', 
                            'side_search', 'blog_sidebar', 'side_tool', 'side_index', 'login',
                            'blog-header','searchForm','NYTLogo','insideNYTimes','adxToolSponsor',
                            'adxLeaderboard']),
                   dict(name=['script', 'noscript', 'style','hr'])]
    encoding = 'cp1252'
    no_stylesheets = True
    extra_css = '.headline  {text-align:left;}\n\
                 .byline    {font:monospace; margin-bottom:0px;}\n\
                 .source    {align:left;}\n\
                 .credit    {text-align:right;font-size:smaller;}\n'

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        if self.username is not None and self.password is not None:
            br.open('http://www.nytimes.com/auth/login')
            br.select_form(name='login')
            br['USERID']   = self.username
            br['PASSWORD'] = self.password
            br.submit()
        return br

    def index_to_soup(self, url_or_raw, raw=False):
        '''
        OVERRIDE of class method
        deals with various page encodings between index and articles
        '''
        def get_the_soup(docEncoding, url_or_raw, raw=False) :
            if re.match(r'\w+://', url_or_raw):
                f = self.browser.open(url_or_raw)
                _raw = f.read()
                f.close()
                if not _raw:
                    raise RuntimeError('Could not fetch index from %s'%url_or_raw)
            else:
                _raw = url_or_raw
            if raw:
                return _raw
                
            if not isinstance(_raw, unicode) and self.encoding:
                _raw = _raw.decode(docEncoding, 'replace')
            massage = list(BeautifulSoup.MARKUP_MASSAGE)
            massage.append((re.compile(r'&(\S+?);'), lambda match: entity_to_unicode(match, encoding=self.encoding)))
            return BeautifulSoup(_raw, markupMassage=massage)
        
        # Entry point
        soup = get_the_soup( self.encoding, url_or_raw )
        contentType = soup.find(True,attrs={'http-equiv':'Content-Type'})
        docEncoding =  str(contentType)[str(contentType).find('charset=') + len('charset='):str(contentType).rfind('"')]
        if docEncoding == '' :
            docEncoding = self.encoding

        if docEncoding != self.encoding :
            soup = get_the_soup(docEncoding, url_or_raw)         

        return soup

    def parse_index(self):
        articles = {}
        ans = []

        feed = key = 'All Top Stories'
        articles[key] = []
        ans.append(key)
        
        soup = self.index_to_soup('http://www.nytimes.com/pages/todaysheadlines/')

        # Fetch the outer table
        table = soup.find('table')
        previousTable = table
        contentTable = None

        # Find the deepest table containing the stories
        while True :
            table = table.find('table')
            if table.find(text=re.compile('top stories start')) :
                previousTable = table
                continue
            else :
                table = previousTable
                break

        # There are multiple subtables, find the one containing the stories
        for block in table.findAll('table') :
            if block.find(text=re.compile('top stories start')) :
                table = block
                break
            else :
                continue

        # Again there are multiple subtables, find the one containing the stories
        for storyblock in table.findAll('table') :
            if storyblock.find(text=re.compile('top stories start')) :
                break
            else :
                continue

        skipThisSection = False

        # Within this table are <font face="times new roman, times, san serif"> entries
        for tr in storyblock.findAllNext('tr'):
            if tr.find('span') is not None :

                sectionblock = tr.find(True, attrs={'face':['times new roman, times,sans serif',
                                                         'times new roman,times, sans serif',
                                                         'times new roman, times, sans serif']})
                section = None
                bylines = []
                descriptions = []
                pubdate = None

                # Get the Section title
                for (x,i) in enumerate(sectionblock.contents) :
                    skipThisSection = False
                    # Extract the section title
                    if ('Comment' in str(i.__class__)) :
                        if 'start(name=' in i :
                            section = i[i.find('=')+1:-2]

                        if not self.sections.has_key(section) :
                            skipThisSection = True
                            break

                        # Check for excluded section
                        if len(self.excludeSectionKeywords):
                            key = self.sections[section]
                            excluded = re.compile('|'.join(self.excludeSectionKeywords))
                            if excluded.search(key) or articles.has_key(key):
                                if self.verbose : self.log("Skipping section %s" % key)
                                skipThisSection = True
                                break

                # Get the bylines and descriptions
                if not skipThisSection :
                    for (x,i) in enumerate(sectionblock.contents) :

                        # Extract the bylines and descriptions
                        if (i.string is not None) and       \
                           (i.string.strip() > "") and      \
                           not ('Comment' in str(i.__class__)) :

                            contentString = i.strip().encode('utf-8')
                            if contentString[0:3] == 'By ' :
                                bylines.append(contentString)
                            else :
                                descriptions.append(contentString)

                    # Fetch the article titles and URLs
                    articleCount = len(sectionblock.findAll('span'))
                    for (i,span) in enumerate(sectionblock.findAll('span')) :
                        a = span.find('a', href=True)
                        #if not a:
                            #continue
                        url = re.sub(r'\?.*', '', a['href'])
                        url += '?pagewanted=all'

                        title = self.tag_to_string(a, use_alt=True)
                        # prepend the section name
                        title = self.sections[section] + " &middot; " + title

                        if not isinstance(title, unicode):
                            title = title.decode('utf-8', 'replace')

                        description = descriptions[i]

                        if len(bylines) == articleCount :
                            author = bylines[i]
                        else :
                            author = None

                        # Check for duplicates
                        duplicateFound = False
                        if len(articles[feed]) > 1:
                            #print articles[feed]
                            for article in articles[feed] :
                                #print "comparing %s\n %s\n" % (url, article['url'])
                                if url == article['url'] :
                                    duplicateFound = True
                                    break
                            #print
                            
                            if duplicateFound:        
                                continue        

                        if not articles.has_key(feed):
                            articles[feed] = []
                        articles[feed].append(
                            dict(title=title, url=url, date=pubdate,
                                 description=description, author=author, content=''))

        ans = self.sort_index_by(ans, {'Top Stories':-1})
        ans = [(key, articles[key]) for key in ans if articles.has_key(key)]
        
        return ans

    def preprocess_html(self, soup):
        refresh = soup.find('meta', {'http-equiv':'refresh'})
        if refresh is None:
            return soup
        content = refresh.get('content').partition('=')[2]
        raw = self.browser.open('http://www.nytimes.com'+content).read()
        return BeautifulSoup(raw.decode('cp1252', 'replace'))

    def postprocess_html(self,soup, True):
        # Change class="kicker" to <h3>
        kicker = soup.find(True, {'class':'kicker'})
        if kicker is not None :
            h3Tag = Tag(soup, "h3")
            h3Tag.insert(0, self.tag_to_string(kicker))
            kicker.replaceWith(h3Tag)

        # Change captions to italic -1
        for caption in soup.findAll(True, {'class':'caption'}) :
            if caption is not None:
                emTag = Tag(soup, "em")
                #emTag['class'] = "caption"
                #emTag['font-size-adjust'] = "-1"
                emTag.insert(0, self.tag_to_string(caption))
                hrTag = Tag(soup, 'hr')
                emTag.insert(1, hrTag)
                caption.replaceWith(emTag)

        # Change <nyt_headline> to <h2>
        headline = soup.find("nyt_headline")
        if headline is not None :
            h2tag = Tag(soup, "h2")
            h2tag['class'] = "headline"
            h2tag.insert(0, self.tag_to_string(headline))
            headline.replaceWith(h2tag)

        # Change <h1> to <h3> - used in editorial blogs
        masthead = soup.find("h1")
        if masthead is not None :
            # Nuke the href
            if masthead.a is not None :
                del(masthead.a['href'])
            h3tag = Tag(soup, "h3")
            h3tag.insert(0, self.tag_to_string(masthead))
            masthead.replaceWith(h3tag)

        # Change <span class="bold"> to <b>
        for subhead in soup.findAll(True, {'class':'bold'}) :
            bTag = Tag(soup, "b")
            bTag.insert(0, self.tag_to_string(subhead))
            subhead.replaceWith(bTag)

        return soup
