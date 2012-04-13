#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2012, Eli Algranti <idea00@hotmail.com>'
__docformat__ = 'restructuredtext en'

import json
from itertools import izip

def encodeJson(definition):
    '''
    Encode a search/replace definition using json.
    '''
    return 'json:' + json.dumps(definition)

def encodeFile(definition, filename):
    '''
    Encode a search/replace definition into a file
    '''
    with open(filename, 'w') as f:
        for search,replace in definition:
            f.write(search + '\n')
            f.write(replace + '\n')

    return 'file:'+filename


def decode(definition):
    '''
    Decodes a search/replace definition
    '''
    if definition.startswith('json:'):
        return json.loads(definition[len('json:'):])
    elif definition.startswith('file:'):
        with open(definition[len('file:'):], 'r') as f:
            ans = []
            for search, replace in izip(f, f):
                ans.append([search.rstrip('\n\r'), replace.rstrip('\n\r')])
        return ans
    raise Exception('Invalid definition')

            
            




    

