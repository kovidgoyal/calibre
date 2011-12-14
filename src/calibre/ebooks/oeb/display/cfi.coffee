#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2011, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
###

log = (error) ->
    if error and window?.console?.log
        window.console.log(error)

fstr = (d) -> # {{{
    # Convert a timestamp floating point number to a string
    ans = ""
    if ( d < 0 )
        ans = "-"
        d = -d
    n = Math.floor(d)
    ans += n
    n = Math.round((d-n)*100)
    if( n != 0 )
        ans += "."
        ans += if (n % 10 == 0) then (n/10) else n
    ans
# }}}

class CanonicalFragmentIdentifier

    # This class is a namespace to expose CFI functions via the window.cfi
    # object

    constructor: () ->

    encode: (doc, node, offset, tail) -> # {{{
        cfi = tail or ""

        # Handle the offset, if any
        switch node.nodeType
            when 1 # Element node
                if typeoff(offset) == 'number'
                    node = node.childNodes.item(offset)
            when 3, 4, 5, 6 # Text/entity/CDATA node
                offset or= 0
                while true
                    p = node.previousSibling
                    if (p?.nodeType not in [3, 4, 5, 6])
                        break
                    offset += p.nodeValue.length
                    node = p
                cfi = ":" + offset + cfi
            else # Not handled
                log("Offsets for nodes of type #{ node.nodeType } are not handled")

        # Construct the path to node from root
        until node == doc
            p = node.parentNode
            if not p
                if node.nodeType == 9 # Document node (iframe)
                    win = node.defaultView
                    if win.frameElement
                        node = win.frameElement
                        cfi = "!" + cfi
                        continue
                break
            # Increase index by the length of all previous sibling text nodes
            index = 0
            child = p.firstChild
            while true
                index |= 1
                if child.nodeType in [1, 7]
                    index++
                if child == node
                    break
                child = child.nextSibling

            # Add id assertions for robustness where possible
            id = node.getAttribute?('id')
            idspec = if id then "[#{ id }]" else ''
            cfi = '/' + index + idspec + cfi
            node = p

        cfi
    # }}}

    at: (x, y, doc=window.document) -> # {{{
        cdoc = doc
        target = null
        cwin = cdoc.defaultView
        tail = ''
        offset = null
        name = null

        # Drill down into iframes, etc.
        while true
            target = cdoc.elementFromPoint x, y
            if not target or target.localName == 'html'
                log("No element at (#{ x }, #{ y })")
                return null

            name = target.localName
            if name not in ['iframe', 'embed', 'object']
                break

            cd = target.contentDocument
            if not cd
                break

            x = x + cwin.pageXOffset - target.offsetLeft
            y = y + cwin.pageYOffset - target.offsetTop
            cdoc = cd
            cwin = cdoc.defaultView

        target.normalize()

        if name in ['audio', 'video']
            tail = "~" + fstr target.currentTime

        else if name in ['img']
            px = ((x + cwin.scrollX - target.offsetLeft)*100)/target.offsetWidth
            py = ((y + cwin.scrollY - target.offsetTop)*100)/target.offsetHeight
            tail = "#{ tail }@#{ fstr px },#{ fstr py }"
        else
            if cdoc.caretRangeFromPoint # WebKit
                range = cdoc.caretRangeFromPoint(x, y)
                if range
                    target = range.startContainer
                    offset = range.startOffset
            else
                # TODO: implement a span bisection algorithm for UAs
                # without caretRangeFromPoint (Gecko, IE)

        this.encode(doc, target, offset, tail)
    # }}}

window.cfi = new CanonicalFragmentIdentifier()
