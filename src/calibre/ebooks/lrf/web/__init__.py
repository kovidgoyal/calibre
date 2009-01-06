__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


builtin_profiles   = []
available_profiles = [i.__module__.rpartition('.')[2] for i in builtin_profiles]
