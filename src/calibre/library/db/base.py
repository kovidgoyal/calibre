#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


''' Design documentation {{{

    Storage paradigm {{{
        * Agnostic to storage paradigm (i.e. no book per folder assumptions)
        * Two separate concepts: A store and collection
          A store is a backend, like a sqlite database associated with a path on
          the local filesystem, or a cloud based storage solution.
          A collection is a user defined group of stores. Most of the logic for
          data manipulation sorting/searching/restrictions should be in the collection
          class. The collection class should transparently handle the
          conversion from store name + id to row number in the collection.
        * Not sure how feasible it is to allow many-many maps between stores
          and collections.
    }}}

    Event system {{{
        * Comprehensive event system that other components can subscribe to
        * Subscribers should be able to temporarily block receiving events
        * Should event dispatch be asynchronous?
        * Track last modified time for metadata and each format
    }}}
}}}'''

# Imports {{{
# }}}




