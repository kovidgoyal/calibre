'''
Trac Macro to generate an end use Changelog from the svn logs.
'''
import re

import pysvn

from cStringIO import StringIO

from trac.wiki.formatter import Formatter
from trac.wiki.macros import WikiMacroBase
from trac.util import Markup


#SVN_PATH = 'https://svn.kovidgoyal.net/code/libprs500/trunk'
SVN_PATH = 'file:///svn/code/libprs500/trunk'

def svn_log_to_txt():
    cl = pysvn.Client()
    
    log = cl.log(SVN_PATH, 
        revision_end=pysvn.Revision(pysvn.opt_revision_kind.number, 583 ), 
        revision_start=pysvn.Revision(pysvn.opt_revision_kind.head))
    
    
    version_change_indices, version_change_version = [], []
    for i in range(len(log)):
        entry = log[i]
        match = re.search(r'version\s+(\d+\.\d+\.\d+)', entry['message']) 
        if match:
            version_change_indices.append(i)
            version_change_version.append(match.group(1))
            
    txt = '= Changelog =\n[[PageOutline]]\n'
    version_pat = re.compile(r'version\s+(\d+\.\d+\.\d+)', re.IGNORECASE)
    current_version = False
    for entry in log:
        msg = entry['message'].strip()
        msg = re.sub(r'\#(\d+)', r'[ticket:\1 Ticket \1]', msg)
        if not msg:
            continue
        match = version_pat.search(msg)
        if match:
            current_version = True
            txt += '----\n== Version '+match.group(1)+' ==\n'
        elif current_version:
            txt += '  * ' + msg + '\n'
            
    return txt


class ChangeLogMacro(WikiMacroBase):

    def expand_macro(self, formatter, name, args):
        txt = svn_log_to_txt()
        out = StringIO()
        Formatter(formatter.env, formatter.context).format(txt, out)
        return Markup(out.getvalue())


if __name__ == '__main__':
    print svn_log_to_txt() 
        
        