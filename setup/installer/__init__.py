#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import subprocess, tempfile, os, time, socket

from setup import Command, installer_name
from setup.build_environment import BUILD_HOST, PROJECT

BASE_RSYNC = ['rsync', '-av', '--delete', '--force']
EXCLUDES = []
for x in [
    'src/calibre/plugins', 'manual', 'translations',
    '.bzr', '.git', '.build', '.svn', 'build', 'dist', 'imgsrc', '*.pyc', '*.pyo', '*.swp',
    '*.swo', 'format_docs', 'translations']:
    EXCLUDES.extend(['--exclude', x])
SAFE_EXCLUDES = ['"%s"'%x if '*' in x else x for x in EXCLUDES]

def get_rsync_pw():
    return open('/home/kovid/work/env/private/buildbot').read().decode('utf-8').partition(
                ':')[-1].strip()

def is_vm_running(name):
    qname = '"%s"' % name
    for line in subprocess.check_output('VBoxManage list runningvms'.split()).decode('utf-8').splitlines():
        if line.startswith(qname):
            return True
    return False

def is_host_reachable(name, timeout=1):
    try:
        socket.create_connection((name, 22), timeout).close()
        return True
    except:
        return False

class Rsync(Command):

    description = 'Sync source tree from development machine'

    SYNC_CMD = ' '.join(BASE_RSYNC+SAFE_EXCLUDES+
            ['rsync://buildbot@{host}/work/{project}', '..'])

    def run(self, opts):
        cmd = self.SYNC_CMD.format(host=BUILD_HOST, project=PROJECT)
        env = dict(os.environ)
        env['RSYNC_PASSWORD'] = get_rsync_pw()
        self.info(cmd)
        subprocess.check_call(cmd, shell=True, env=env)

def push(host, vmname, available):
    if vmname is None:
        hostname = host.partition(':')[0].partition('@')[-1]
        ok = is_host_reachable(hostname)
    else:
        ok = is_vm_running(vmname)
    if ok:
        available[vmname or host] = True
        rcmd = BASE_RSYNC + EXCLUDES + ['.', host]
        print ('\n\nPushing to:', vmname or host, '\n')
        subprocess.check_call(rcmd, stdout=open(os.devnull, 'wb'))

class Push(Command):

    description = 'Push code to another host'

    def run(self, opts):
        from threading import Thread
        threads, available = {}, {}
        for host, vmname in {
                r'Owner@winxp:/cygdrive/c/Documents\ and\ Settings/Owner/calibre':'winxp',
                'kovid@ox:calibre':None,
                r'kovid@win7:/cygdrive/c/Users/kovid/calibre':'Windows 7',
                'kovid@win7-x64:calibre':'win7-x64',
                'kovid@tiny:calibre':None,
                'kovid@getafix:calibre-src':None,
                }.iteritems():
                threads[vmname or host] = thread = Thread(target=push, args=(host, vmname, available))
                thread.start()
        while threads:
            for name, thread in tuple(threads.iteritems()):
                thread.join(0.01)
                if not thread.is_alive():
                    if available.get(name, False):
                        print ('\n\n', name, 'done')
                    threads.pop(name)


class VMInstaller(Command):

    INSTALLER_EXT = None
    VM_NAME = None
    FREEZE_COMMAND = None
    FREEZE_TEMPLATE = 'python setup.py {freeze_command}'
    SHUTDOWN_CMD = ['sudo', 'shutdown', '-h', 'now']
    IS_64_BIT = False

    BUILD_CMD = 'ssh -t %s bash build-calibre'
    BUILD_PREFIX = ['#!/bin/bash', 'export CALIBRE_BUILDBOT=1']
    BUILD_RSYNC  = ['mkdir -p ~/build/{project}', r'cd ~/build/{project}', Rsync.SYNC_CMD]
    BUILD_CLEAN  = ['rm -rf dist/* build/* src/calibre/plugins/*']
    BUILD_BUILD  = ['python setup.py build',]
    FORCE_SHUTDOWN = 0  # number of seconds to wait before doing a forced power off (0 means disabled)

    def add_options(self, parser):
        if not parser.has_option('--dont-shutdown'):
            parser.add_option('-s', '--dont-shutdown', default=False,
                action='store_true', help='Dont shutdown the VM after building')

    def get_build_script(self):
        rs = ['export RSYNC_PASSWORD=%s'%get_rsync_pw()]
        ans = '\n'.join(self.BUILD_PREFIX + rs)+'\n\n'
        ans += ' && \\\n'.join(self.BUILD_RSYNC) + ' && \\\n'
        ans += ' && \\\n'.join(self.BUILD_CLEAN) + ' && \\\n'
        ans += ' && \\\n'.join(self.BUILD_BUILD) + ' && \\\n'
        ans += self.FREEZE_TEMPLATE.format(freeze_command=self.FREEZE_COMMAND) + '\n'
        ans = ans.format(project=PROJECT, host=BUILD_HOST)
        return ans

    def run_vm(self):
        if is_vm_running(self.VM_NAME):
            return True
        self.__p = subprocess.Popen(("VBoxManage startvm %s --type gui" % self.VM_NAME).split())
        return False

    def start_vm(self, sleep=75):
        ssh_host = self.VM_NAME
        already_running = self.run_vm()
        if not already_running:
            time.sleep(2)
        print ('Waiting for SSH server to start')
        while not is_host_reachable(ssh_host, timeout=1):
            time.sleep(0.1)

    def run_vm_builder(self):
        ssh_host = self.VM_NAME
        build_script = self.get_build_script()
        t = tempfile.NamedTemporaryFile(suffix='.sh')
        t.write(build_script)
        t.flush()
        print ('Running VM builder')
        subprocess.check_call(('scp', t.name, ssh_host+':build-calibre'))
        subprocess.check_call(self.BUILD_CMD%ssh_host, shell=True)
        self.download_installer()

    def installer(self):
        return installer_name(self.INSTALLER_EXT, self.IS_64_BIT)

    def run(self, opts):
        subprocess.call(['chmod', '-R', '+r', 'recipes'])
        self.start_vm()
        self.run_vm_builder()
        if not opts.dont_shutdown:
            print ('Shutting down', self.VM_NAME)
            subprocess.call(['ssh', self.VM_NAME]+self.SHUTDOWN_CMD)
            if self.FORCE_SHUTDOWN:
                while is_host_reachable(self.VM_NAME):
                    time.sleep(0.1)  # wait for SSH server to shutdown
                time.sleep(self.FORCE_SHUTDOWN)
                subprocess.check_call(('VBoxManage controlvm %s poweroff' % self.VM_NAME).split())

    def download_installer(self):
        installer = self.installer()
        subprocess.check_call(['scp',
            self.VM_NAME+':build/calibre/'+installer, 'dist'])
        if not os.path.exists(installer):
            self.warn('Failed to download installer: '+installer)
            raise SystemExit(1)

    def clean(self):
        installer = self.installer()
        if os.path.exists(installer):
            os.remove(installer)

