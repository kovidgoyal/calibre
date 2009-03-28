from django.db.models import get_model
from django.template import Library, Node, TemplateSyntaxError, Variable, resolve_variable
from django.utils.translation import ugettext as _

from tagging.models import Tag, TaggedItem
from tagging.utils import LINEAR, LOGARITHMIC

register = Library()

class TagsForModelNode(Node):
    def __init__(self, model, context_var, counts):
        self.model = model
        self.context_var = context_var
        self.counts = counts

    def render(self, context):
        model = get_model(*self.model.split('.'))
        if model is None:
            raise TemplateSyntaxError(_('tags_for_model tag was given an invalid model: %s') % self.model)
        context[self.context_var] = Tag.objects.usage_for_model(model, counts=self.counts)
        return ''

class TagCloudForModelNode(Node):
    def __init__(self, model, context_var, **kwargs):
        self.model = model
        self.context_var = context_var
        self.kwargs = kwargs

    def render(self, context):
        model = get_model(*self.model.split('.'))
        if model is None:
            raise TemplateSyntaxError(_('tag_cloud_for_model tag was given an invalid model: %s') % self.model)
        context[self.context_var] = \
            Tag.objects.cloud_for_model(model, **self.kwargs)
        return ''

class TagsForObjectNode(Node):
    def __init__(self, obj, context_var):
        self.obj = Variable(obj)
        self.context_var = context_var

    def render(self, context):
        context[self.context_var] = \
            Tag.objects.get_for_object(self.obj.resolve(context))
        return ''

class TaggedObjectsNode(Node):
    def __init__(self, tag, model, context_var):
        self.tag = Variable(tag)
        self.context_var = context_var
        self.model = model

    def render(self, context):
        model = get_model(*self.model.split('.'))
        if model is None:
            raise TemplateSyntaxError(_('tagged_objects tag was given an invalid model: %s') % self.model)
        context[self.context_var] = \
            TaggedItem.objects.get_by_model(model, self.tag.resolve(context))
        return ''

def do_tags_for_model(parser, token):
    """
    Retrieves a list of ``Tag`` objects associated with a given model
    and stores them in a context variable.

    Usage::

       {% tags_for_model [model] as [varname] %}

    The model is specified in ``[appname].[modelname]`` format.

    Extended usage::

       {% tags_for_model [model] as [varname] with counts %}

    If specified - by providing extra ``with counts`` arguments - adds
    a ``count`` attribute to each tag containing the number of
    instances of the given model which have been tagged with it.

    Examples::

       {% tags_for_model products.Widget as widget_tags %}
       {% tags_for_model products.Widget as widget_tags with counts %}

    """
    bits = token.contents.split()
    len_bits = len(bits)
    if len_bits not in (4, 6):
        raise TemplateSyntaxError(_('%s tag requires either three or five arguments') % bits[0])
    if bits[2] != 'as':
        raise TemplateSyntaxError(_("second argument to %s tag must be 'as'") % bits[0])
    if len_bits == 6:
        if bits[4] != 'with':
            raise TemplateSyntaxError(_("if given, fourth argument to %s tag must be 'with'") % bits[0])
        if bits[5] != 'counts':
            raise TemplateSyntaxError(_("if given, fifth argument to %s tag must be 'counts'") % bits[0])
    if len_bits == 4:
        return TagsForModelNode(bits[1], bits[3], counts=False)
    else:
        return TagsForModelNode(bits[1], bits[3], counts=True)

