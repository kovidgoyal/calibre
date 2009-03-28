from django.db import models
from django.contrib.contenttypes.models import ContentType


class InlineType(models.Model):
    """ InlineType model """
    title           = models.CharField(max_length=200)
    content_type    = models.ForeignKey(ContentType)

    class Meta:
        db_table = 'inline_types'

    class Admin:
        pass

    def __unicode__(self):
        return self.title