from urllib2 import urlopen, Request
from xml.dom.minidom import parse
from url import URL

class Description:
    """A class for representing OpenSearch Description files.
    """

    def __init__(self, url="", agent=""):
        """The constructor which may pass an optional url to load from.

        d = Description("http://www.example.com/description")
        """
        self.agent = agent
        if url: 
            self.load(url)


    def load(self, url):
        """For loading up a description object from a url. Normally
        you'll probably just want to pass a URL into the constructor.
        """
        req = Request(url, headers={'User-Agent':self.agent})
        self.dom = parse(urlopen(req))

        # version 1.1 has repeating Url elements
        self.urls = self._get_urls()

        # this is version 1.0 specific
        self.url = self._get_element_text('Url')
        self.format = self._get_element_text('Format')

        self.shortname = self._get_element_text('ShortName')
        self.longname = self._get_element_text('LongName')
        self.description = self._get_element_text('Description')
        self.image = self._get_element_text('Image')
        self.samplesearch = self._get_element_text('SampleSearch')
        self.developer = self._get_element_text('Developer')
        self.contact = self._get_element_text('Contact')
        self.attribution = self._get_element_text('Attribution')
        self.syndicationright = self._get_element_text('SyndicationRight')

        tag_text = self._get_element_text('Tags')
        if tag_text != None:
            self.tags = tag_text.split(" ")

        if self._get_element_text('AdultContent') == 'true':
            self.adultcontent = True
        else:
            self.adultcontent = False

    def get_url_by_type(self, type):
        """Walks available urls and returns them by type. Only 
        appropriate in opensearch v1.1 where there can be multiple
        query targets. Returns none if no such type is found.

        url = description.get_url_by_type('application/rss+xml')
        """
        for url in self.urls:
            if url.type == type:
                return url
        return None

    def get_best_template(self):
        """OK, best is a value judgement, but so be it. You'll get 
        back either the atom, rss or first template available. This
        method handles the main difference between opensearch v1.0 and v1.1
        """
        # version 1.0
        if self.url: 
            return self.url

        # atom
        if self.get_url_by_type('application/atom+xml'):
            return self.get_url_by_type('application/atom+xml').template

        # rss
        if self.get_url_by_type('application/rss+xml'):
            return self.get_url_by_type('application/rss+xml').template

        # other possible rss type
        if self.get_url_by_type('text/xml'):
            return self.get_url_by_Type('text/xml').template

        # otherwise just the first one
        if len(self.urls) > 0:
            return self.urls[0].template

        # out of luck
        return Nil
        

    # these are internal methods for querying xml

    def _get_element_text(self, tag):
        elements = self._get_elements(tag)
        if not elements:
            return None 
        return self._get_text(elements[0].childNodes)

    def _get_attribute_text(self, tag, attribute):
        elements = self._get_elements(tag)
        if not elements:
            return ''
        return elements[0].getAttribute('template')

    def _get_elements(self, tag):
        return self.dom.getElementsByTagName(tag)

    def _get_text(self, nodes):
        text = ''
        for node in nodes:
            if node.nodeType == node.TEXT_NODE:
                text += node.data
        return text.strip()

    def _get_urls(self):
        urls = []
        for element in self._get_elements('Url'):
            template = element.getAttribute('template')
            type = element.getAttribute('type')
            if template and type:
                url = URL()
                url.template = template
                url.type = type
                urls.append(url)
        return urls
