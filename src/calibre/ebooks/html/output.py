from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re

from os.path import dirname, abspath, relpath, exists, basename

from lxml import etree
from templite import Templite

from calibre.ebooks.oeb.base import element
from calibre.customize.conversion import OutputFormatPlugin, OptionRecommendation
from calibre import CurrentDir

from urllib import unquote

class HTMLOutput(OutputFormatPlugin):

    name = 'HTML Output'
    author = 'Fabian Grassl'
    file_type = 'html'

    recommendations = set([('pretty_print', True, OptionRecommendation.HIGH)])

    def generate_toc(self, oeb_book, ref_url, output_dir):
        with CurrentDir(output_dir):
            def build_node(current_node, parent=None):
                if parent is None:
                    parent = etree.Element('ul')
                elif len(current_node.nodes):
                    parent = element(parent, ('ul'))
                for node in current_node.nodes:
                    point = element(parent, 'li')
                    href = relpath(abspath(unquote(node.href)), dirname(ref_url))
                    link = element(point, 'a', href=href)
                    title = node.title
                    if title:
                        title = re.sub(r'\s+', ' ', title)
                    link.text=title
                    build_node(node, point)
                return parent
            lang = unicode(oeb_book.metadata.language[0])
            wrap = etree.Element('div')
            wrap.append(build_node(oeb_book.toc))
            return wrap

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        self.log  = log
        self.opts = opts
        output_file = output_path
        output_dir = re.sub(r'\.html', '', output_path)+'_files'
        if not exists(output_dir):
            os.makedirs(output_dir)

        with open(output_file, 'wb') as f:
            link_prefix=basename(output_dir)+'/'
            root = self.generate_toc(oeb_book, output_dir, output_dir)
            html_toc = etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=False)
            templite = Templite(P('templates/html_export_default_index.tmpl', data=True))
            t = templite.render(toc=html_toc)
            f.write(t)

        with CurrentDir(output_dir):
            for item in oeb_book.manifest:
                path = abspath(unquote(item.href))
                dir = dirname(path)
                if not exists(dir):
                    os.makedirs(dir)
                if item.spine_position is not None:
                    with open(path, 'wb') as f:
                        pass
                else:
                    with open(path, 'wb') as f:
                        f.write(str(item))
                    item.unload_data_from_memory(memory=path)

            for item in oeb_book.spine:
                path = abspath(unquote(item.href))
                dir = dirname(path)
                root = item.data.getroottree()
                body = root.xpath('//h:body', namespaces={'h': 'http://www.w3.org/1999/xhtml'})[0]
                ebook_content = etree.tostring(body, pretty_print=True, encoding='utf-8')
                ebook_content = re.sub(r'\<\/?body.*\>', '', ebook_content)
                if item.spine_position+1 < len(oeb_book.spine):
                    nextLink = oeb_book.spine[item.spine_position+1].href
                    nextLink = relpath(abspath(nextLink), dir)
                else:
                    nextLink = None
                if item.spine_position > 0:
                    prevLink = oeb_book.spine[item.spine_position-1].href
                    prevLink = relpath(abspath(prevLink), dir)
                else:
                    prevLink = None
                templite = Templite(P('templates/html_export_default.tmpl', data=True))
                t = templite.render(ebookContent=ebook_content, prevLink=prevLink, nextLink=nextLink)
                with open(path, 'wb') as f:
                    f.write(t)
                item.unload_data_from_memory(memory=path)
