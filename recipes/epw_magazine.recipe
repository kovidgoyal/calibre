from calibre.web.feeds.news import BasicNewsRecipe, classes
from collections import OrderedDict


def absurl(x):
    if x.startswith('/'):
        x = 'http://www.epw.in' + x
        return x


class epw(BasicNewsRecipe):
    title = 'EPW Magazine'
    __author__ = 'unkn0wn'
    description = 'Economic and Political news from India'
    no_stylesheets = True
    use_embedded_content = False
    encoding = 'utf-8'
    language = 'en_IN'
    remove_attributes = ['style', 'height', 'width']
    masthead_url = 'http://www.epw.in/system/files/epw_masthead.png'
    ignore_duplicate_articles = {'title', 'url'}

    keep_only_tags = [
        dict(name='h1', attrs={'id': 'page-title'}),
        classes(
            'field-name-field-secondary-title field-type-text region-content updated_field'
        )
    ]
    remove_tags = [
        classes('premium-message node-readmore tag_container mobile_article_info')
    ]

    def parse_index(self):
        soup = self.index_to_soup('https://www.epw.in/journal/epw-archive')
        div = soup.find('div', **classes('fieldset-wrapper'))
        a = div.find('a', href=lambda x: x and x.startswith('/journal/'))
        url = absurl(a['href'])
        self.log(self.tag_to_string(a))
        soup = self.index_to_soup(url)

        view = soup.findAll('div', **classes('views-field-field-cover-image'))[0]
        try:
            self.cover_url = view.find('img', src=True)['src'].split('?')[0].replace(
                '/styles/freeissue/public', ''
            )
        except Exception:
            # sometimes they dont add img src
            self.cover_url = 'https://www.epw.in/sites/default/files/cache/cover_images/2022/Cover_4June2022_Big.gif'

        feeds = OrderedDict()

        div = soup.find('div', attrs={'id': 'block-system-main'})
        for a in div.findAll('a', href=lambda x: x and x.startswith('/journal/')):
            articles = []
            url = absurl(a['href'])
            title = self.tag_to_string(a)
            view = a.findParent('h4'
                                ).findParent('div', **classes('views-field-title'))
            new = view.find_next_sibling('div')
            if new:
                desc = self.tag_to_string(new)
            h3 = view.findParent('div',
                                 **classes('views-row')).find_previous_sibling('h3')
            section_title = self.tag_to_string(h3)
            self.log('\t', title)
            self.log('\t', desc)
            self.log('\t\t', url)
            articles.append({'title': title, 'url': url, 'description': desc})

            if articles:
                if section_title not in feeds:
                    feeds[section_title] = []
                feeds[section_title] += articles
        ans = [(key, val) for key, val in feeds.items()]
        return ans
