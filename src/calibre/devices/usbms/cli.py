__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com'
'''
Generic implemenation of the prs500 command line functions. This is not a
complete stand alone driver. It is intended to be subclassed with the relevant
parts implemented for a particular device.
'''

class CLI(object):

# ls, cp, mkdir, touch, cat,
       
    def rm(self, path, end_session=True):
        path = self.munge_path(path)
        self.delete_books([path])
        
