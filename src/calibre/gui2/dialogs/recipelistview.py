__license__   = 'GPL v3'
__copyright__ = '2009, John Schember john@nachtimwald.com'
'''
List View for showing recipies. Allows for keyboad events when selecting new
items.
'''

from PyQt4.Qt import QListView, SIGNAL
            
class RecipeListView(QListView):
    def __init__(self, *args):
        QListView.__init__(self, *args)
        
    def selectionChanged(self, selected, deselected):
        self.emit(SIGNAL('itemChanged(QModelIndex)'), selected.indexes()[0])

