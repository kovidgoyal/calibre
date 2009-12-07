.. include:: global.rst

.. _news_recipe:

API Documentation for recipes
===============================

.. module:: calibre.web.feeds.news
    :synopsis: Defines various abstract base classes that can be subclassed to create powerful news fetching recipes.

Defines various abstract base classes that can be subclassed to create powerful news fetching recipes. The useful
subclasses are:

.. contents::
    :depth: 1
    :local:

BasicNewsRecipe
-----------------

.. class:: BasicNewsRecipe

    Abstract base class that contains a number of members and methods to customize the fetching of contents in your recipes. All
    recipes must inherit from this class or a subclass of it.

    The members and methods are organized as follows:

.. contents::
    :depth: 1
    :local:

    

Customizing e-book download
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automember:: BasicNewsRecipe.title

.. automember:: BasicNewsRecipe.description

.. automember:: BasicNewsRecipe.__author__

.. automember:: BasicNewsRecipe.max_articles_per_feed

.. automember:: BasicNewsRecipe.oldest_article

.. automember:: BasicNewsRecipe.recursions

.. automember:: BasicNewsRecipe.delay

.. automember:: BasicNewsRecipe.simultaneous_downloads

.. automember:: BasicNewsRecipe.timeout

.. automember:: BasicNewsRecipe.timefmt

.. automember:: BasicNewsRecipe.conversion_options

.. automember:: BasicNewsRecipe.feeds

.. automember:: BasicNewsRecipe.no_stylesheets

.. automember:: BasicNewsRecipe.encoding

.. automethod:: BasicNewsRecipe.get_browser

.. automethod:: BasicNewsRecipe.get_cover_url

.. automethod:: BasicNewsRecipe.get_feeds
    
.. automethod:: BasicNewsRecipe.parse_index



Customizing feed parsing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automember:: BasicNewsRecipe.summary_length

.. automember:: BasicNewsRecipe.use_embedded_content

.. automethod:: BasicNewsRecipe.get_article_url

.. automethod:: BasicNewsRecipe.print_version

.. automethod:: BasicNewsRecipe.parse_feeds


Pre/post processing of downloaded HTML
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automember:: BasicNewsRecipe.extra_css

.. automember:: BasicNewsRecipe.match_regexps

.. automember:: BasicNewsRecipe.filter_regexps

.. automember:: BasicNewsRecipe.remove_tags

.. automember:: BasicNewsRecipe.remove_tags_after

.. automember:: BasicNewsRecipe.remove_tags_before

.. automember:: BasicNewsRecipe.remove_attributes

.. automember:: BasicNewsRecipe.keep_only_tags

.. automember:: BasicNewsRecipe.preprocess_regexps

.. automember:: BasicNewsRecipe.template_css

.. automember:: BasicNewsRecipe.remove_javascript

.. automethod:: BasicNewsRecipe.preprocess_html

.. automethod:: BasicNewsRecipe.postprocess_html


    

Convenience methods
~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: BasicNewsRecipe.cleanup

.. automethod:: BasicNewsRecipe.index_to_soup

.. automethod:: BasicNewsRecipe.sort_index_by

.. automethod:: BasicNewsRecipe.tag_to_string


Miscellaneous
~~~~~~~~~~~~~~~~~~

.. automember:: BasicNewsRecipe.requires_version


CustomIndexRecipe
---------------------

.. class:: CustomIndexRecipe

    This class is useful for getting content from websites that don't follow the "multiple articles in several feeds" content model. 

.. automethod:: CustomIndexRecipe.custom_index


