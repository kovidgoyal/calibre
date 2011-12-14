#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2011, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
###

viewport_top = (node) ->
    node.offsetTop - window.pageYOffset

viewport_left = (node) ->
    node.offsetLeft - window.pageXOffset


window.onload = ->
    h1 = document.getElementsByTagName('h1')[0]
    x = h1.scrollLeft + 150
    y = viewport_top(h1) + h1.offsetHeight/2
    e = document.elementFromPoint x, y
    if e.getAttribute('id') != 'first-h1'
        alert 'Failed to find top h1'
        return
    alert window.cfi.at x, y

