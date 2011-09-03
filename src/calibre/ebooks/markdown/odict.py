class OrderedDict(dict):
    """
    A dictionary that keeps its keys in the order in which they're inserted.
    
    Copied from Django's SortedDict with some modifications.

    """
    def __new__(cls, *args, **kwargs):
        instance = super(OrderedDict, cls).__new__(cls, *args, **kwargs)
        instance.keyOrder = []
        return instance

    def __init__(self, data=None):
        if data is None:
            data = {}
        super(OrderedDict, self).__init__(data)
        if isinstance(data, dict):
            self.keyOrder = data.keys()
        else:
            self.keyOrder = []
            for key, value in data:
                if key not in self.keyOrder:
                    self.keyOrder.append(key)

    def __deepcopy__(self, memo):
        from copy import deepcopy
        return self.__class__([(key, deepcopy(value, memo))
                               for key, value in self.iteritems()])

    def __setitem__(self, key, value):
        super(OrderedDict, self).__setitem__(key, value)
        if key not in self.keyOrder:
            self.keyOrder.append(key)

    def __delitem__(self, key):
        super(OrderedDict, self).__delitem__(key)
        self.keyOrder.remove(key)

    def __iter__(self):
        for k in self.keyOrder:
            yield k

    def pop(self, k, *args):
        result = super(OrderedDict, self).pop(k, *args)
        try:
            self.keyOrder.remove(k)
        except ValueError:
            # Key wasn't in the dictionary in the first place. No problem.
            pass
        return result

    def popitem(self):
        result = super(OrderedDict, self).popitem()
        self.keyOrder.remove(result[0])
        return result

    def items(self):
        return zip(self.keyOrder, self.values())

    def iteritems(self):
        for key in self.keyOrder:
            yield key, super(OrderedDict, self).__getitem__(key)

    def keys(self):
        return self.keyOrder[:]

    def iterkeys(self):
        return iter(self.keyOrder)

    def values(self):
        return [super(OrderedDict, self).__getitem__(k) for k in self.keyOrder]

    def itervalues(self):
        for key in self.keyOrder:
            yield super(OrderedDict, self).__getitem__(key)

    def update(self, dict_):
        for k, v in dict_.items():
            self.__setitem__(k, v)

    def setdefault(self, key, default):
        if key not in self.keyOrder:
            self.keyOrder.append(key)
        return super(OrderedDict, self).setdefault(key, default)

    def value_for_index(self, index):
        """Return the value of the item at the given zero-based index."""
        return self[self.keyOrder[index]]

    def insert(self, index, key, value):
        """Insert the key, value pair before the item with the given index."""
        if key in self.keyOrder:
            n = self.keyOrder.index(key)
            del self.keyOrder[n]
            if n < index:
                index -= 1
        self.keyOrder.insert(index, key)
        super(OrderedDict, self).__setitem__(key, value)

    def copy(self):
        """Return a copy of this object."""
        # This way of initializing the copy means it works for subclasses, too.
        obj = self.__class__(self)
        obj.keyOrder = self.keyOrder[:]
        return obj

    def __repr__(self):
        """
        Replace the normal dict.__repr__ with a version that returns the keys
        in their sorted order.
        """
        return '{%s}' % ', '.join(['%r: %r' % (k, v) for k, v in self.items()])

    def clear(self):
        super(OrderedDict, self).clear()
        self.keyOrder = []

    def index(self, key):
        """ Return the index of a given key. """
        return self.keyOrder.index(key)

    def index_for_location(self, location):
        """ Return index or None for a given location. """
        if location == '_begin':
            i = 0
        elif location == '_end':
            i = None
        elif location.startswith('<') or location.startswith('>'):
            i = self.index(location[1:])
            if location.startswith('>'):
                if i >= len(self):
                    # last item
                    i = None
                else:
                    i += 1
        else:
            raise ValueError('Not a valid location: "%s". Location key '
                             'must start with a ">" or "<".' % location)
        return i

    def add(self, key, value, location):
        """ Insert by key location. """
        i = self.index_for_location(location)
        if i is not None:
            self.insert(i, key, value)
        else:
            self.__setitem__(key, value)

    def link(self, key, location):
        """ Change location of an existing item. """
        n = self.keyOrder.index(key)
        del self.keyOrder[n]
        i = self.index_for_location(location)
        try:
            if i is not None:
                self.keyOrder.insert(i, key)
            else:
                self.keyOrder.append(key)
        except Error:
            # restore to prevent data loss and reraise
            self.keyOrder.insert(n, key)
            raise Error
