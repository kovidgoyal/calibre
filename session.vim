" Scan the following dirs (recursively for tags
let g:project_tags_dirs = ['src/calibre']

set wildignore+=resources/mathjax/*
set wildignore+=resources/rapydscript/lib/*
set wildignore+=build/*
set wildignore+=dist/*
set wildignore+=manual/generated/*
set wildignore+=manual/locale/*
set wildignore+=imgsrc/*

fun! CalibreLog()
    " Setup buffers to edit the calibre changelog and version info prior to
    " making a release.
    enew
    read ! git log  "--pretty=\%an:::\%n\%s\%n\%b\%n" -500
    setl nomodifiable noswapfile buftype=nofile
    hi def link au Keyword
    syntax match au /^.*:::$/
    nnoremap <silent> <buffer> n :call cursor(1+search('\V:::\$', 'n'), 0)<CR>
    nnoremap <silent> <buffer> yb v/#<CR>t<Space>y:nohl<CR>
    normal! gg2j
    edit Changelog.txt
    edit src/calibre/constants.py
endfun

nnoremap \log :call CalibreLog()<CR>
