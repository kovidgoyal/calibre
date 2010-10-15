from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, Fabian Grassl <fg@jusmeum.de>'
__docformat__ = 'restructuredtext en'

import os, re

from os.path import dirname, abspath, relpath, exists, basename

from lxml import etree
from templite import Templite

from calibre.ebooks.oeb.base import element, namespace, barename, DC11_NS
from calibre.customize.conversion import OutputFormatPlugin, OptionRecommendation
from calibre import CurrentDir

from urllib import unquote

from calibre.ebooks.html.meta import EasyMeta

class HTMLOutput(OutputFormatPlugin):

    name = 'HTML Output'
    author = 'Fabian Grassl'
    file_type = 'html'

    recommendations = set([('pretty_print', True, OptionRecommendation.HIGH)])

    def generate_toc(self, oeb_book, ref_url, output_dir):
        '''
        Generate table of contents
        '''
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

    def generate_html_toc(self, oeb_book, ref_url, output_dir):
        root = self.generate_toc(oeb_book, ref_url, output_dir)
        return etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=False)

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        if oeb_book.toc.count() == 0:
          if len(oeb_book.spine) > 1:
            pass
          else:
            pass
        self.log  = log
        self.opts = opts
        output_file = output_path
        output_dir = re.sub(r'\.html', '', output_path)+'_files'
        meta=EasyMeta(oeb_book.metadata)
        if not exists(output_dir):
            os.makedirs(output_dir)

        with open(output_file, 'wb') as f:
            link_prefix=basename(output_dir)+'/'
            html_toc = self.generate_html_toc(oeb_book, output_file, output_dir)
            templite = Templite(P('templates/html_export_default_index.tmpl', data=True))
            print oeb_book.metadata.items
            t = templite.render(toc=html_toc, meta=meta)
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

                # get & clean HTML <HEAD>-data
                head = root.xpath('//h:head', namespaces={'h': 'http://www.w3.org/1999/xhtml'})[0]
                head_content = etree.tostring(head, pretty_print=True, encoding='utf-8')
                head_content = re.sub(r'\<\/?head.*\>', '', head_content)
                head_content = re.sub(re.compile(r'\<style.*\/style\>', re.M|re.S), '', head_content)

                # get & clean HTML <BODY>-data
                body = root.xpath('//h:body', namespaces={'h': 'http://www.w3.org/1999/xhtml'})[0]
                ebook_content = etree.tostring(body, pretty_print=True, encoding='utf-8')
                ebook_content = re.sub(r'\<\/?body.*\>', '', ebook_content)

                # generate link to next page
                if item.spine_position+1 < len(oeb_book.spine):
                    nextLink = oeb_book.spine[item.spine_position+1].href
                    nextLink = relpath(abspath(nextLink), dir)
                else:
                    nextLink = None

                # generate link to previous page
                if item.spine_position > 0:
                    prevLink = oeb_book.spine[item.spine_position-1].href
                    prevLink = relpath(abspath(prevLink), dir)
                else:
                    prevLink = None

                # render template
                templite = Templite(P('templates/html_export_default.tmpl', data=True))
                toc = lambda: self.generate_html_toc(oeb_book, path, output_dir)
                t = templite.render(ebookContent=ebook_content, prevLink=prevLink, nextLink=nextLink, toc=toc, head_content=head_content, meta=meta)

                # write html to file
                with open(path, 'wb') as f:
                    f.write(t)
                item.unload_data_from_memory(memory=path)
