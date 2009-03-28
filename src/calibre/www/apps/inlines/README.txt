==============================================
Django Basic Inlines
http://code.google.com/p/django-basic-apps/
==============================================

A simple book library application for Django projects.

To install this app, simply create a folder somewhere in
your PYTHONPATH named 'basic' and place the 'inlines'
app inside. Then add 'basic.inlines' to your projects
INSTALLED_APPS list in your settings.py file.

Inlines is a template filter that can be used in
conjunction with inline markup to insert content objects
into other pieces of content. An example would be inserting
a photo into a blog post body. 

An example of the markup is:
  <inline type="media.photo" id="1" />

The type attribute is app_name.model_name and the id is
the object id. Pretty simple. 

In your template you would say:
  {% load inlines %}
  
  {{ post.body|render_inlines }}