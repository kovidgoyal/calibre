# -*- coding: utf-8 -*-

"""
feedjack
Gustavo Picón
fjcloud.py
"""

import math

from calibre.www.apps.feedjack import fjlib, fjcache

def getsteps(levels, tagmax):
    """ Returns a list with the max number of posts per "tagcloud level"
    """
    ntw = levels
    if ntw < 2:
        ntw = 2

    steps = [(stp, 1 + (stp * int(math.ceil(tagmax * 1.0 / ntw - 1))))
              for stp in range(ntw)]
    # just to be sure~
    steps[-1] = (steps[-1][0], tagmax+1)
    return steps

def build(site, tagdata):
    """ Returns the tag cloud for a list of tags.
    """

    tagdata.sort()

    # we get the most popular tag to calculate the tags' weigth
    tagmax = 0
    for tagname, tagcount in tagdata:
        if tagcount > tagmax:
            tagmax = tagcount
    steps = getsteps(site.tagcloud_levels, tagmax)

    tags = []
    for tagname, tagcount in tagdata:
        weight = [twt[0] \
          for twt in steps if twt[1] >= tagcount and twt[1] > 0][0]+1
        tags.append({'tagname':tagname, 'count':tagcount, 'weight':weight})
    return tags

def cloudata(site):
    """ Returns a dictionary with all the tag clouds related to a site.
    """

    tagdata = fjlib.getquery("""
          SELECT feedjack_post.feed_id, feedjack_tag.name, COUNT(*)
          FROM feedjack_post, feedjack_subscriber, feedjack_tag,
          feedjack_post_tags
          WHERE feedjack_post.feed_id=feedjack_subscriber.feed_id AND
          feedjack_post_tags.tag_id=feedjack_tag.id AND
          feedjack_post_tags.post_id=feedjack_post.id AND
          feedjack_subscriber.site_id=%d
          GROUP BY feedjack_post.feed_id, feedjack_tag.name
          ORDER BY feedjack_post.feed_id, feedjack_tag.name""" % site.id)
    tagdict = {}
    globaldict = {}
    cloudict = {}
    for feed_id, tagname, tagcount in tagdata:
        if feed_id not in tagdict:
            tagdict[feed_id] = []
        tagdict[feed_id].append((tagname, tagcount))
        try:
            globaldict[tagname] += tagcount
        except KeyError:
            globaldict[tagname] = tagcount
    tagdict[0] = globaldict.items()
    for key, val in tagdict.items():
        cloudict[key] = build(site, val)
    return cloudict

def getcloud(site, feed_id=None):
    """ Returns the tag cloud for a site or a site's subscriber.
    """

    cloudict = fjcache.cache_get(site.id, 'tagclouds')
    if not cloudict:
        cloudict = cloudata(site)
        fjcache.cache_set(site, 'tagclouds', cloudict)

    # A subscriber's tag cloud has been requested.
    if feed_id:
        feed_id = int(feed_id)
        if feed_id in cloudict:
            return cloudict[feed_id]
        return []
    # The site tagcloud has been requested.
    return cloudict[0]

