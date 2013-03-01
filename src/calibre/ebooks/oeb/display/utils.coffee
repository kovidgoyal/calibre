#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2012, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
###

class CalibreUtils
    # This class is a namespace to expose functions via the
    # window.calibre_utils object.

    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('CalibreUtils constructor called as function')
        this.dom_attr = 'calibre_f3fa75ca98eb4413a4ee413f20f60226'
        this.dom_data = []

    # Data API {{{

    retrieve: (node, key, def=null) ->
        # Retrieve data previously stored on node (a DOM node) with key (a
        # string). If no such data is found then return the value of def.
        idx = parseInt(node.getAttribute(this.dom_attr))
        if isNaN(idx)
            return def
        data = this.dom_data[idx]
        if not data.hasOwnProperty(key)
            return def
        return data[key]

    store: (node, key, val) ->
        # Store arbitrary javscript object val on DOM node node with key (a
        # string). This can be later retrieved by the retrieve method.
        idx = parseInt(node.getAttribute(this.dom_attr))
        if isNaN(idx)
            idx = this.dom_data.length
            node.setAttribute(this.dom_attr, idx+'')
            this.dom_data.push({})
        this.dom_data[idx][key] = val
    # }}}

    log: (args...) -> # {{{
        # Output args to the window.console object. args are automatically
        # coerced to strings
        if args
            msg = args.join(' ')
            if window?.console?.log
                window.console.log(msg)
            else if process?.stdout?.write
                process.stdout.write(msg + '\n')
    # }}}

    window_scroll_pos: (win=window) -> # {{{
        # The current scroll position of the browser window
        if typeof(win.pageXOffset) == 'number'
            x = win.pageXOffset
            y = win.pageYOffset
        else # IE < 9
            if document.body and ( document.body.scrollLeft or document.body.scrollTop )
                x = document.body.scrollLeft
                y = document.body.scrollTop
            else if document.documentElement and ( document.documentElement.scrollLeft or document.documentElement.scrollTop)
                y = document.documentElement.scrollTop
                x = document.documentElement.scrollLeft
        return [x, y]
    # }}}

    viewport_to_document: (x, y, doc=window?.document) -> # {{{
        # Convert x, y from the viewport (window) co-ordinate system to the
        # document (body) co-ordinate system
        until doc == window.document
            # We are in a frame
            frame = doc.defaultView.frameElement
            rect = frame.getBoundingClientRect()
            x += rect.left
            y += rect.top
            doc = frame.ownerDocument
        win = doc.defaultView
        [wx, wy] = this.window_scroll_pos(win)
        x += wx
        y += wy
        return [x, y]
    # }}}

    absleft: (elem) -> # {{{
        # The left edge of elem in document co-ords. Works in all
        # circumstances, including column layout. Note that this will cause
        # a relayout if the render tree is dirty. Also, because of a bug in the
        # version of WebKit bundled with Qt 4.8, this does not always work, see
        # https://bugs.launchpad.net/bugs/1132641 for a test case.
        r = elem.getBoundingClientRect()
        return this.viewport_to_document(r.left, 0, elem.ownerDocument)[0]
    # }}}

if window?
    window.calibre_utils = new CalibreUtils()

