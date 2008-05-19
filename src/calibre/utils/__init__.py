#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Miscelleaneous utilities.
'''
import subprocess

from calibre import iswindows, isosx
from calibre.ptempfile import PersistentTemporaryFile

def sendmail(recipient='', subject='', attachments=[], body=''):
    if not recipient:
        recipient = 'someone@somewhere.net'
    if isinstance(recipient, unicode):
        recipient = recipient.encode('utf-8')
    if isinstance(subject, unicode):
        subject = subject.encode('utf-8')
    if isinstance(body, unicode):
        body = body.encode('utf-8')
    for i, src in enumerate(attachments):
        if isinstance(src, unicode):
            attachments[i] = src.encode('utf-8')
    
    if iswindows:
        from calibre.utils.simplemapi import SendMail
        SendMail(recipient, subject=subject, body=body, attachfiles=';'.join(attachments))
    elif isosx:
        pt = PersistentTemporaryFile(suffix='.txt')
        pt.write(body)
        if attachments:
            pt.write('\n\n----\n\n')
            pt.write(open(attachments[0], 'rb').read())
        pt.close()
        
        subprocess.Popen(('open', '-t', pt.name))
         
    else:
        body = '"' + body.replace('"', '\\"') + '"'
        subject = '"' + subject.replace('"', '\\"') + '"'
        attach = ''
        if attachments:
            attach = attachments[0]
            attach = '"' + attach.replace('"', '\\"') + '"'
            attach = '--attach '+attach
        subprocess.check_call('xdg-email --utf8 --subject %s --body %s %s %s'%(subject, body, attach, recipient), shell=True)