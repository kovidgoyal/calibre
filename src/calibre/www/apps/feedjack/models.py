# -*- coding: utf-8 -*-
# pylint: disable-msg=W0232, R0903, W0131

"""
feedjack
Gustavo Picón
models.py
"""

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import smart_unicode

from calibre.www.apps.feedjack import fjcache

SITE_ORDERBY_CHOICES = (
    (1, _('Date published.')),
    (2, _('Date the post was first obtained.'))
)

class Link(models.Model):
    name = models.CharField(_('name'), max_length=100, unique=True)
    link = models.URLField(_('link'), verify_exists=True)

    class Meta:
        verbose_name = _('link')
        verbose_name_plural = _('links')

    class Admin:
        pass

    def __unicode__(self):
        return u'%s (%s)' % (self.name, self.link)



class Site(models.Model):
    name = models.CharField(_('name'), max_length=100)
    url = models.CharField(_('url'),
      max_length=100,
      unique=True,
      help_text=u'%s: %s, %s' % (smart_unicode(_('Example')),
        u'http://www.planetexample.com',
        u'http://www.planetexample.com:8000/foo'))
    title = models.CharField(_('title'), max_length=200)
    description = models.TextField(_('description'))
    welcome = models.TextField(_('welcome'), null=True, blank=True)
    greets = models.TextField(_('greets'), null=True, blank=True)

    default_site = models.BooleanField(_('default site'), default=False)
    posts_per_page = models.IntegerField(_('posts per page'), default=20)
    order_posts_by = models.IntegerField(_('order posts by'), default=1,
        choices=SITE_ORDERBY_CHOICES)
    tagcloud_levels = models.IntegerField(_('tagcloud level'), default=5)
    show_tagcloud = models.BooleanField(_('show tagcloud'), default=True)

    use_internal_cache = models.BooleanField(_('use internal cache'), default=True)
    cache_duration = models.IntegerField(_('cache duration'), default=60*60*24,
        help_text=_('Duration in seconds of the cached pages and data.') )

    links = models.ManyToManyField(Link, verbose_name=_('links'),
      null=True, blank=True)
    template = models.CharField(_('template'), max_length=100, null=True,
      blank=True,
      help_text=_('This template must be a directory in your feedjack '
        'templates directory. Leave blank to use the default template.') )

    class Meta:
        verbose_name = _('site')
        verbose_name_plural = _('sites')
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    def save(self):
        if not self.template:
            self.template = 'default'
        # there must be only ONE default site
        defs = Site.objects.filter(default_site=True)
        if not defs:
            self.default_site = True
        elif self.default_site:
            for tdef in defs:
                if tdef.id != self.id:
                    tdef.default_site = False
                    tdef.save()
        self.url = self.url.rstrip('/')
        fjcache.hostcache_set({})
        super(Site, self).save()




class Feed(models.Model):
    feed_url = models.URLField(_('feed url'), unique=True)

    name = models.CharField(_('name'), max_length=100)
    shortname = models.CharField(_('shortname'), max_length=50)
    is_active = models.BooleanField(_('is active'), default=True,
        help_text=_('If disabled, this feed will not be further updated.') )

    title = models.CharField(_('title'), max_length=200, blank=True)
    tagline = models.TextField(_('tagline'), blank=True)
    link = models.URLField(_('link'), blank=True)

    # http://feedparser.org/docs/http-etag.html
    etag = models.CharField(_('etag'), max_length=50, blank=True)
    last_modified = models.DateTimeField(_('last modified'), null=True, blank=True)
    last_checked = models.DateTimeField(_('last checked'), null=True, blank=True)

    class Meta:
        verbose_name = _('feed')
        verbose_name_plural = _('feeds')
        ordering = ('name', 'feed_url',)

    def __unicode__(self):
        return u'%s (%s)' % (self.name, self.feed_url)

    def save(self):
        super(Feed, self).save()



class Tag(models.Model):
    name = models.CharField(_('name'), max_length=50, unique=True)

    class Meta:
        verbose_name = _('tag')
        verbose_name_plural = _('tags')
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    def save(self):
        super(Tag, self).save()

class Post(models.Model):
    feed = models.ForeignKey(Feed, verbose_name=_('feed'), null=False, blank=False)
    title = models.CharField(_('title'), max_length=255)
    link = models.URLField(_('link'), )
    content = models.TextField(_('content'), blank=True)
    date_modified = models.DateTimeField(_('date modified'), null=True, blank=True)
    guid = models.CharField(_('guid'), max_length=200, db_index=True)
    author = models.CharField(_('author'), max_length=50, blank=True)
    author_email = models.EmailField(_('author email'), blank=True)
    comments = models.URLField(_('comments'), blank=True)
    tags = models.ManyToManyField(Tag, verbose_name=_('tags'))
    date_created = models.DateField(_('date created'), auto_now_add=True)

    class Meta:
        verbose_name = _('post')
        verbose_name_plural = _('posts')
        ordering = ('-date_modified',)
        unique_together = (('feed', 'guid'),)

    def __unicode__(self):
        return self.title

    def save(self):
        super(Post, self).save()

    def get_absolute_url(self):
        return self.link



class Subscriber(models.Model):
    site = models.ForeignKey(Site, verbose_name=_('site') )
    feed = models.ForeignKey(Feed, verbose_name=_('feed') )

    name = models.CharField(_('name'), max_length=100, null=True, blank=True,
        help_text=_('Keep blank to use the Feed\'s original name.') )
    shortname = models.CharField(_('shortname'), max_length=50, null=True,
      blank=True,
      help_text=_('Keep blank to use the Feed\'s original shortname.') )
    is_active = models.BooleanField(_('is active'), default=True,
        help_text=_('If disabled, this subscriber will not appear in the site or '
        'in the site\'s feed.') )

    class Meta:
        verbose_name = _('subscriber')
        verbose_name_plural = _('subscribers')
        ordering = ('site', 'name', 'feed')
        unique_together = (('site', 'feed'),)

    def __unicode__(self):
        return u'%s in %s' % (self.feed, self.site)

    def get_cloud(self):
        from calibre.www.apps.feedjack import fjcloud
        return fjcloud.getcloud(self.site, self.feed.id)

    def save(self):
        if not self.name:
            self.name = self.feed.name
        if not self.shortname:
            self.shortname = self.feed.shortname
        super(Subscriber, self).save()


