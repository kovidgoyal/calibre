.. _news:

Adding your favorite news website
==================================

calibre has a powerful, flexible and easy-to-use framework for downloading news from the Internet and converting it into an e-book. The following will show you, by means of examples, how to get news from various websites.

To gain an understanding of how to use the framework, follow the examples in the order listed below:

.. contents::
    :depth: 2
    :local:

Completely automatic fetching
-------------------------------

If your news source is simple enough, calibre may well be able to fetch it
completely automatically, all you need to do is provide the URL. calibre
gathers all the information needed to download a news source into a
:term:`recipe`. In order to tell calibre about a news source, you have to
create a :term:`recipe` for it. Let's see some examples:

.. _calibre_blog:

The calibre blog
~~~~~~~~~~~~~~~~~~~

The calibre blog is a blog of posts that describe many useful calibre features
in a simple and accessible way for new calibre users. In order to download this
blog into an e-book, we rely on the :term:`RSS` feed of the blog::

    https://blog.calibre-ebook.com/feeds/posts/default

I got the RSS URL by looking under "Subscribe to" at the bottom of the blog
page and choosing :guilabel:`Posts->Atom`. To make calibre download the feeds and convert
them into an e-book, you should right click the :guilabel:`Fetch news` button
and then the :guilabel:`Add a custom news source` menu item and then the
:guilabel:`New Recipe` button. A dialog similar to that shown below should open up.

.. image:: images/custom_news.png
    :align: center

First enter ``calibre Blog`` into the :guilabel:`Recipe title` field. This will be the title of the e-book that will be created from the articles in the above feeds. 

The next two fields (:guilabel:`Oldest article` and :guilabel:`Max. number of articles`) allow you some control over how many articles should be downloaded from each feed, and they are pretty self explanatory.

To add the feeds to the recipe, enter the feed title and the feed URL and click
the :guilabel:`Add feed` button. Once you have added the feed, simply click the
:guilabel:`Save` button and you're done! Close the dialog.

To test your new :term:`recipe`, click the :guilabel:`Fetch news` button and in the :guilabel:`Custom news sources` sub-menu click :guilabel:`calibre Blog`. After a couple of minutes, the newly downloaded e-book of blog posts will appear in the main library view (if you have your reader connected, it will be put onto the reader instead of into the library). Select it and hit the :guilabel:`View` button to read!

The reason this worked so well, with so little effort is that the blog provides *full-content* :term:`RSS` feeds, i.e., the article content is embedded in the feed itself. For most news sources that provide news in this fashion, with *full-content* feeds, you don't need any more effort to convert them to e-books. Now we will look at a news source that does not provide full content feeds. In such feeds, the full article is a webpage and the feed only contains a link to the webpage with a short summary of the article. 

.. _bbc:

bbc.co.uk
~~~~~~~~~~~~~~

Lets try the following two feeds from *The BBC*:

    #. News Front Page: https://newsrss.bbc.co.uk/rss/newsonline_world_edition/front_page/rss.xml
    #. Science/Nature: https://newsrss.bbc.co.uk/rss/newsonline_world_edition/science/nature/rss.xml

Follow the procedure outlined in :ref:`calibre_blog` above to create a recipe for *The BBC* (using the feeds above). Looking at the downloaded e-book, we see that calibre has done a creditable job of extracting only the content you care about from each article's webpage. However, the extraction process is not perfect. Sometimes it leaves in undesirable content like menus and navigation aids or it removes content that should have been left alone, like article headings. In order, to have perfect content extraction, we will need to customize the fetch process, as described in the next section. 

Customizing the fetch process
--------------------------------

When you want to perfect the download process, or download content from a particularly complex website, you can avail yourself of all the power and flexibility of the :term:`recipe` framework. In order to do that, in the :guilabel:`Add custom news sources` dialog, simply click the :guilabel:`Switch to Advanced mode` button.

The easiest and often most productive customization is to use the print version of the online articles. The print version typically has much less cruft and translates much more smoothly to an e-book. Let's try to use the print version of the articles from *The BBC*.