def do_tag_cloud_for_model(parser, token):
    """
    Retrieves a list of ``Tag`` objects for a given model, with tag
    cloud attributes set, and stores them in a context variable.

    Usage::

       {% tag_cloud_for_model [model] as [varname] %}

    The model is specified in ``[appname].[modelname]`` format.

    Extended usage::

       {% tag_cloud_for_model [model] as [varname] with [options] %}

    Extra options can be provided after an optional ``with`` argument,
    with each option being specified in ``[name]=[value]`` format. Valid
    extra options are:

       ``steps``
          Integer. Defines the range of font sizes.

       ``min_count``
          Integer. Defines the minimum number of times a tag must have
          been used to appear in the cloud.

       ``distribution``
          One of ``linear`` or ``log``. Defines the font-size
          distribution algorithm to use when generating the tag cloud.

    Examples::

       {% tag_cloud_for_model products.Widget as widget_tags %}
       {% tag_cloud_for_model products.Widget as widget_tags with steps=9 min_count=3 distribution=log %}

    """
    bits = token.contents.split()
    len_bits = len(bits)
    if len_bits != 4 and len_bits not in range(6, 9):
        raise TemplateSyntaxError(_('%s tag requires either three or between five and seven arguments') % bits[0])
    if bits[2] != 'as':
        raise TemplateSyntaxError(_("second argument to %s tag must be 'as'") % bits[0])
    kwargs = {}
    if len_bits > 5:
        if bits[4] != 'with':
            raise TemplateSyntaxError(_("if given, fourth argument to %s tag must be 'with'") % bits[0])
        for i in range(5, len_bits):
            try:
                name, value = bits[i].split('=')
                if name == 'steps' or name == 'min_count':
                    try:
                        kwargs[str(name)] = int(value)
                    except ValueError:
                        raise TemplateSyntaxError(_("%(tag)s tag's '%(option)s' option was not a valid integer: '%(value)s'") % {
                            'tag': bits[0],
                            'option': name,
                            'value': value,
                        })
                elif name == 'distribution':
                    if value in ['linear', 'log']:
                        kwargs[str(name)] = {'linear': LINEAR, 'log': LOGARITHMIC}[value]
                    else:
                        raise TemplateSyntaxError(_("%(tag)s tag's '%(option)s' option was not a valid choice: '%(value)s'") % {
                            'tag': bits[0],
                            'option': name,
                            'value': value,
                        })
                else:
                    raise TemplateSyntaxError(_("%(tag)s tag was given an invalid option: '%(option)s'") % {
                        'tag': bits[0],
                        'option': name,
                    })
            except ValueError:
                raise TemplateSyntaxError(_("%(tag)s tag was given a badly formatted option: '%(option)s'") % {
                    'tag': bits[0],
                    'option': bits[i],
                })
    return TagCloudForModelNode(bits[1], bits[3], **kwargs)

def do_tags_for_object(parser, token):
    """
    Retrieves a list of ``Tag`` objects associated with an object and
    stores them in a context variable.

    Usage::

       {% tags_for_object [object] as [varname] %}

    Example::

        {% tags_for_object foo_object as tag_list %}
    """
    bits = token.contents.split()
    if len(bits) != 4:
        raise TemplateSyntaxError(_('%s tag requires exactly three arguments') % bits[0])
    if bits[2] != 'as':
        raise TemplateSyntaxError(_("second argument to %s tag must be 'as'") % bits[0])
    return TagsForObjectNode(bits[1], bits[3])

def do_tagged_objects(parser, token):
    """
    Retrieves a list of instances of a given model which are tagged with
    a given ``Tag`` and stores them in a context variable.

    Usage::

       {% tagged_objects [tag] in [model] as [varname] %}

    The model is specified in ``[appname].[modelname]`` format.

    The tag must be an instance of a ``Tag``, not the name of a tag.

    Example::

        {% tagged_objects comedy_tag in tv.Show as comedies %}

    """
    bits = token.contents.split()
    if len(bits) != 6:
        raise TemplateSyntaxError(_('%s tag requires exactly five arguments') % bits[0])
    if bits[2] != 'in':
        raise TemplateSyntaxError(_("second argument to %s tag must be 'in'") % bits[0])
    if bits[4] != 'as':
        raise TemplateSyntaxError(_("fourth argument to %s tag must be 'as'") % bits[0])
    return TaggedObjectsNode(bits[1], bits[3], bits[5])

register.tag('tags_for_model', do_tags_for_model)
register.tag('tag_cloud_for_model', do_tag_cloud_for_model)
register.tag('tags_for_object', do_tags_for_object)
register.tag('tagged_objects', do_tagged_objects)
