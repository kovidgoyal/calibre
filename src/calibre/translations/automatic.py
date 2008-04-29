
import sys, glob, re

import mechanize

URL = 'http://translate.google.com/translate_t?text=%(text)s&langpair=en|%(lang)s&oe=UTF8'

def browser():
    opener = mechanize.Browser()
    opener.set_handle_refresh(True)
    opener.set_handle_robots(False)
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; i686 Linux; en_US; rv:1.8.0.4) Gecko/20060508 Firefox/1.5.0.4')]
    return opener


class PoFile(object):
    
    SANITIZE = re.compile(r'&|<[^<>]+>|\%')
    STRING   = re.compile(r'"(.*)"')
    
    def __init__(self, po_file):
        self.po_file = open(po_file, 'r+b')
        self.browser = browser()
        self.entries = []
        self.read()
        
    def sanitize_line(self, line):
        return self.SANITIZE.sub(line)
    
    def read(self):
        translated_lines = []
        self.po_file.seek(0)
        
        ID  = 0
        STR = 1
        WHR = 2
        
        mode = None
        where, msgid, msgstr, fuzzy = [], [], [], False
        
        for line in self.po_file.readlines():
            prev_mode = mode
            if line.startswith('#:'):
                mode = WHR
            elif line.startswith('msgid'):
                mode = ID
            elif line.startswith('msgstr'):
                mode = STR
            elif line.startswith('#,'):
                fuzzy = True
                continue
            elif line.startswith('#') or not line.strip():
                mode = None 
            
                
            if mode != prev_mode:
                if prev_mode == STR:
                    self.add_entry(where, fuzzy, msgid, msgstr)
                    where, msgid, msgstr, fuzzy = [], [], [], False
                    
            if mode == WHR:
                where.append(line[2:].strip())
            elif mode == ID:
                msgid.append(self.get_string(line))
            elif mode == STR:
                msgstr.append(self.get_string(line))
            elif mode == None:
                self.add_line(line)    
            
    def get_string(self, line):
        return self.STRING.search(line).group(1)
    
    def add_line(self, line):
        self.entries.append(line.strip())
        
    def add_entry(self, where, fuzzy, msgid, msgstr):
        self.entries.append(Entry(where, fuzzy, msgid, msgstr))
        
    def __str__(self):
        return '\n'.join([str(i) for i in self.entries]) + '\n'
        
        
class Entry(object):
    
    def __init__(self, where, fuzzy, msgid, msgstr, encoding='utf-8'):
        self.fuzzy  = fuzzy
        self.where  = [i.decode(encoding) for i in where]
        self.msgid  = [i.decode(encoding) for i in msgid]
        self.msgstr = [i.decode(encoding) for i in msgstr]
        self.encoding = encoding 
        
    def __str__(self):
        ans = []
        for line in self.where:
            ans.append('#: ' + line.encode(self.encoding))
        if self.fuzzy:
            ans.append('#, fuzzy')
        first = True
        for line in self.msgid:
            prefix = 'msgid ' if first else ''
            ans.append(prefix + '"%s"'%line.encode(self.encoding))
            first = False
        first = True
        for line in self.msgstr:
            prefix = 'msgstr ' if first else ''
            ans.append(prefix + '"%s"'%line.encode(self.encoding))
            first = False
        return '\n'.join(ans)
            
        

def main():
    po_files = glob.glob('*.po')
    for po_file in po_files:
        PoFile(po_file)
    pass

if __name__ == '__main__':
    pof = PoFile('de.po')
    open('/tmp/de.po', 'wb').write(str(pof))
    #sys.exit(main())