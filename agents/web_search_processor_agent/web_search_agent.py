from .pubmed_search import PubmedSearchAgent

class WebSearchAgent:
    """
    Agent responsible for retrieving real-time medical information from web sources.
    """
    
    def __init__(self, config):
        self.pubmed_search_agent = PubmedSearchAgent(
            email=getattr(config.web_search, "pubmed_email", "")
        )
    
    def search(self, query: str) -> str:
        """
        Search PubMed for biomedical literature.
        """
        # print(f"[WebSearchAgent] Searching for: {query}")
        
        pubmed_results = self.pubmed_search_agent.search_pubmed(query=query)
        return f"PubMed Results:\n{pubmed_results}\n"

    def search_with_sources(self, query: str):
        """Return formatted PubMed evidence and structured citations."""
        records = self.pubmed_search_agent.search_pubmed_records(query=query)
        if isinstance(records, str):
            return f"PubMed Results:\n{records}\n", []
        evidence = "\n\n".join(
            "Title: {title}\nJournal: {journal}\nPublication date: {publication_date}\n"
            "PubMed URL: {url}".format(**record)
            for record in records
        ) or "No relevant PubMed articles found."
        return f"PubMed Results:\n{evidence}\n", records
