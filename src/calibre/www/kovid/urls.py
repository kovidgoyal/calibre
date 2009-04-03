from django.conf.urls.defaults import patterns, include, handler404, handler500
from django.conf import settings

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',

    (r'^admin/(.*)', admin.site.root),

    (r'^comments/', include('django.contrib.comments.urls')),
    (r'', include('calibre.www.apps.blog.urls')),



)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^site_media/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.MEDIA_ROOT}),
    )



