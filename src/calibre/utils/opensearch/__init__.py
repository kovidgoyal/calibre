'''
Based on the OpenSearch Python module by Ed Summers <ehs@pobox.com> from
https://github.com/edsu/opensearch .

This module is heavily modified and does not implement all the features from
the original. The ability for the module to perform a search and retrieve
search results has been removed. The original module used a modified version
of the Universal feed parser from http://feedparser.org/ . The use of
FeedPaser made getting search results very slow. There is also a bug in the
modified FeedParser that causes the system to run out of file descriptors.

Instead of fixing the modified feed parser it was decided to remove it and
manually parse the feeds in a set of type specific classes. This is much
faster and as we know in advance the feed format is simpler than using
FeedParser. Also, replacing the modified FeedParser with the newest version
of FeedParser caused some feeds to be parsed incorrectly and result in a loss
of data.

The module was also rewritten to use lxml instead of MiniDom.


Usage:

description = Description(open_search_url)
url_template = description.get_best_template()
if not url_template:
    return
query = Query(url_template)

# set up initial values.
query.searchTerms = search_terms
# Note the count is ignored by some feeds.
query.count = max_results

search_url = oquery.url()

'''
