from django.utils.translation import ugettext as _

from tagging.managers import ModelTaggedItemManager, TagDescriptor

VERSION = (0, 3, 'pre')

class AlreadyRegistered(Exception):
    """
    An attempt was made to register a model more than once.
    """
    pass

registry = []

def register(model, tag_descriptor_attr='tags',
             tagged_item_manager_attr='tagged'):
    """
    Sets the given model class up for working with tags.
    """
    if model in registry:
        raise AlreadyRegistered(
            _('The model %s has already been registered.') % model.__name__)
    registry.append(model)

    # Add tag descriptor
    setattr(model, tag_descriptor_attr, TagDescriptor())

    # Add custom manager
    ModelTaggedItemManager().contribute_to_class(model,
                                                 tagged_item_manager_attr)
