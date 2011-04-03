#!/usr/bin/env  python2

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Plugin to make the commit command automatically close bugs when the commit
message contains `Fix #number` or `Implement #number`. Also updates the commit
message with the summary of the closed bug. It also set the `--fixes` metadata
appropriately.

'''
import re, urllib, importlib, sys
from bzrlib.builtins import cmd_commit as _cmd_commit
import bzrlib

from lxml import html

SENDMAIL = ('/home/kovid/work/kde', 'pgp_mail')

class cmd_commit(_cmd_commit):

    def expand_bug(self, msg):
        close_bug = r'(Fix|Implement|Fixes|Fixed|Implemented)\s+#(\d+)'
        close_bug_pat = re.compile(close_bug, re.IGNORECASE)
        match = close_bug_pat.search(msg)
        if not match:
            return msg, None, None
        action, bug = match.group(1), match.group(2)
        summary = ''
        raw = urllib.urlopen('https://bugs.launchpad.net/calibre/+bug/' +
                bug).read()
        try:
            h1 = html.fromstring(raw).xpath('//h1[@id="edit-title"]')[0]
            summary = html.tostring(h1, method='text', encoding=unicode).strip()
        except:
            summary = 'Private bug'
        print 'Working on bug:', summary
        if summary:
            msg = msg.replace('#%s'%bug, '#%s (%s)'%(bug, summary))
            msg = msg.replace('Fixesed', 'Fixed')
        return msg, bug, action

    def run(self, message=None, file=None, verbose=False, selected_list=None,
            unchanged=False, strict=False, local=False, fixes=None,
            author=None, show_diff=False, exclude=None):
        bug = action = None
        if message:
            message, bug, action = self.expand_bug(message)

            if bug and not fixes:
                fixes = ['lp:'+bug]

        ret = _cmd_commit.run(self, message=message, file=file, verbose=verbose,
                              selected_list=selected_list, unchanged=unchanged,
                              strict=strict, local=local, fixes=fixes,
                              author=author, show_diff=show_diff, exclude=exclude)
        if message and bug and action:
            self.close_bug(bug, action)
        return ret

    def close_bug(self, bug, action):
        print 'Closing bug #%s'% bug
        #nick = config.get_nickname()
        suffix = ('The fix will be in the next release. '
                'calibre is usually released every Friday.')
        action = action+'ed'
        msg = '%s in branch %s. %s'%(action, 'lp:calibre', suffix)
        msg = msg.replace('Fixesed', 'Fixed')
        msg += '\n\n status fixreleased'

        sys.path.insert(0, SENDMAIL[0])

        sendmail = importlib.import_module(SENDMAIL[1])

        to = bug+'@bugs.launchpad.net'
        sendmail.sendmail(msg, to, 'Fixed in lp:calibre')


bzrlib.commands.register_command(cmd_commit)
