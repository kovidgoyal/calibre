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
