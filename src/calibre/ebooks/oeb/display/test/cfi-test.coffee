#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2011, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
###

log = (error) ->
    if error
        if window?.console?.log
            window.console.log(error)
        else if process?.stdout?.write
            process.stdout.write(error + '\n')

viewport_top = (node) ->
    $(node).offset().top - window.pageYOffset

viewport_left = (node) ->
    $(node).offset().left - window.pageXOffset

show_cfi = (dont_seek) ->
    if window.current_cfi
        pos = window.cfi.point(window.current_cfi)
        ms = document.getElementById("marker").style
        if pos
            ms.visibility = "visible"
            ms.top = (pos.y - 30) + window.scrollY + "px"
            ms.left = (pos.x - 1) + window.scrollX + "px"
            if not dont_seek
                if typeof pos.time == "number"
                    window.cfi.set_current_time(pos.node, pos.time)
                scrollTo(0, pos.y - 30)
    null

RELOAD = true

mark_and_reload = (evt) ->
    window.current_cfi = window.cfi.at(evt.clientX, evt.clientY)
    if not RELOAD
        show_cfi(true)
    if window.current_cfi
        fn = () ->
            newloc = window.location.href.replace(/#.*$/, '') + "#epubcfi(#{ window.current_cfi })"
            window.location.replace(newloc)
            if RELOAD
                window.location.reload()

        setTimeout(fn, 1)
    null

window.onload = ->
    window.onscroll = show_cfi
    window.onresize = show_cfi
    document.onclick = mark_and_reload
    for iframe in document.getElementsByTagName("iframe")
        iframe.contentWindow.onscroll = show_cfi
    r = location.hash.match(/#epubcfi\((.+)\)$/)
    if r
        window.current_cfi = r[1]
        setTimeout(show_cfi, 1)
    null


