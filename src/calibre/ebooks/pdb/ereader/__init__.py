# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

class EreaderError(Exception):
    pass
    
def image_name(name):
    name = os.path.basename(name)
    
    if len(name) > 32:
        cut = len(name) - 32
        names = name[:10]
        namee = name[10+cut:]
        name = names + namee
        
    name = name.ljust(32, '\x00')[:32]
    
    return name

