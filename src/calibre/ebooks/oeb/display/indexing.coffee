#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2012, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
###

body_height = () ->
    db = document.body
    dde = document.documentElement
    if db? and dde?
        return Math.max(db.scrollHeight, dde.scrollHeight, db.offsetHeight,
            dde.offsetHeight, db.clientHeight, dde.clientHeight)
    return 0

abstop = (elem) ->
    ans = elem.offsetTop
    while elem.offsetParent
        elem = elem.offsetParent
        ans += elem.offsetTop
    return ans

class BookIndexing
    ###
    This class is a namespace to expose indexing functions via the
    window.book_indexing object. The most important functions are:

    anchor_positions(): Get the absolute (document co-ordinate system) position
    for elements with the specified id/name attributes.

    ###

    constructor: () ->
        this.cache = {}
        this.body_height_at_last_check = null

    cache_valid: (anchors) ->
        for a in anchors
            if not Object.prototype.hasOwnProperty.call(this.cache, a)
                return false
        for p of this.cache
            if Object.prototype.hasOwnProperty.call(this.cache, p) and p not in anchors
                return false
        return true

    anchor_positions: (anchors, use_cache=false) ->
        if use_cache and body_height() == this.body_height_at_last_check and this.cache_valid(anchors)
            return this.cache

        ans = {}
        for anchor in anchors
            elem = document.getElementById(anchor)
            if elem == null
                # Look for an <a name="anchor"> element
                try
                    result = document.evaluate(
                        ".//*[local-name() = 'a' and @name='#{ anchor }']",
                        document.body, null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE, null)
                    elem = result.singleNodeValue
                catch error
                    # The anchor had a ' or other invalid char
                    elem = null
            if elem == null
                pos = body_height() + 10000
            else
                pos = abstop(elem)
            ans[anchor] = pos
        this.cache = ans
        this.body_height_at_last_check = body_height()
        return ans

if window?
    window.book_indexing = new BookIndexing()