Using the print version of bbc.co.uk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first step is to look at the e-book we downloaded previously from :ref:`bbc`. At the end of each article, in the e-book is a little blurb telling you where the article was downloaded from. Copy and paste that URL into a browser. Now on the article webpage look for a link that points to the "Printable version". Click it to see the print version of the article. It looks much neater! Now compare the two URLs. For me they were:

    Article URL
        https://news.bbc.co.uk/2/hi/science/nature/7312016.stm

    Print version URL
        https://newsvote.bbc.co.uk/mpapps/pagetools/print/news.bbc.co.uk/2/hi/science/nature/7312016.stm

So it looks like to get the print version, we need to prefix every article URL with:
    
    newsvote.bbc.co.uk/mpapps/pagetools/print/

Now in the :guilabel:`Advanced Mode` of the Custom  news sources dialog, you should see something like (remember to select *The BBC* recipe before switching to advanced mode):

.. image:: images/bbc_advanced.png
    :align: center

You can see that the fields from the :guilabel:`Basic mode` have been translated to python code in a straightforward manner. We need to add instructions to this recipe to use the print version of the articles. All that's needed is to add the following two lines:

.. code-block:: python

    def print_version(self, url):
        return url.replace('https://', 'https://newsvote.bbc.co.uk/mpapps/pagetools/print/')

This is python, so indentation is important. After you've added the lines, it should look like:

.. image:: images/bbc_altered.png
    :align: center

In the above, ``def print_version(self, url)`` defines a *method* that is called by calibre for every article. ``url`` is the URL of the original article. What ``print_version`` does is take that url and replace it with the new URL that points to the print version of the article. To learn about `python <https://www.python.org>`_ see the `tutorial <https://docs.python.org/2/tutorial/>`_.

Now, click the :guilabel:`Add/update recipe` button and your changes will be saved. Re-download the e-book. You should have a much improved e-book. One of the problems with the new version is that the fonts on the print version webpage are too small. This is automatically fixed when converting to an e-book, but even after the fixing process, the font size of the menus and navigation bar to become too large relative to the article text. To fix this, we will do some more customization, in the next section.

Replacing article styles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the previous section, we saw that the font size for articles from the print version of *The BBC* was too small. In most websites, *The BBC* included, this font size is set by means of :term:`CSS` stylesheets. We can disable the fetching of such stylesheets by adding the line::

    no_stylesheets = True

.. _bbc1:

The recipe now looks like:

.. image:: images/bbc_altered1.png
    :align: center

The new version looks pretty good. If you're a perfectionist, you'll want to read the next section, which deals with actually modifying the downloaded content.

Slicing and dicing
~~~~~~~~~~~~~~~~~~~~~~~

calibre contains very powerful and flexible abilities when it comes to manipulating downloaded content. To show off a couple of these, let's look at our old friend the :ref:`The BBC <bbc1>` recipe again. Looking at the source code (:term:`HTML`) of a couple of articles (print version), we see that they have a footer that contains no useful information, contained in 

.. code-block:: html

    <div class="footer">
    ...
    </div>

This can be removed by adding::

    remove_tags    = [dict(name='div', attrs={'class':'footer'})]

to the recipe. Finally, lets replace some of the :term:`CSS` that we disabled earlier, with our own :term:`CSS` that is suitable for conversion to an e-book::

    extra_css      = '.headline {font-size: x-large;} \n .fact { padding-top: 10pt  }' 

With these additions, our recipe has become "production quality", indeed it is very close to the actual recipe used by calibre for the *BBC*, shown below:

.. literalinclude:: ../../../recipes/bbc.recipe

This :term:`recipe` explores only the tip of the iceberg when it comes to the power of calibre. To explore more of the abilities of calibre we'll examine a more complex real life example in the next section.

Real life example
~~~~~~~~~~~~~~~~~~~~~

A reasonably complex real life example that exposes more of the :term:`API` of ``BasicNewsRecipe`` is the :term:`recipe` for *The New York Times*

