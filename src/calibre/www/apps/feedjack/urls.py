# -*- coding: utf-8 -*-

"""
feedjack
Gustavo Picón
urls.py
"""

from django.conf.urls.defaults import patterns
from django.views.generic.simple import redirect_to

from calibre.www.apps.feedjack import views



urlpatterns = patterns('',
    (r'^rss20.xml$', redirect_to,
      {'url':'/feed/rss/'}),
    (r'^feed/$', redirect_to,
      {'url':'/feed/atom/'}),
    (r'^feed/rss/$', views.rssfeed),
    (r'^feed/atom/$', views.atomfeed),

    (r'^feed/user/(?P<user>\d+)/tag/(?P<tag>.*)/$', redirect_to,
      {'url':'/feed/atom/user/%(user)s/tag/%(tag)s/'}),
    (r'^feed/user/(?P<user>\d+)/$', redirect_to,
      {'url':'/feed/atom/user/%(user)s/'}),
    (r'^feed/tag/(?P<tag>.*)/$', redirect_to,
      {'url':'/feed/atom/tag/%(tag)s/'}),

    (r'^feed/atom/user/(?P<user>\d+)/tag/(?P<tag>.*)/$', views.atomfeed),
    (r'^feed/atom/user/(?P<user>\d+)/$', views.atomfeed),
    (r'^feed/atom/tag/(?P<tag>.*)/$', views.atomfeed),
    (r'^feed/rss/user/(?P<user>\d+)/tag/(?P<tag>.*)/$', views.rssfeed),
    (r'^feed/rss/user/(?P<user>\d+)/$', views.rssfeed),
    (r'^feed/rss/tag/(?P<tag>.*)/$', views.rssfeed),

    (r'^user/(?P<user>\d+)/tag/(?P<tag>.*)/$', views.mainview),
    (r'^user/(?P<user>\d+)/$', views.mainview),
    (r'^tag/(?P<tag>.*)/$', views.mainview),

    (r'^opml/$', views.opml),
    (r'^foaf/$', views.foaf),
    (r'^$', views.mainview),
)

#~
