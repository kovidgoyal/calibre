"""
HeaderID Extension for Python-Markdown
======================================

Auto-generate id attributes for HTML headers.

See <https://pythonhosted.org/Markdown/extensions/header_id.html>
for documentation.

Original code Copyright 2007-2011 [Waylan Limberg](http://achinghead.com/).

All changes Copyright 2011-2014 The Python Markdown Project

License: [BSD](http://www.opensource.org/licenses/bsd-license.php)

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from . import Extension
from ..treeprocessors import Treeprocessor
from ..util import parseBoolValue
from .toc import slugify, unique, stashedHTML2text
import warnings


class HeaderIdTreeprocessor(Treeprocessor):
    """ Assign IDs to headers. """

    IDs = set()

    def run(self, doc):
        start_level, force_id = self._get_meta()
        slugify = self.config['slugify']
        sep = self.config['separator']
        for elem in doc:
            if elem.tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                if force_id:
                    if "id" in elem.attrib:
                        id = elem.get('id')
                    else:
                        id = stashedHTML2text(''.join(elem.itertext()), self.md)
                        id = slugify(id, sep)
                    elem.set('id', unique(id, self.IDs))
                if start_level:
                    level = int(elem.tag[-1]) + start_level
                    if level > 6:
                        level = 6
                    elem.tag = 'h%d' % level

    def _get_meta(self):
        """ Return meta data suported by this ext as a tuple """
        level = int(self.config['level']) - 1
        force = parseBoolValue(self.config['forceid'])
        if hasattr(self.md, 'Meta'):
            if 'header_level' in self.md.Meta:
                level = int(self.md.Meta['header_level'][0]) - 1
            if 'header_forceid' in self.md.Meta:
                force = parseBoolValue(self.md.Meta['header_forceid'][0])
        return level, force


class HeaderIdExtension(Extension):
    def __init__(self, *args, **kwargs):
        # set defaults
        self.config = {
            'level': ['1', 'Base level for headers.'],
            'forceid': ['True', 'Force all headers to have an id.'],
            'separator': ['-', 'Word separator.'],
            'slugify': [slugify, 'Callable to generate anchors']
        }

        super(HeaderIdExtension, self).__init__(*args, **kwargs)

        warnings.warn(
            'The HeaderId Extension is pending deprecation. Use the TOC Extension instead.',
            PendingDeprecationWarning
        )

    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)
        self.processor = HeaderIdTreeprocessor()
        self.processor.md = md
        self.processor.config = self.getConfigs()
        if 'attr_list' in md.treeprocessors.keys():
            # insert after attr_list treeprocessor
            md.treeprocessors.add('headerid', self.processor, '>attr_list')
        else:
            # insert after 'prettify' treeprocessor.
            md.treeprocessors.add('headerid', self.processor, '>prettify')

    def reset(self):
        self.processor.IDs = set()


def makeExtension(*args, **kwargs):
    return HeaderIdExtension(*args, **kwargs)
