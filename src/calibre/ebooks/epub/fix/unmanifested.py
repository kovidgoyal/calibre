#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.ebooks.epub.fix import ePubFixer

class Unmanifested(ePubFixer):

    name = 'Fix unmanifested files'

    @property
    def short_description(self):
        return _('Fix unmanifested files')

    @property
    def long_description(self):
        return _('Fix unmanifested files. epub-fix can either add them to '
        'the manifest or delete them as specified by the '
        'delete unmanifested option.')

    @property
    def description(self):
        return self.long_description

    @property
    def fix_name(self):
        return 'unmanifested'

    @property
    def options(self):
        return [('delete_unmanifested', 'bool', False,
            _('Delete unmanifested files instead of adding them to the manifest'))]

    def run(self, container, opts, log, fix=False):
        dirtied = False
        for name in list(container.manifest_worthy_names()):
            item = container.manifest_item_for_name(name)
            if item is None:
                log.error(name, 'not in manifest')
                if fix:
                    if opts.delete_unmanifested:
                        container.delete_name(name)
                        log('\tDeleted')
                    else:
                        container.add_name_to_manifest(name)
                        log('\tAdded to manifest')
                        dirtied = True
        if dirtied:
            container.set(container.opf_name, container.opf)
