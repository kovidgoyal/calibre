#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
feedjack
Gustavo Picón
update_feeds.py
"""

import os
import time
import optparse
import datetime
import socket
import traceback
import sys

import feedparser

try:
    import threadpool
except ImportError:
    threadpool = None

VERSION = '0.9.16'
URL = 'http://www.feedjack.org/'
USER_AGENT = 'Feedjack %s - %s' % (VERSION, URL)
SLOWFEED_WARNING = 10
ENTRY_NEW, ENTRY_UPDATED, ENTRY_SAME, ENTRY_ERR = range(4)
FEED_OK, FEED_SAME, FEED_ERRPARSE, FEED_ERRHTTP, FEED_ERREXC = range(5)


def encode(tstr):
    """ Encodes a unicode string in utf-8
    """
    if not tstr:
        return ''
    # this is _not_ pretty, but it works
    try:
        return tstr.encode('utf-8', "xmlcharrefreplace")
    except UnicodeDecodeError:
        # it's already UTF8.. sigh
        return tstr.decode('utf-8').encode('utf-8')

def prints(tstr):
    """ lovely unicode
    """
    sys.stdout.write('%s\n' % (tstr.encode(sys.getdefaultencoding(),
                         'replace')))
    sys.stdout.flush()

def mtime(ttime):
    """ datetime auxiliar function.
    """
    return datetime.datetime.fromtimestamp(time.mktime(ttime))

class ProcessEntry:
    def __init__(self, feed, options, entry, postdict, fpf):
        self.feed = feed
        self.options = options
        self.entry = entry
        self.postdict = postdict
        self.fpf = fpf

    def get_tags(self):
        """ Returns a list of tag objects from an entry.
        """
        from calibre.www.apps.feedjack import models

        fcat = []
        if self.entry.has_key('tags'):
            for tcat in self.entry.tags:
                if tcat.label != None:
                    term = tcat.label
                else:
                    term = tcat.term
                qcat = term.strip()
                if ',' in qcat or '/' in qcat:
                    qcat = qcat.replace(',', '/').split('/')
                else:
                    qcat = [qcat]
                for zcat in qcat:
                    tagname = zcat.lower()
                    while '  ' in tagname:
                        tagname = tagname.replace('  ', ' ')
                    tagname = tagname.strip()
                    if not tagname or tagname == ' ':
                        continue
                    if not models.Tag.objects.filter(name=tagname):
                        cobj = models.Tag(name=tagname)
                        cobj.save()
                    fcat.append(models.Tag.objects.get(name=tagname))
        return fcat

    def get_entry_data(self):
        """ Retrieves data from a post and returns it in a tuple.
        """
        try:
            link = self.entry.link
        except AttributeError:
            link = self.feed.link
        try:
            title = self.entry.title
        except AttributeError:
            title = link
        guid = self.entry.get('id', title)

        if self.entry.has_key('author_detail'):
            author = self.entry.author_detail.get('name', '')
            author_email = self.entry.author_detail.get('email', '')
        else:
            author, author_email = '', ''

        if not author:
            author = self.entry.get('author', self.entry.get('creator', ''))
        if not author_email:
            # this should be optional~
            author_email = 'nospam@nospam.com'

        try:
            content = self.entry.content[0].value
        except:
            content = self.entry.get('summary',
                                     self.entry.get('description', ''))

        if self.entry.has_key('modified_parsed'):
            date_modified = mtime(self.entry.modified_parsed)
        else:
            date_modified = None

        fcat = self.get_tags()
        comments = self.entry.get('comments', '')

        return (link, title, guid, author, author_email, content,
                date_modified, fcat, comments)

    def process(self):
        """ Process a post in a feed and saves it in the DB if necessary.
        """
        from calibre.www.apps.feedjack import models

        (link, title, guid, author, author_email, content, date_modified,
         fcat, comments) = self.get_entry_data()

        if False and self.options.verbose:
            prints(u'[%d] Entry\n' \
                   u'  title: %s\n' \
                   u'  link: %s\n' \
                   u'  guid: %s\n' \
                   u'  author: %s\n' \
                   u'  author_email: %s\n' \
                   u'  tags: %s' % (
                self.feed.id,
                title, link, guid, author, author_email,
                u' '.join(tcat.name for tcat in fcat)))

        if guid in self.postdict:
            tobj = self.postdict[guid]
            if tobj.content != content or (date_modified and
                    tobj.date_modified != date_modified):
                retval = ENTRY_UPDATED
                if self.options.verbose:
                    prints('[%d] Updating existing post: %s' % (
                           self.feed.id, link))
                if not date_modified:
                    # damn non-standard feeds
                    date_modified = tobj.date_modified
                tobj.title = title
                tobj.link = link
                tobj.content = content
                tobj.guid = guid
                tobj.date_modified = date_modified
                tobj.author = author
                tobj.author_email = author_email
                tobj.comments = comments
                tobj.tags.clear()
                [tobj.tags.add(tcat) for tcat in fcat]
                tobj.save()
            else:
                retval = ENTRY_SAME
                if self.options.verbose:
                    prints('[%d] Post has not changed: %s' % (self.feed.id,
                                                              link))
        else:
            retval = ENTRY_NEW
            if self.options.verbose:
                prints('[%d] Saving new post: %s' % (self.feed.id, link))
            if not date_modified and self.fpf:
                # if the feed has no date_modified info, we use the feed
                # mtime or the current time
                if self.fpf.feed.has_key('modified_parsed'):
                    date_modified = mtime(self.fpf.feed.modified_parsed)
                elif self.fpf.has_key('modified'):
                    date_modified = mtime(self.fpf.modified)
            if not date_modified:
                date_modified = datetime.datetime.now()
            tobj = models.Post(feed=self.feed, title=title, link=link,
                content=content, guid=guid, date_modified=date_modified,
                author=author, author_email=author_email,
                comments=comments)
            tobj.save()
            [tobj.tags.add(tcat) for tcat in fcat]
        return retval


class ProcessFeed:
    def __init__(self, feed, options):
        self.feed = feed
        self.options = options
        self.fpf = None

    def process_entry(self, entry, postdict):
        """ wrapper for ProcessEntry
        """
        entry = ProcessEntry(self.feed, self.options, entry, postdict,
                             self.fpf)
        ret_entry = entry.process()
        del entry
        return ret_entry

    def process(self):
        """ Downloads and parses a feed.
        """
        from calibre.www.apps.feedjack import models

        ret_values = {
            ENTRY_NEW:0,
            ENTRY_UPDATED:0,
            ENTRY_SAME:0,
            ENTRY_ERR:0}

        prints(u'[%d] Processing feed %s' % (self.feed.id,
                                             self.feed.feed_url))

        # we check the etag and the modified time to save bandwith and
        # avoid bans
        try:
            self.fpf = feedparser.parse(self.feed.feed_url,
                                        agent=USER_AGENT,
                                        etag=self.feed.etag)
        except:
            prints('! ERROR: feed cannot be parsed')
            return FEED_ERRPARSE, ret_values

        if hasattr(self.fpf, 'status'):
            if self.options.verbose:
                prints(u'[%d] HTTP status %d: %s' % (self.feed.id,
                                                     self.fpf.status,
                                                     self.feed.feed_url))
            if self.fpf.status == 304:
                # this means the feed has not changed
                if self.options.verbose:
                    prints('[%d] Feed has not changed since ' \
                           'last check: %s' % (self.feed.id,
                                               self.feed.feed_url))
                return FEED_SAME, ret_values

            if self.fpf.status >= 400:
                # http error, ignore
                prints('[%d] !HTTP_ERROR! %d: %s' % (self.feed.id,
                                                     self.fpf.status,
                                                     self.feed.feed_url))
                return FEED_ERRHTTP, ret_values

        if hasattr(self.fpf, 'bozo') and self.fpf.bozo:
            prints('[%d] !BOZO! Feed is not well formed: %s' % (
                self.feed.id, self.feed.feed_url))

        # the feed has changed (or it is the first time we parse it)
        # saving the etag and last_modified fields
        self.feed.etag = self.fpf.get('etag', '')
        # some times this is None (it never should) *sigh*
        if self.feed.etag is None:
            self.feed.etag = ''

        try:
            self.feed.last_modified = mtime(self.fpf.modified)
        except:
            pass

        self.feed.title = self.fpf.feed.get('title', '')[0:254]
        self.feed.tagline = self.fpf.feed.get('tagline', '')
        self.feed.link = self.fpf.feed.get('link', '')
        self.feed.last_checked = datetime.datetime.now()

        if False and self.options.verbose:
            prints(u'[%d] Feed info for: %s\n' \
                   u'  title %s\n' \
                   u'  tagline %s\n' \
                   u'  link %s\n' \
                   u'  last_checked %s' % (
                self.feed.id, self.feed.feed_url, self.feed.title,
                self.feed.tagline, self.feed.link, self.feed.last_checked))

        guids = []
        for entry in self.fpf.entries:
            if entry.get('id', ''):
                guids.append(entry.get('id', ''))
            elif entry.title:
                guids.append(entry.title)
            elif entry.link:
                guids.append(entry.link)
        self.feed.save()
        if guids:
            postdict = dict([(post.guid, post)
              for post in models.Post.objects.filter(
                   feed=self.feed.id).filter(guid__in=guids)])
        else:
            postdict = {}

        for entry in self.fpf.entries:
            try:
                ret_entry = self.process_entry(entry, postdict)
            except:
                (etype, eobj, etb) = sys.exc_info()
                print '[%d] ! -------------------------' % (self.feed.id,)
                print traceback.format_exception(etype, eobj, etb)
                traceback.print_exception(etype, eobj, etb)
                print '[%d] ! -------------------------' % (self.feed.id,)
                ret_entry = ENTRY_ERR
            ret_values[ret_entry] += 1

        self.feed.save()

        return FEED_OK, ret_values

class Dispatcher:
    def __init__(self, options, num_threads):
        self.options = options
        self.entry_stats = {
            ENTRY_NEW:0,
            ENTRY_UPDATED:0,
            ENTRY_SAME:0,
            ENTRY_ERR:0}
        self.feed_stats = {
            FEED_OK:0,
            FEED_SAME:0,
            FEED_ERRPARSE:0,
            FEED_ERRHTTP:0,
            FEED_ERREXC:0}
        self.entry_trans = {
            ENTRY_NEW:'new',
            ENTRY_UPDATED:'updated',
            ENTRY_SAME:'same',
            ENTRY_ERR:'error'}
        self.feed_trans = {
            FEED_OK:'ok',
            FEED_SAME:'unchanged',
            FEED_ERRPARSE:'cant_parse',
            FEED_ERRHTTP:'http_error',
            FEED_ERREXC:'exception'}
        self.entry_keys = sorted(self.entry_trans.keys())
        self.feed_keys = sorted(self.feed_trans.keys())
        if threadpool:
            self.tpool = threadpool.ThreadPool(num_threads)
        else:
            self.tpool = None
        self.time_start = datetime.datetime.now()


    def add_job(self, feed):
        """ adds a feed processing job to the pool
        """
        if self.tpool:
            req = threadpool.WorkRequest(self.process_feed_wrapper,
                (feed,))
            self.tpool.putRequest(req)
        else:
            # no threadpool module, just run the job
            self.process_feed_wrapper(feed)

    def process_feed_wrapper(self, feed):
        """ wrapper for ProcessFeed
        """
        start_time = datetime.datetime.now()
        try:
            pfeed = ProcessFeed(feed, self.options)
            ret_feed, ret_entries = pfeed.process()
            del pfeed
        except:
            (etype, eobj, etb) = sys.exc_info()
            print '[%d] ! -------------------------' % (feed.id,)
            print traceback.format_exception(etype, eobj, etb)
            traceback.print_exception(etype, eobj, etb)
            print '[%d] ! -------------------------' % (feed.id,)
            ret_feed = FEED_ERREXC
            ret_entries = {}

        delta = datetime.datetime.now() - start_time
        if delta.seconds > SLOWFEED_WARNING:
            comment = u' (SLOW FEED!)'
        else:
            comment = u''
        prints(u'[%d] Processed %s in %s [%s] [%s]%s' % (
            feed.id, feed.feed_url, unicode(delta),
            self.feed_trans[ret_feed],
            u' '.join(u'%s=%d' % (self.entry_trans[key],
                      ret_entries[key]) for key in self.entry_keys),
            comment))

        self.feed_stats[ret_feed] += 1
        for key, val in ret_entries.items():
            self.entry_stats[key] += val

        return ret_feed, ret_entries

    def poll(self):
        """ polls the active threads
        """
        if not self.tpool:
            # no thread pool, nothing to poll
            return
        while True:
            try:
                time.sleep(0.2)
                self.tpool.poll()
            except KeyboardInterrupt:
                prints('! Cancelled by user')
                break
            except threadpool.NoResultsPending:
                prints(u'* DONE in %s\n* Feeds: %s\n* Entries: %s' % (
                    unicode(datetime.datetime.now() - self.time_start),
                    u' '.join(u'%s=%d' % (self.feed_trans[key],
                              self.feed_stats[key])
                              for key in self.feed_keys),
                    u' '.join(u'%s=%d' % (self.entry_trans[key],
                              self.entry_stats[key])
                              for key in self.entry_keys)
                    ))
                break


def main():
    """ Main function. Nothing to see here. Move along.
    """
    parser = optparse.OptionParser(usage='%prog [options]',
                                   version=USER_AGENT)
    parser.add_option('--settings',
      help='Python path to settings module. If this isn\'t provided, ' \
           'the DJANGO_SETTINGS_MODULE enviroment variable will be used.')
    parser.add_option('-f', '--feed', action='append', type='int',
      help='A feed id to be updated. This option can be given multiple ' \
           'times to update several feeds at the same time ' \
           '(-f 1 -f 4 -f 7).')
    parser.add_option('-s', '--site', type='int',
      help='A site id to update.')
    parser.add_option('-v', '--verbose', action='store_true',
      dest='verbose', default=False, help='Verbose output.')
    parser.add_option('-t', '--timeout', type='int', default=10,
      help='Wait timeout in seconds when connecting to feeds.')
    parser.add_option('-w', '--workerthreads', type='int', default=10,
      help='Worker threads that will fetch feeds in parallel.')
    options = parser.parse_args()[0]
    if options.settings:
        os.environ["DJANGO_SETTINGS_MODULE"] = options.settings


    from calibre.www.apps.feedjack import models, fjcache

    # settting socket timeout (default= 10 seconds)
    socket.setdefaulttimeout(options.timeout)

    # our job dispatcher
    disp = Dispatcher(options, options.workerthreads)

    prints('* BEGIN: %s' % (unicode(datetime.datetime.now()),))

    if options.feed:
        feeds = models.Feed.objects.filter(id__in=options.feed)
        known_ids = []
        for feed in feeds:
            known_ids.append(feed.id)
            disp.add_job(feed)
        for feed in options.feed:
            if feed not in known_ids:
                prints('! Unknown feed id: %d' % (feed,))
    elif options.site:
        try:
            site = models.Site.objects.get(pk=int(options.site))
        except models.Site.DoesNotExist:
            site = None
            prints('! Unknown site id: %d' % (options.site,))
        if site:
            feeds = [sub.feed for sub in site.subscriber_set.all()]
            for feed in feeds:
                disp.add_job(feed)
    else:
        for feed in models.Feed.objects.filter(is_active=True):
            disp.add_job(feed)

    disp.poll()

    # removing the cached data in all sites, this will only work with the
    # memcached, db and file backends
    [fjcache.cache_delsite(site.id) for site in models.Site.objects.all()]

    if threadpool:
        tcom = u'%d threads' % (options.workerthreads,)
    else:
        tcom = u'no threadpool module available, no parallel fetching'

    prints('* END: %s (%s)' % (unicode(datetime.datetime.now()), tcom))

if __name__ == '__main__':
    main()

