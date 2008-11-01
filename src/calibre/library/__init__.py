__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''' Code to manage ebook library'''
import re

title_pat = re.compile('^(A|The|An)\s+', re.IGNORECASE)
def title_sort(title):
    match = title_pat.search(title)
    if match:
        prep = match.group(1)
        title = title.replace(prep, '') + ', ' + prep
    return title.strip()