#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, subprocess, socket

BASE = '/srv/download/bw'

def main():
    if not os.path.exists(BASE):
        os.makedirs(BASE)
    os.chdir(BASE)

    for name in 'hours days months top10 summary'.split():
        subprocess.check_call(['vnstati', '--' + name, '-o', name + '.png'])

    html = '''\
    <!DOCTYPE html>
    <html>
    <head><title>Bandwidth usage for {host}</title></head>
    <body>
    <style> .float {{ float: left; margin-right:30px; margin-left:30px; text-align:center; width: 500px; }}</style>
    <h1>Bandwidth usage for {host}</h1>
    <div class="float">
    <h2>Summary</h2>
    <img src="summary.png"/>
    </div>
    <div class="float">
    <h2>Hours</h2>
    <img src="hours.png"/>
    </div>
    <div class="float">
    <h2>Days</h2>
    <img src="days.png"/>
    </div>
    <div class="float">
    <h2>Months</h2>
    <img src="months.png"/>
    </div>
    <div class="float">
    <h2>Top10</h2>
    <img src="top10.png"/>
    </div>
    </body>
    </html>
    '''.format(host=socket.gethostname())

    with open('index.html', 'wb') as f:
        f.write(html.encode('utf-8'))

if __name__ == '__main__':
    main()
