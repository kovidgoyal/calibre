from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re

from lxml import etree
from Cheetah.Template import Template

from calibre.customize.conversion import OutputFormatPlugin
from calibre import CurrentDir
from calibre.customize.conversion import OptionRecommendation

from urllib import unquote

class HTMLOutput(OutputFormatPlugin):

    name = 'HTML Output'
    author = 'Fabian Grassl'
    file_type = 'html'

    recommendations = set([('pretty_print', True, OptionRecommendation.HIGH)])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        self.log  = log
        self.opts = opts
        output_file = output_path
        output_path = re.sub(r'\.html', '', output_path)+'_files'

        with open(output_file, 'wb') as f:
            root = oeb_book.html_toc()
            html_txt = etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=False)
            f.write(html_txt)

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        with CurrentDir(output_path):
            for item in oeb_book.manifest:
                path = os.path.abspath(unquote(item.href))
                dir = os.path.dirname(path)
                if not os.path.exists(dir):
                    os.makedirs(dir)
                if item.spine_position is not None:
                    with open(path, 'wb') as f:
                        pass
                else:
                    with open(path, 'wb') as f:
                        f.write(str(item))
                    item.unload_data_from_memory(memory=path)

            for item in oeb_book.spine:
                path = os.path.abspath(unquote(item.href))
                dir = os.path.dirname(path)
                root = item.data.getroottree()
                body = root.xpath('//h:body', namespaces={'h': 'http://www.w3.org/1999/xhtml'})[0]
                ebook_content = etree.tostring(body, pretty_print=True, encoding='utf-8')
                ebook_content = re.sub(r'\<\/?body.*\>', '', ebook_content)
                if item.spine_position+1 < len(oeb_book.spine):
                  nextLink = oeb_book.spine[item.spine_position+1].href
                  nextLink = os.path.abspath((nextLink))
                  nextLink = os.path.relpath(nextLink, dir)
                else:
                  nextLink = None
                if item.spine_position > 0:
                  prevLink = oeb_book.spine[item.spine_position-1].href
                  prevLink = os.path.abspath((prevLink))
                  prevLink = os.path.relpath(prevLink, dir)
                else:
                  prevLink = None
                vars = {
                  'ebookContent': ebook_content,
                  'prevLink': prevLink,
                  'nextLink': nextLink
                }
                template_file = os.path.dirname(__file__)+'/outputtemplates/default.tmpl'
                t = Template(file=template_file, searchList=[ vars ]) # compilerSettings={'useStackFrames': False}
                with open(path, 'wb') as f:
                    f.write(str(t))

                item.unload_data_from_memory(memory=path)
