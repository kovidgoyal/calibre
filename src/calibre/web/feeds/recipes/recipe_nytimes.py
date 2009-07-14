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
    #max_articles_per_feed = 3
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
    #extra_css = 'h1 {font: sans-serif large;}\n.byline {font:monospace;}'
    extra_css = '.headline  {text-align:left;}\n\
                 .byline    {font:monospace; margin-bottom:0px;}\n\
                 .source    {align:left;}\n\
                 .credit    {align:right;}\n'


    flatPeriodical = True
    feed = None
    ans = []

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
        Convenience method that takes an URL to the index page and returns
        a `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_
        of it.
        
        This is an OVERRIDE of the method provided in news.py to solve an encoding problem
        with NYTimes index pages which seem to be encoded in a wonderful blend

        `url_or_raw`: Either a URL or the downloaded index page as a string
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

        if self.verbose :
            self.log( "  document encoding: '%s'" % docEncoding)
        if docEncoding != self.encoding :
            soup = get_the_soup(docEncoding, url_or_raw)         

        return soup

    def parse_index(self):
        articles = {}

        if self.flatPeriodical :
            self.feed = key = 'All Top Stories'
            articles[key] = []
            self.ans.append(key)
        else :
            key = None

        '''
        def feed_title(div):
            return ''.join(div.findAll(text=True, recursive=False)).strip()
        '''
        

        sections = {
                     'arts'             :   'Arts',
                     'business'         :   'Business',
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

        '''
        excludeSectionKeywords = ['Arts','Business','Editorials','Health','Magazine','Media',
                                   'New York','Op-Ed','Politics','Science','Sports','Technology',
                                   'Top Stories','Travel','U.S.','World']
        '''                                   
        excludeSectionKeywords = ['Arts','Business','Editorials','Health','Magazine','Media',
                                   'New York','Politics','Science','Sports','Technology',
                                   'Top Stories','Travel','U.S.','World']
        
        #excludeSectionKeywords = []
        
        soup = self.index_to_soup('http://www.nytimes.com/pages/todaysheadlines/')

        # Fetch the outer table
        table = soup.find('table')
        previousTable = table
        contentTable = None

        # Find the deepest table containing the stories
        while True :
            table = table.find('table')
            if table.find(text=re.compile('top stories start')) :
                if self.verbose > 2 : self.log( "*********** dropping one level deeper **************")
                previousTable = table
                continue
            else :
                if self.verbose > 2 : self.log( "found table with top stories")
                table = previousTable
                if self.verbose > 2 : self.log( "lowest table containing 'top stories start:\n%s" % table)
                break

        # There are multiple subtables, find the one containing the stories
        for block in table.findAll('table') :
            if block.find(text=re.compile('top stories start')) :
                if self.verbose > 2 : self.log( "found subtable with top stories")
                table = block
                if self.verbose > 2 : self.log( "lowest subtable containing 'top stories start:\n%s" % table)
                break
            else :
                if self.verbose > 2 : self.log( "trying next subtable")
                continue

        # Again there are multiple subtables, find the one containing the stories
        for storyblock in table.findAll('table') :
            if storyblock.find(text=re.compile('top stories start')) :
                if self.verbose > 2 : self.log( "found subsubtable with top stories\n" )
                # table = storyblock
                if self.verbose > 2 : self.log( "\nlowest subsubtable containing 'top stories start:\n%s" % storyblock)
                break
            else :
                if self.verbose > 2 : self.log( "trying next subsubtable")
                continue

        skipThisSection = False

        # Within this table are <font face="times new roman, times, san serif"> entries
        for tr in storyblock.findAllNext('tr'):
            if tr.find('span') is not None :

                sectionblock = tr.find(True, attrs={'face':['times new roman, times,sans serif',
                                                         'times new roman,times, sans serif',
                                                         'times new roman, times, sans serif']})
                if self.verbose > 2 : self.log( "----------- new tr ----------------")
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
                            if self.verbose > 2 : self.log( "sectionTitle: %s" % sections[section])

                        if not sections.has_key(section) :
                            self.log( "Unrecognized section id: %s, skipping" % section )
                            skipThisSection = True
                            break

                        # Check for excluded section
                        if len(excludeSectionKeywords):
                            key = sections[section]
                            excluded = re.compile('|'.join(excludeSectionKeywords))
                            if excluded.search(key) or articles.has_key(key):
                                if self.verbose > 2 : self.log("Skipping section %s" % key)
                                skipThisSection = True
                                break

                        if not self.flatPeriodical :
                            articles[key] = []
                            self.ans.append(key)

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
                        if self.flatPeriodical :
                            # prepend the section name
                            title = sections[section] + " &middot; " + title
                        if not isinstance(title, unicode):
                            title = title.decode('utf-8', 'replace')
                        description = descriptions[i]
                        if len(bylines) == articleCount :
                            author = bylines[i]
                        else :
                            author = None

                        if self.verbose > 2 : self.log( "      title: %s" % title)
                        if self.verbose > 2 : self.log( "        url: %s" % url)
                        if self.verbose > 2 : self.log( "     author: %s" % author)
                        if self.verbose > 2 : self.log( "description: %s" % description)

                        if not self.flatPeriodical :
                            self.feed = key

                        # Check for duplicates
                        duplicateFound = False
                        if self.flatPeriodical and len(articles[self.feed]) > 1:
                            #print articles[self.feed]
                            for article in articles[self.feed] :
                                #print "comparing %s\n %s\n" % (url, article['url'])
                                if url == article['url'] :
                                    duplicateFound = True
                                    break
                            #print
                            
                            if duplicateFound:        
                                # Continue fetching, don't add this article
                                print "  skipping duplicate %s" % article['url']
                                continue        

                        if not articles.has_key(self.feed):
                            if self.verbose > 2 : self.log( "adding %s to articles[]" % self.feed)
                            articles[self.feed] = []
                        if self.verbose > 2 : self.log( "     adding: %s to articles[%s]\n" % (title, self.feed))
                        articles[self.feed].append(
                            dict(title=title, url=url, date=pubdate,
                                 description=description, author=author, content=''))

        self.ans = self.sort_index_by(self.ans, {'Top Stories':-1})
        self.ans = [(key, articles[key]) for key in self.ans if articles.has_key(key)]
        #sys.exit(1)

        return self.ans

    def preprocess_html(self, soup):
        refresh = soup.find('meta', {'http-equiv':'refresh'})
        if refresh is None:
            return soup
        content = refresh.get('content').partition('=')[2]
        raw = self.browser.open('http://www.nytimes.com'+content).read()
        return BeautifulSoup(raw.decode('cp1252', 'replace'))

    def postprocess_html(self,soup, True):
        if self.verbose > 2 : self.log(" ********** recipe.postprocess_html ********** ")
        # Change class="kicker" to <h3>
        kicker = soup.find(True, {'class':'kicker'})
        if kicker is not None :
            print "changing kicker to <h3>"
            print kicker
            h3Tag = Tag(soup, "h3")
            h3Tag.insert(0, kicker.contents[0])
            kicker.replaceWith(h3Tag)

        # Change captions to italic -1
        for caption in soup.findAll(True, {'class':'caption'}) :
            if caption is not None:
                emTag = Tag(soup, "em")
                #emTag['class'] = "caption"
                #emTag['font-size-adjust'] = "-1"
                emTag.insert(0, caption.contents[0])
                hrTag = Tag(soup, 'hr')
                emTag.insert(1, hrTag)
                caption.replaceWith(emTag)

        # Change <nyt_headline> to <h2>
        headline = soup.find("nyt_headline")
        if headline is not None :
            tag = Tag(soup, "h2")
            tag['class'] = "headline"
            tag.insert(0, headline.contents[0])
            soup.h1.replaceWith(tag)

        # Change <h1> to <h3> - used in editorial blogs
        masthead = soup.find("h1")
        if masthead is not None :
            # Nuke the href
            if masthead.a is not None :
                del(masthead.a['href'])
            tag = Tag(soup, "h3")
            tag.insert(0, masthead.contents[0])
            soup.h1.replaceWith(tag)
        '''
        # Change subheads to <h3>
        for subhead in soup.findAll(True, {'class':'bold'}) :
            h3Tag = Tag(soup, "h3")
            h3Tag.insert(0, subhead.contents[0])
            subhead.replaceWith(h3Tag)
        '''
        # Change <span class="bold"> to <b>
        for subhead in soup.findAll(True, {'class':'bold'}) :
            bTag = Tag(soup, "b")
            bTag.insert(0, subhead.contents[0])
            subhead.replaceWith(bTag)

        return soup

