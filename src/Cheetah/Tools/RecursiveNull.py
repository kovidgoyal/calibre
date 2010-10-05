"""
Nothing, but in a friendly way.  Good for filling in for objects you want to
hide.  If $form.f1 is a RecursiveNull object, then
$form.f1.anything["you"].might("use") will resolve to the empty string.

This module was contributed by Ian Bicking.
"""

class RecursiveNull(object):
    def __getattr__(self, attr):
        return self
    def __getitem__(self, item):
        return self
    def __call__(self, *args, **kwargs):
        return self
    def __str__(self):
        return ''
    def __repr__(self):
        return ''
    def __nonzero__(self):
        return 0
    def __eq__(self, x):
        if x:
            return False
        return True
    def __ne__(self, x):
        return x and True or False

