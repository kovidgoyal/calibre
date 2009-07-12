#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
nytimes.com
'''
import re
from calibre.web.feeds.recipes import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class NYTimes(BasicNewsRecipe):

    title       = 'NYTimes Top Stories'
    __author__  = 'Greg Riker'
    language = _('English')
    description = 'Top Stories from the New York Times'
    #max_articles_per_feed = 3
    timefmt = ''
    needs_subscription = False
    remove_tags_before = dict(id='article')
    remove_tags_after  = dict(id='article')
    remove_tags = [dict(attrs={'class':['articleTools', 'post-tools', 'side_tool', 'nextArticleLink', 'clearfix']}),
                   dict(id=['footer', 'toolsRight', 'articleInline', 'navigation', 'archive', 'side_search', 'blog_sidebar', 'side_tool', 'side_index']),
                   dict(name=['script', 'noscript', 'style'])]
    encoding = 'cp1252'
    no_stylesheets = True
    #extra_css = 'h1 {font: sans-serif large;}\n.byline {font:monospace;}'
    extra_css = '.headline  {text-align:left;}\n\
                 .byline    {font:monospace; margin-bottom:0px;}\n\
                 .source    {align:left;}\n\
                 .credit    {align:right;}\n'


    flatPeriodical = True

    def parse_index(self):
        soup = self.index_to_soup('http://www.nytimes.com/pages/todaysheadlines/')

        def feed_title(div):
            return ''.join(div.findAll(text=True, recursive=False)).strip()

        articles = {}

        ans = []
        if self.flatPeriodical :
            feed = key = 'All Top Stories'
            articles[key] = []
            ans.append(key)
        else :
            key = None

        sections = { 'topstories'   :   'Top Stories',
                     'world'        :   'World',
                     'us'           :   'U.S.',
                     'politics'     :   'Politics',
                     'business'     :   'Business',
                     'technology'   :   'Technology',
                     'sports'       :   'Sports',
                     'arts'         :   'Arts',
                     'newyorkregion':   'New York/Region',
                     'travel'       :   'Travel',
                     'editorials'   :   'Editorials',
                     'oped'         :   'Op-Ed'
                   }

        #excludeSectionKeywords = ['World','U.S.', 'Politics','Business','Technology','Sports','Arts','New York','Travel', 'Editorials', 'Op-Ed']
        excludeSectionKeywords = []

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
                            ans.append(key)

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
                            title = sections[section] + " : " + title
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
                            feed = key

                        if not articles.has_key(feed):
                            if self.verbose > 2 : self.log( "adding %s to articles[]" % feed)
                            articles[feed] = []
                        if self.verbose > 2 : self.log( "     adding: %s to articles[%s]\n" % (title, feed))
                        articles[feed].append(
                            dict(title=title, url=url, date=pubdate,
                                 description=description, author=author, content=''))

        ans = self.sort_index_by(ans, {'Top Stories':-1})
        ans = [(key, articles[key]) for key in ans if articles.has_key(key)]
        #sys.exit(1)

        return ans

    def postprocess_html(self,soup, True):
        if self.verbose > 2 : self.log(" ********** recipe.postprocess_html ********** ")

        # Change captions to italic -1
        for caption in soup.findAll(True, {'class':'caption'}) :
            emTag = Tag(soup, "em")
            #emTag['class'] = "caption"
            #emTag['font-size-adjust'] = "-1"
            emTag.insert(0, caption.contents[0])
            hrTag = Tag(soup, 'hr')
            emTag.insert(1, hrTag)
            caption.replaceWith(emTag)


        # Change <nyt_headline> to <h2>
        headline = soup.div.div.div.div.div.h1.nyt_headline
        tag = Tag(soup, "h2")
        tag['class'] = "headline"
        tag.insert(0, headline.contents[0])
        soup.h1.replaceWith(tag)

        return soup

    def postprocess_book(self, oeb, opts, log) :
        log( " ********** recipe.postprocess_book ********** ")
        log( list(oeb.toc) )
        log( "oeb: %s" % oeb.toc)
        log( "opts: %s" % opts.verbose)
        for sections in oeb.toc :
            log( "section:")
            for articleTOC in sections:
                log( "      title: %s" % articleTOC.title)
                log( "     author: %s" % articleTOC.author)
                log( "description: %s" % articleTOC.description)
                log( "       href: %s" % articleTOC.href)
                log( "    content: %s" % oeb.manifest.hrefs[articleTOC.href])
        return
