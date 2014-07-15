#!/usr/bin/python2.7
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import __builtin__

import cherrypy

from calibre import fit_image, guess_type
from calibre.utils.filenames import ascii_filename
from calibre.ebooks.metadata.meta import set_metadata
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.smtp import sendmail, create_mail

class ShareServer(object):
    'Serves Share and the Ajax based HTML frontend'

    def add_routes(self, connect):
        connect('share_kindle', '/book/{id}/share/kindle', self.share_kindle)

    def share_kindle(self, id=None, what="mobi", _=None ):
        try:
            id_ = int(id)
        except:
            raise cherrypy.HTTPError(404, 'invalid id: %r'%id)
        id = id_
        if not self.db.has_id(id):
            raise cherrypy.HTTPError(404, 'id:%d does not exist in database'%id)

        # check format
        what = what.upper()
        fm = self.db.format_metadata(id, what, allow_cache=False)
        if not fm:
            raise cherrypy.HTTPError(404, 'book: %d does not have format: %s'%(id, what))
        fmt = self.db.format(id, what, index_is_id=True, as_file=True, mode='rb')
        if fmt is None:
            raise cherrypy.HTTPError(404, 'book: %d does not have format: %s'%(id, what))

        # read meta info
        mi = self.db.get_metadata(id, index_is_id=True)
        set_metadata(fmt, mi, what.lower())
        au = authors_to_string(mi.authors if mi.authors else
                [_('Unknown')])
        title = mi.title if mi.title else _('Unknown')
        fname = u'%s - %s_%s.%s'%(title[:30], au[:30], id, what.lower())
        fname = ascii_filename(fname).replace('"', '_')
        fmt.seek(0)
        body = fmt.read()

        # content type
        mt = guess_type('dummy.'+what.lower())[0]
        if mt is None:
            mt = 'application/octet-stream'

        # send mail
        mail_username = 'calibre'
        mail_password = 'calibre19871987'
        mail_from = 'calibre@lib.talebook.org'
        mail_to = 'talebook.cn@kindle.cn'
        mail_to = 'talebook@foxmail.com'
        mail_subject = '<%s> from calibre' % title
        mail_body = 'We Send this book <%s> for your kindle.' % title
        try:
            msg = create_mail(mail_from, mail_to, mail_subject,
                    text = mail_body, attachment_data = body,
                    attachment_type = mt, attachment_name = fname
                    )
            sendmail(msg, from_=mail_from, to=[mail_to],
                timeout=30,
                username=mail_username,
                password=mail_password)
            output = "ok"
        except:
            import traceback
            cherrypy.log.error('Failed to generate cover:')
            cherrypy.log.error(traceback.format_exc())
            output = traceback.format_exc()

        # send response
        cherrypy.response.headers['Content-Type'] = 'text/html'
        cherrypy.response.body = output
        return output


