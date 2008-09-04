__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Manage translation of user visible strings.
'''
import shutil, tarfile, re, os, subprocess, urllib2

def import_from_launchpad(url):
    f = open('/tmp/launchpad_export.tar.gz', 'wb')
    shutil.copyfileobj(urllib2.urlopen(url), f)
    f.close()
    tf = tarfile.open('/tmp/launchpad_export.tar.gz', 'r:gz')
    next = tf.next()
    while next is not None:
        if next.isfile() and next.name.endswith('.po'):
            try:
                po = re.search(r'-([a-z]{2,3}\.po)', next.name).group(1)
            except:
                next = tf.next()
                continue
            out = os.path.abspath(os.path.join('.', os.path.basename(po)))
            print 'Updating', '%6s'%po, '-->', out
            open(out, 'wb').write(tf.extractfile(next).read())
        next = tf.next()
    check_for_critical_bugs()
    return 0
 
def check_for_critical_bugs():
    if os.path.exists('.errors'):
        shutil.rmtree('.errors')
    pofilter = ('pofilter', '-i', '.', '-o', '.errors',
                '-t', 'accelerators', '-t', 'escapes', '-t', 'variables',
                '-t', 'xmltags')
    subprocess.check_call(pofilter)
    errs = os.listdir('.errors')
    if errs:
        print 'WARNING: Translation errors detected'
        print 'See the .errors directory and http://translate.sourceforge.net/wiki/toolkit/using_pofilter' 

if __name__ == '__main__':
    import sys
    import_from_launchpad(sys.argv[1])

