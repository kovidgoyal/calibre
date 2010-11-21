#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Plugin to make the commit command automatically close bugs when the commit
message contains `Fix #number` or `Implement #number`. Also updates the commit
message with the summary of the closed bug. It also set the `--fixes` metadata
appropriately. Currently only works with a Trac bug repository with the XMLRPC
plugin enabled.

To use copy this file into `~/.bazaar/plugins` and add the following to branch.conf
in the working tree you want to use it with::

    trac_reponame_url = <url>
    trac_reponame_username = <username>
    trac_reponame_password = <password>

'''
import os, re, xmlrpclib
from bzrlib.builtins import cmd_commit as _cmd_commit, tree_files
from bzrlib import branch
import bzrlib


class cmd_commit(_cmd_commit):

    @classmethod
    def trac_url(self, username, password, url):
        return url.replace('//', '//%s:%s@'%(username, password))+'/login/xmlrpc'

    def get_trac_summary(self, bug, url):
        print 'Getting bug summary for bug #%s'%bug,
        server = xmlrpclib.ServerProxy(url)
        attributes = server.ticket.get(int(bug))[-1]
        print attributes['summary']
        return attributes['summary']

    def expand_bug(self, msg, nick, config, bug_tracker, type='trac'):
        prefix = '%s_%s_'%(type, nick)
        username = config.get_user_option(prefix+'username')
        password = config.get_user_option(prefix+'password')
        close_bug = config.get_user_option(prefix+'pattern')
        if close_bug is None:
            close_bug = r'(Fix|Implement|Fixes|Fixed|Implemented)\s+#(\d+)'
        close_bug_pat = re.compile(close_bug, re.IGNORECASE)
        match = close_bug_pat.search(msg)
        if not match:
            return msg, None, None, None
        action, bug = match.group(1), match.group(2)
        summary = ''
        if type == 'trac':
            url = self.trac_url(username, password, bug_tracker)
            summary = self.get_trac_summary(bug, url)
        if summary:
            msg = msg.replace('#%s'%bug, '#%s (%s)'%(bug, summary))
            msg = msg.replace('Fixesed', 'Fixed')
        return msg, bug, url, action


    def get_bugtracker(self, basedir, type='trac'):
        config = os.path.join(basedir, '.bzr', 'branch', 'branch.conf')
        bugtracker, nick = None, None
        if os.access(config, os.R_OK):
            for line in open(config).readlines():
                match = re.search(r'%s_(\S+)_url\s*=\s*(\S+)'%type, line)
                if match:
                    nick, bugtracker = match.group(1), match.group(2)
                    break
        return nick, bugtracker

    def expand_message(self, msg, tree):
        nick, bugtracker = self.get_bugtracker(tree.basedir, type='trac')
        if not bugtracker:
            return msg
        config =  branch.Branch.open(tree.basedir).get_config()
        msg, bug, url, action = self.expand_bug(msg, nick, config, bugtracker)

        return msg, bug, url, action, nick, config

    def run(self, message=None, file=None, verbose=False, selected_list=None,
            unchanged=False, strict=False, local=False, fixes=None,
            author=None, show_diff=False, exclude=None):
        nick = config = bug = action = None
        if message:
            try:
                message, bug, url, action, nick, config = \
                    self.expand_message(message, tree_files(selected_list)[0])
            except ValueError:
                pass

            if nick and bug and not fixes:
                fixes = [nick+':'+bug]

        ret = _cmd_commit.run(self, message=message, file=file, verbose=verbose,
                              selected_list=selected_list, unchanged=unchanged,
                              strict=strict, local=local, fixes=fixes,
                              author=author, show_diff=show_diff, exclude=exclude)
        if message and bug and action and nick and config:
            self.close_bug(bug, action, url, config)
        return ret

    def close_bug(self, bug, action, url, config):
        print 'Closing bug #%s'% bug
        nick = config.get_nickname()
        suffix = config.get_user_option('bug_close_comment')
        if suffix is None:
            suffix = 'The fix will be in the next release.'
        action = action+'ed'
        msg = '%s in branch %s. %s'%(action, nick, suffix)
        server = xmlrpclib.ServerProxy(url)
        server.ticket.update(int(bug), msg,
                             {'status':'closed', 'resolution':'fixed'},
                             True)

bzrlib.commands.register_command(cmd_commit)
