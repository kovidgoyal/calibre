#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, shutil, subprocess, re, time, glob
from datetime import datetime

from setup import Command, __appname__, __version__


class Stage1(Command):

    description = 'Stage 1 of the publish process'

    sub_commands = [
            'check',
            'pot',
            'build',
            'resources',
            'translations',
            'iso639',
            'gui',
            ]

class Stage2(Command):

   description = 'Stage 2 of the publish process'
   sub_commands = ['linux', 'win', 'osx']

   def pre_sub_commands(self, opts):
       for x in glob.glob(os.path.join(self.d(self.SRC), 'dist', '*')):
           os.remove(x)


class Stage3(Command):

   description = 'Stage 3 of the publish process'
   sub_commands = ['upload_rss', 'upload_user_manual', 'upload_demo',
            'pypi_upload', 'tag_release', 'upload_installers',
            'upload_to_server']

class Publish(Command):

    description = 'Publish a new calibre release'
    sub_commands = ['stage1', 'stage2', 'stage3']

class Manual(Command):

    description='''Build the User Manual '''

    def run(self, opts):
        cwd = os.path.abspath(os.getcwd())
        os.chdir(os.path.join(self.SRC, 'calibre', 'manual'))
        try:
            for d in ('.build', 'cli'):
                if os.path.exists(d):
                    shutil.rmtree(d)
                os.makedirs(d)
            if not os.path.exists('.build'+os.sep+'html'):
                os.makedirs('.build'+os.sep+'html')
            os.environ['__appname__']= __appname__
            os.environ['__version__']= __version__
            subprocess.check_call(['sphinx-build', '-b', 'custom', '-t', 'online',
                                   '-d', '.build/doctrees', '.', '.build/html'])
            subprocess.check_call(['sphinx-build', '-b', 'epub', '-d',
                                   '.build/doctrees', '.', '.build/epub'])
            shutil.copyfile(self.j('.build', 'epub', 'calibre.epub'), self.j('.build',
                'html', 'calibre.epub'))
        finally:
            os.chdir(cwd)

    def clean(self):
        path = os.path.join(self.SRC, 'calibre', 'manual', '.build')
        if os.path.exists(path):
            shutil.rmtree(path)

class TagRelease(Command):

    description = 'Tag a new release in bzr'

    def run(self, opts):
        self.info('Tagging release')
        subprocess.check_call(('bzr tag '+__version__).split())
        subprocess.check_call('bzr commit --unchanged -m'.split() + ['IGN:Tag release'])

if os.environ.get('CALIBRE_BUILDBOT', None) == '1':
    class UploadRss(Command):
        pass
else:
    class UploadRss(Command):

        description = 'Generate and upload a RSS feed of calibre releases'

        from bzrlib import log as blog

        class ChangelogFormatter(blog.LogFormatter):
            supports_tags = True
            supports_merge_revisions = False
            _show_advice = False

            def __init__(self, num_of_versions=20):
                sys.path.insert(0, os.path.join(Command.SRC, 'calibre', 'utils'))
                from rss_gen import RSS2
                self.num_of_versions = num_of_versions
                self.rss = RSS2(
                                title = 'calibre releases',
                                link  = 'http://calibre.kovidgoyal.net/wiki/Changelog',
                                description = 'Latest release of calibre',
                                lastBuildDate = datetime.utcnow()
                                )
                self.current_entry = None

            def log_revision(self, r):
                from rss_gen import RSSItem, Guid
                if len(self.rss.items) > self.num_of_versions-1:
                    return
                msg = r.rev.message
                match = re.match(r'version\s+(\d+\.\d+.\d+)', msg)

                if match:
                    if self.current_entry is not None:
                        mkup = '<div><ul>%s</ul></div>'
                        self.current_entry.description = mkup%(''.join(
                                    self.current_entry.description))
                        if match.group(1) == '0.5.14':
                            self.current_entry.description = \
                            '''<div>See <a href="http://calibre.kovidgoyal.net/new_in_6">New in
                            6</a></div>'''
                        self.rss.items.append(self.current_entry)
                    timestamp = r.rev.timezone + r.rev.timestamp
                    self.current_entry = RSSItem(
                            title = 'calibre %s released'%match.group(1),
                            link  = 'http://calibre.kovidgoyal.net/download',
                            guid = Guid(match.group(), False),
                            pubDate = datetime(*time.gmtime(timestamp)[:6]),
                            description = []
                    )
                elif self.current_entry is not None:
                    if re.search(r'[a-zA-Z]', msg) and len(msg.strip()) > 5:
                        if 'translation' not in msg and not msg.startswith('IGN'):
                            msg = msg.replace('<', '&lt;').replace('>', '&gt;')
                            msg = re.sub('#(\d+)', r'<a href="http://calibre.kovidgoyal.net/ticket/\1">#\1</a>',
                                            msg)

                            self.current_entry.description.append(
                                            '<li>%s</li>'%msg.strip())


        def run(self, opts):
            from bzrlib import log, branch
            bzr_path = os.path.expanduser('~/work/calibre')
            b = branch.Branch.open(bzr_path)
            lf = UploadRss.ChangelogFormatter()
            self.info('\tGenerating bzr log...')
            log.show_log(b, lf)
            lf.rss.write_xml(open('/tmp/releases.xml', 'wb'))
            self.info('\tUploading RSS to server...')
            subprocess.check_call('scp /tmp/releases.xml divok:/var/www/calibre.kovidgoyal.net/htdocs/downloads'.split())

