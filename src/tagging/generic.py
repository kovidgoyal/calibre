from django.contrib.contenttypes.models import ContentType

def fetch_content_objects(tagged_items, select_related_for=None):
    """
    Retrieves ``ContentType`` and content objects for the given list of
    ``TaggedItems``, grouping the retrieval of content objects by model
    type to reduce the number of queries executed.

    This results in ``number_of_content_types + 1`` queries rather than
    the ``number_of_tagged_items * 2`` queries you'd get by iterating
    over the list and accessing each item's ``object`` attribute.

    A ``select_related_for`` argument can be used to specify a list of
    of model names (corresponding to the ``model`` field of a
    ``ContentType``) for which ``select_related`` should be used when
    retrieving model instances.
    """
    if select_related_for is None: select_related_for = []

    # Group content object pks by their content type pks
    objects = {}
    for item in tagged_items:
        objects.setdefault(item.content_type_id, []).append(item.object_id)

    # Retrieve content types and content objects in bulk
    content_types = ContentType._default_manager.in_bulk(objects.keys())
    for content_type_pk, object_pks in objects.iteritems():
        model = content_types[content_type_pk].model_class()
        if content_types[content_type_pk].model in select_related_for:
            objects[content_type_pk] = model._default_manager.select_related().in_bulk(object_pks)
        else:
            objects[content_type_pk] = model._default_manager.in_bulk(object_pks)

    # Set content types and content objects in the appropriate cache
    # attributes, so accessing the 'content_type' and 'object'
    # attributes on each tagged item won't result in further database
    # hits.
    for item in tagged_items:
        item._object_cache = objects[item.content_type_id][item.object_id]
        item._content_type_cache = content_types[item.content_type_id]
