from django.contrib import admin
from calibre.www.apps.tagging.models import Tag, TaggedItem

admin.site.register(TaggedItem)
admin.site.register(Tag)