.. code-block:: python

   import string, re
   from calibre import strftime
   from calibre.web.feeds.recipes import BasicNewsRecipe
   from calibre.ebooks.BeautifulSoup import BeautifulSoup

   class NYTimes(BasicNewsRecipe):
    
       title       = 'The New York Times'
       __author__  = 'Kovid Goyal'
       description = 'Daily news from the New York Times'
       timefmt = ' [%a, %d %b, %Y]'
       needs_subscription = True
       remove_tags_before = dict(id='article')
       remove_tags_after  = dict(id='article')
       remove_tags = [dict(attrs={'class':['articleTools', 'post-tools', 'side_tool', 'nextArticleLink clearfix']}), 
                   dict(id=['footer', 'toolsRight', 'articleInline', 'navigation', 'archive', 'side_search', 'blog_sidebar', 'side_tool', 'side_index']), 
                   dict(name=['script', 'noscript', 'style'])]
       encoding = 'cp1252'
       no_stylesheets = True
       extra_css = 'h1 {font: sans-serif large;}\n.byline {font:monospace;}'
    
       def get_browser(self):
           br = BasicNewsRecipe.get_browser()
           if self.username is not None and self.password is not None:
               br.open('https://www.nytimes.com/auth/login')
               br.select_form(name='login')
               br['USERID']   = self.username
               br['PASSWORD'] = self.password
               br.submit()
           return br
    
       def parse_index(self):
           soup = self.index_to_soup('https://www.nytimes.com/pages/todayspaper/index.html')
        
           def feed_title(div):
               return ''.join(div.findAll(text=True, recursive=False)).strip()
        
           articles = {}
           key = None
           ans = []
           for div in soup.findAll(True, 
                attrs={'class':['section-headline', 'story', 'story headline']}):
            
                if div['class'] == 'section-headline':
                    key = string.capwords(feed_title(div))
                    articles[key] = []
                    ans.append(key)
            
                elif div['class'] in ['story', 'story headline']:
                    a = div.find('a', href=True)
                    if not a:
                        continue
                    url = re.sub(r'\?.*', '', a['href'])
                    url += '?pagewanted=all'
                    title = self.tag_to_string(a, use_alt=True).strip()
                    description = ''
                    pubdate = strftime('%a, %d %b')
                    summary = div.find(True, attrs={'class':'summary'})
                    if summary:
                        description = self.tag_to_string(summary, use_alt=False)
                
                    feed = key if key is not None else 'Uncategorized'
                    if not articles.has_key(feed):
                        articles[feed] = []
                    if not 'podcasts' in url:
                        articles[feed].append(
                                  dict(title=title, url=url, date=pubdate, 
                                       description=description,
                                       content=''))
           ans = self.sort_index_by(ans, {'The Front Page':-1, 'Dining In, Dining Out':1, 'Obituaries':2})
           ans = [(key, articles[key]) for key in ans if articles.has_key(key)]
           return ans
    
       def preprocess_html(self, soup):
           refresh = soup.find('meta', {'http-equiv':'refresh'})
           if refresh is None:
               return soup
           content = refresh.get('content').partition('=')[2]
           raw = self.browser.open('https://www.nytimes.com'+content).read()
           return BeautifulSoup(raw.decode('cp1252', 'replace'))
 

We see several new features in this :term:`recipe`. First, we have::

    timefmt = ' [%a, %d %b, %Y]'

This sets the displayed time on the front page of the created e-book to be in the format,
``Day, Day_Number Month, Year``. See :attr:`timefmt <calibre.web.feeds.news.BasicNewsRecipe.timefmt>`.

Then we see a group of directives to cleanup the downloaded :term:`HTML`::

    remove_tags_before = dict(name='h1')
    remove_tags_after  = dict(id='footer')
    remove_tags = ...

These remove everything before the first ``<h1>`` tag and everything after the first tag whose id is ``footer``. See :attr:`remove_tags <calibre.web.feeds.news.BasicNewsRecipe.remove_tags>`, :attr:`remove_tags_before <calibre.web.feeds.news.BasicNewsRecipe.remove_tags_before>`, :attr:`remove_tags_after <calibre.web.feeds.news.BasicNewsRecipe.remove_tags_after>`.

The next interesting feature is::

    needs_subscription = True
    ...
    def get_browser(self):
        ...

``needs_subscription = True`` tells calibre that this recipe needs a username and password in order to access the content. This causes, calibre to ask for a username and password whenever you try to use this recipe. The code in :meth:`calibre.web.feeds.news.BasicNewsRecipe.get_browser` actually does the login into the NYT website. Once logged in, calibre will use the same, logged in, browser instance to fetch all content. See `mechanize <https://github.com/jjlee/mechanize>`_ to understand the code in ``get_browser``.

