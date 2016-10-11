#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

# Based on https://github.com/jlhutch/pylru/blob/master/pylru.py (which is
# licensed GPL v2+)


class DoublyLinkedNode(object):

    __slots__ = 'empty prev next key value'.split()

    def __init__(self):
        self.empty = True
        self.prev = self.next = self.key = self.value = None


class lru_cache(object):

    '''
    An LRU cache with constant time lookup. Uses a doubly linked list that is
    pre-allocated based on the cache size. Infinite caches are not supported.
    '''

    def __init__(self, size=1000, callback=None):
        ''' callback is called with the key and value when the item is either replaced or removed from the cache. '''

        self.callback = callback

        # Create an empty hash table.
        self.table = {}

        # Initialize the doubly linked list with one empty node. This is an
        # invariant. The cache size must always be greater than zero. Each
        # node has a 'prev' and 'next' variable to hold the node that comes
        # before it and after it respectively. Initially the two variables
        # each point to the head node itself, creating a circular doubly
        # linked list of size one. Then the size property is used to adjust
        # the list to the desired size.
        self.head = DoublyLinkedNode()
        self.head.next = self.head
        self.head.prev = self.head
        self._size = 1

        # Adjust the size
        self.size = size

    def __len__(self):
        return len(self.table)

    def clear(self):
        for node in self:
            node.empty = True
            node.key = None
            node.value = None

        self.table.clear()

    def __contains__(self, key):
        return key in self.table

    def peek(self, key):
        ' Looks up a value in the cache without affecting cache order. '
        return self.table[key].value

    def __getitem__(self, key):
        # Look up the node
        node = self.table[key]

        # Update the list ordering. Move this node so that is directly
        # proceeds the head node. Then set the 'head' variable to it. This
        # makes it the new head of the list.
        self.move_to_front(node)
        self.head = node

        # Return the value.
        return node.value

    def get(self, key, default=None):
        """Get an item - return default (None) if not present"""
        try:
            return self[key]
        except KeyError:
            return default

    def set(self, key, value):
        self[key] = value

    def __setitem__(self, key, value):
        # First, see if any value is stored under 'key' in the cache already.
        # If so we are going to replace that value with the new one.
        node = self.table.get(key)
        if node is not None:
            # Replace the value.
            node.value = value

            # Update the list ordering.
            self.move_to_front(node)
            self.head = node
            return

        # Ok, no value is currently stored under 'key' in the cache. We need
        # to choose a node to place the new item in. There are two cases. If
        # the cache is full some item will have to be pushed out of the
        # cache. We want to choose the node with the least recently used
        # item. This is the node at the tail of the list. If the cache is not
        # full we want to choose a node that is empty. Because of the way the
        # list is managed, the empty nodes are always together at the tail
        # end of the list. Thus, in either case, by chooseing the node at the
        # tail of the list our conditions are satisfied.

        # Since the list is circular, the tail node directly preceeds the
        # 'head' node.
        node = self.head.prev

        # If the node already contains something we need to remove the old
        # key from the dictionary.
        if not node.empty:
            if self.callback is not None:
                self.callback(node.key, node.value)
            del self.table[node.key]

        # Place the new key and value in the node
        node.empty = False
        node.key = key
        node.value = value

        # Add the node to the dictionary under the new key.
        self.table[key] = node

        # We need to move the node to the head of the list. The node is the
        # tail node, so it directly preceeds the head node due to the list
        # being circular. Therefore, the ordering is already correct, we just
        # need to adjust the 'head' variable.
        self.head = node

    def __delitem__(self, key):
        # Lookup the node, then remove it from the hash table.
        node = self.table[key]
        del self.table[key]

        node.empty = True

        # Not strictly necessary.
        node.key = None
        node.value = None

        # Because this node is now empty we want to reuse it before any
        # non-empty node. To do that we want to move it to the tail of the
        # list. We move it so that it directly precedes the 'head' node. This
        # makes it the tail node. The 'head' is then adjusted. This
        # adjustment ensures correctness even for the case where the 'node'
        # is the 'head' node.
        self.move_to_front(node)
        self.head = node.next

    def __iter__(self):
        ''' Return an iterator that returns the keys in the cache in order from
        the most recently to least recently used. Does not modify the cache
        order. '''
        node = self.head
        left = len(self.table)
        while left > 0:
            left -= 1
            yield node
            node = node.next

    def items(self):
        ''' Return an iterator that returns the (key, value) pairs in the cache
        in order from the most recently to least recently used. Does not
        modify the cache order. '''
        for node in self:
            yield node.key, node.value
    iteritems = items

    def keys(self):
        ''' Return an iterator that returns the keys in the cache in order from
        the most recently to least recently used. Does not modify the cache
        order. '''
        for node in self:
            yield node.key
    iterkeys = keys

    def values(self):
        ''' Return an iterator that returns the values in the cache in order
        from the most recently to least recently used. Does not modify the
        cache order. '''
        for node in self:
            yield node.value
    itervalues = values

    @property
    def size(self):
        ' The current cache size '
        return self._size

    @size.setter
    def size(self, size):
        ' Change the current cache size, the value is auto-clamped to [1, *] '
        size = max(1, size)
        if size > self._size:
            self.expand(size - self._size)
        elif size < self._size:
            self.shrink(self._size - size)

    # Internal API {{{

    def expand(self, n):
        ' Increases the size of the cache by inserting n empty nodes at the tail of the list '
        n = max(0, n)
        left = n
        while left > 0:
            left -= 1
            node = DoublyLinkedNode()
            node.next = self.head
            node.prev = self.head.prev

            self.head.prev.next = node
            self.head.prev = node

        self._size += n

    def shrink(self, n):
        ' Decreases the size of the cache by removing n nodes from the tail of the list '
        n = max(0, min(n, self._size - 1))
        left = n
        while left > 0:
            left -= 1
            node = self.head.prev
            if not node.empty:
                if self.callback is not None:
                    self.callback(node.key, node.value)
                del self.table[node.key]

            # Splice the tail node out of the list
            self.head.prev = node.prev
            node.prev.next = self.head

            # The next four lines are not strictly necessary.
            node.prev = None
            node.next = None

            node.key = None
            node.value = None

        self._size -= n

    def move_to_front(self, node):
        ''' This method adjusts the ordering of the doubly linked list so that
        'node' directly precedes the 'head' node. Because of the order of
        operations, if 'node' already directly precedes the 'head' node or if
        'node' is the 'head' node the order of the list will be unchanged. '''
        node.prev.next = node.next
        node.next.prev = node.prev

        node.prev = self.head.prev
        node.next = self.head.prev.next

        node.next.prev = node
        node.prev.next = node

    # }}}
