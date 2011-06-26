from description import Description
from query import Query
from results import Results

class Client:

    """This is the class you'll probably want to be using. You simply
    pass the constructor the url for the service description file and
    issue a search and get back results as an iterable Results object.

    The neat thing about a Results object is that it will seamlessly
    handle fetching more results from the opensearch server when it can...
    so you just need to iterate and can let the paging be taken care of 
    for you.

    from opensearch import Client
    client = Client(description_url)
    results = client.search("computer")
    for result in results:
        print result.title
    """

    def __init__(self, url, agent="python-opensearch <https://github.com/edsu/opensearch>"):
        self.agent = agent
        self.description = Description(url, self.agent)

    def search(self, search_terms, page_size=25):
        """Perform a search and get back a results object
        """
        url = self.description.get_best_template()
        query = Query(url)

        # set up initial values
        query.searchTerms = search_terms
        query.count = page_size

        # run the results
        return Results(query, agent=self.agent)

