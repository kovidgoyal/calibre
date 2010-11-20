#multiple replace from dictionnary : http://code.activestate.com/recipes/81330/
__license__   = 'GPL v3'
__copyright__ = '2010, sengian <sengian1 @ gmail.com>'
__docformat__ = 'restructuredtext en'

import re
from UserDict import UserDict

class MReplace(UserDict):
    def __init__(self, dict = None):
        UserDict.__init__(self, dict)
        self.re = None
        self.regex = None
        self.compile_regex()

    def compile_regex(self): 
        if len(self.data) > 0:
            keys = sorted(self.data.keys(), key=len)
            keys.reverse()
            tmp = "(%s)" % "|".join(map(re.escape, keys))
            if self.re != tmp:
                self.re = tmp
                self.regex = re.compile(self.re)

    def __call__(self, mo): 
        return self[mo.string[mo.start():mo.end()]]

    def mreplace(self, text): 
        #Replace without regex compile
        if len(self.data) < 1 or self.re is None:
            return text
        return self.regex.sub(self, text)