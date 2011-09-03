import calibre.ebooks.markdown.markdown as markdown
from calibre.ebooks.markdown.markdown import etree

DEFAULT_URL = "http://www.freewisdom.org/projects/python-markdown/"
DEFAULT_CREATOR = "Yuri Takhteyev"
DEFAULT_TITLE = "Markdown in Python"
GENERATOR = "http://www.freewisdom.org/projects/python-markdown/markdown2rss"

month_map = { "Jan" : "01",
              "Feb" : "02",
              "March" : "03",
              "April" : "04",
              "May" : "05",
              "June" : "06",
              "July" : "07",
              "August" : "08",
              "September" : "09",
              "October" : "10",
              "November" : "11",
              "December" : "12" }

def get_time(heading):

    heading = heading.split("-")[0]
    heading = heading.strip().replace(",", " ").replace(".", " ")

    month, date, year = heading.split()
    month = month_map[month]

    return rdftime(" ".join((month, date, year, "12:00:00 AM")))

def rdftime(time):

    time = time.replace(":", " ")
    time = time.replace("/", " ")
    time = time.split()
    return "%s-%s-%sT%s:%s:%s-08:00" % (time[0], time[1], time[2],
                                        time[3], time[4], time[5])


def get_date(text):
    return "date"

class RssExtension (markdown.Extension):

    def extendMarkdown(self, md, md_globals):

        self.config = { 'URL' : [DEFAULT_URL, "Main URL"],
                        'CREATOR' : [DEFAULT_CREATOR, "Feed creator's name"],
                        'TITLE' : [DEFAULT_TITLE, "Feed title"] }

        md.xml_mode = True
        
        # Insert a tree-processor that would actually add the title tag
        treeprocessor = RssTreeProcessor(md)
        treeprocessor.ext = self
        md.treeprocessors['rss'] = treeprocessor
        md.stripTopLevelTags = 0
        md.docType = '<?xml version="1.0" encoding="utf-8"?>\n'

class RssTreeProcessor(markdown.treeprocessors.Treeprocessor):

    def run (self, root):

        rss = etree.Element("rss")
        rss.set("version", "2.0")

        channel = etree.SubElement(rss, "channel")

        for tag, text in (("title", self.ext.getConfig("TITLE")),
                          ("link", self.ext.getConfig("URL")),
                          ("description", None)):
            
            element = etree.SubElement(channel, tag)
            element.text = text

        for child in root:

            if child.tag in ["h1", "h2", "h3", "h4", "h5"]:
      
                heading = child.text.strip()
                item = etree.SubElement(channel, "item")
                link = etree.SubElement(item, "link")
                link.text = self.ext.getConfig("URL")
                title = etree.SubElement(item, "title")
                title.text = heading

                guid = ''.join([x for x in heading if x.isalnum()])
                guidElem = etree.SubElement(item, "guid")
                guidElem.text = guid
                guidElem.set("isPermaLink", "false")

            elif child.tag in ["p"]:
                try:
                    description = etree.SubElement(item, "description")
                except UnboundLocalError:
                    # Item not defined - moving on
                    pass
                else:
                    if len(child):
                        content = "\n".join([etree.tostring(node)
                                             for node in child])
                    else:
                        content = child.text
                    pholder = self.markdown.htmlStash.store(
                                                "<![CDATA[ %s]]>" % content)
                    description.text = pholder
    
        return rss


def makeExtension(configs):

    return RssExtension(configs)
