#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.utils.config import Config, StringConfig, config_dir, tweaks


listen_on = tweaks['server_listen_on']


log_access_file = os.path.join(config_dir, 'server_access_log.txt')
log_error_file = os.path.join(config_dir, 'server_error_log.txt')


def server_config(defaults=None):
    desc=_('Settings to control the calibre content server')
    c = Config('server', desc) if defaults is None else StringConfig(defaults, desc)

    c.add_opt('port', ['-p', '--port'], default=8080,
              help=_('The port on which to listen. Default is %default'))
    c.add_opt('timeout', ['-t', '--timeout'], default=120,
              help=_('The server timeout in seconds. Default is %default'))
    c.add_opt('thread_pool', ['--thread-pool'], default=30,
              help=_('The max number of worker threads to use. Default is %default'))
    c.add_opt('password', ['--password'], default=None,
              help=_('Set a password to restrict access. By default access is unrestricted.'))
    c.add_opt('username', ['--username'], default='calibre',
              help=_('Username for access. By default, it is: %default'))
    c.add_opt('develop', ['--develop'], default=False,
              help='Development mode. Server automatically restarts on file changes and serves code files (html, css, js) from the file system instead of calibre\'s resource system.')
    c.add_opt('max_cover', ['--max-cover'], default='600x800',
              help=_('The maximum size for displayed covers. Default is %default.'))
    c.add_opt('max_opds_items', ['--max-opds-items'], default=30,
            help=_('The maximum number of matches to return per OPDS query. '
            'This affects Stanza, WordPlayer, etc. integration.'))
    c.add_opt('max_opds_ungrouped_items', ['--max-opds-ungrouped-items'],
            default=100,
            help=_('Group items in categories such as author/tags '
                'by first letter when there are more than this number '
                'of items. Default: %default. Set to a large number '
                'to disable grouping.'))
    c.add_opt('url_prefix', ['--url-prefix'], default='',
              help=_('Prefix to prepend to all URLs. Useful for reverse'
                  'proxying to this server from Apache/nginx/etc.'))

    return c

def custom_fields_to_display(db):
    ckeys = db.field_metadata.ignorable_field_keys()
    yes_fields = set(tweaks['content_server_will_display'])
    no_fields = set(tweaks['content_server_wont_display'])
    if '*' in yes_fields:
        yes_fields = set(ckeys)
    if '*' in no_fields:
        no_fields = set(ckeys)
    return frozenset(yes_fields - no_fields)

def main():
    from calibre.library.server.main import main
    return main()