The next new feature is the
:meth:`calibre.web.feeds.news.BasicNewsRecipe.parse_index` method. Its job is
to go to https://www.nytimes.com/pages/todayspaper/index.html and fetch the list
of articles that appear in *todays* paper. While more complex than simply using
:term:`RSS`, the recipe creates an e-book that corresponds very closely to the
days paper. ``parse_index`` makes heavy use of `BeautifulSoup
<https://www.crummy.com/software/BeautifulSoup/documentation.html>`_ to parse
the daily paper webpage. You can also use other, more modern parsers if you
dislike BeatifulSoup. calibre comes with `lxml <http://lxml.de/>`_ and
`html5lib <https://github.com/html5lib/html5lib-python>`_, which are the
recommended parsers. To use them, replace the call to ``index_to_soup()`` with
the following::
    
    raw = self.index_to_soup(url, raw=True)
    # For html5lib
    import html5lib
    root = html5lib.parse(raw, namespaceHTMLElements=False, treebuilder='lxml')
    # For the lxml html 4 parser
    from lxml import html
    root = html.fromstring(raw)

The final new feature is the :meth:`calibre.web.feeds.news.BasicNewsRecipe.preprocess_html` method. It can be used to perform arbitrary transformations on every downloaded HTML page. Here it is used to bypass the ads that the nytimes shows you before each article.

Tips for developing new recipes
---------------------------------

The best way to develop new recipes is to use the command line interface. Create the recipe using your favorite python editor and save it to a file say :file:`myrecipe.recipe`. The `.recipe` extension is required. You can download content using this recipe with the command::

    ebook-convert myrecipe.recipe .epub --test -vv --debug-pipeline debug

The command :command:`ebook-convert` will download all the webpages and save
them to the EPUB file :file:`myrecipe.epub`. The ``-vv`` option makes
ebook-convert spit out a lot of information about what it is doing. The
:option:`ebook-convert-recipe-input --test` option makes it download only a couple of articles from at most two
feeds. In addition, ebook-convert will put the downloaded HTML into the
``debug/input`` directory, where ``debug`` is the directory you specified in
the :option:`ebook-convert --debug-pipeline` option. 

Once the download is complete, you can look at the downloaded :term:`HTML` by opening the file :file:`debug/input/index.html` in a browser. Once you're satisfied that the download and preprocessing is happening correctly, you can generate e-books in different formats as shown below::

    ebook-convert myrecipe.recipe myrecipe.epub
    ebook-convert myrecipe.recipe myrecipe.mobi
    ...


If you're satisfied with your recipe, and you feel there is enough demand to justify its inclusion into the set of built-in recipes, post your recipe in the `calibre recipes forum <https://www.mobileread.com/forums/forumdisplay.php?f=228>`_ to share it with other calibre users.

.. note:: 
    On OS X, the command line tools are inside the calibre bundle, for example,
    if you installed calibre in :file:`/Applications` the command line tools
    are in :file:`/Applications/calibre.app/Contents/console.app/Contents/MacOS/`.

.. seealso::

    :doc:`generated/en/ebook-convert`
        The command line interface for all e-book conversion.


Further reading
--------------------

To learn more about writing advanced recipes using some of the facilities, available in ``BasicNewsRecipe`` you should consult the following sources:

    :ref:`API documentation <news_recipe>`
        Documentation of the ``BasicNewsRecipe`` class and all its important methods and fields.

    `BasicNewsRecipe <https://github.com/kovidgoyal/calibre/blob/master/src/calibre/web/feeds/news.py>`_
        The source code of ``BasicNewsRecipe``

    `Built-in recipes <https://github.com/kovidgoyal/calibre/tree/master/recipes>`_
        The source code for the built-in recipes that come with calibre

    `The calibre recipes forum <https://www.mobileread.com/forums/forumdisplay.php?f=228>`_
        Lots of knowledgeable calibre recipe writers hang out here.


API documentation
--------------------

.. toctree::
    
    news_recipe
