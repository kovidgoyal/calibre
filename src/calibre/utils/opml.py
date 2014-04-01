__license__ = 'GPL 3'
__copyright__ = '2014, Kenny Billiau <kennybilliau@gmail.co'
__docformat__ = 'restructuredtext en'

import time
import xml.etree.ElementTree as ET

class OPML(object):

    def __init__(self, oldest_article = 7, max_articles = 100):
        self.doc = None # xml document
        self.outlines = None # parsed outline objects
        self.oldest_article = oldest_article
        self.max_articles = max_articles

    def load(self, filename):
        tree = ET.parse(filename)
        self.doc = tree.getroot()

    def parse(self):
        self.outlines = self.doc.findall(u"body/outline")

        for outline in self.outlines: # check for groups
            #if ('type' not in outline.attrib):
                feeds = [] # title, url
                for feed in outline.iter('outline'):
                    if 'type' in feed.attrib:
                        feeds.append( (feed.get('title'), feed.get('xmlUrl')) )
                outline.set('xmlUrl', feeds)
        
        return self.outlines

    def import_recipes(self, outlines):
        nr = 0
        #recipe_model = CustomRecipeModel(RecipeModel())
        for outline in outlines:
            src, title = self.options_to_profile(dict(
                nr=nr,
                title=unicode(outline.get('title')),
                feeds=outline.get('xmlUrl'),
                oldest_article=self.oldest_article,
                max_articles=self.max_articles,
                base_class='AutomaticNewsRecipe'
            ))
            try:
                compile_recipe(src)
                add_custom_recipe(title, src)
            except Exception as err:
                # error dialog should be placed somewhere where it can have a parent
                # Left it here as this way only failing feeds will silently fail
                error_dialog(None, _('Invalid input'),
                    _('<p>Could not create recipe. Error:<br>%s')%str(err)).exec_()
            nr+=1

            #recipe_model.add(title, src)


    def options_to_profile(self, recipe):
        classname = 'BasicUserRecipe'+str(recipe.get('nr'))+str(int(time.time()))
        title = recipe.get('title').strip()
        if not title:
            title = classname
        oldest_article = self.oldest_article
        max_articles   = self.max_articles
        feeds = recipe.get('feeds')

        src = '''\
class %(classname)s(%(base_class)s):
    title          = %(title)s
    oldest_article = %(oldest_article)d
    max_articles_per_feed = %(max_articles)d
    auto_cleanup = True

    feeds          = %(feeds)s
'''%dict(classname=classname, title=repr(title),
                 feeds=repr(feeds), oldest_article=oldest_article,
                 max_articles=max_articles,
                 base_class='AutomaticNewsRecipe')
        return src, title

if __name__ == '__main__':
    opml = OPML();
    opml.load('/media/sf_Kenny/Downloads/feedly.opml')
    outlines = opml.parse()
    print(len(opml.outlines))
    opml.import_recipes(outlines)

