from typing import Any, Dict, List

import requests


class PubmedSearchAgent:
    """Search the free NCBI PubMed E-utilities API."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, email: str = ""):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Multi-Agent-Medical-Assistant/1.0 (PubMed research client)"
        })
        self.email = email

    def search_pubmed(self, query: str, retmax: int = 5) -> str:
        """Return compact, cited PubMed records for *query*."""
        records = self.search_pubmed_records(query, retmax=retmax)
        if isinstance(records, str):
            return records
        return "\n\n".join(
            "Title: {title}\nJournal: {journal}\nPublication date: {publication_date}\n"
            "PubMed URL: {url}".format(**record)
            for record in records
        ) or "No relevant PubMed articles found."

    def search_pubmed_records(self, query: str, retmax: int = 5):
        """Return structured PubMed citation records for *query*."""
        query = (query or "").strip().strip("\"'")
        if not query:
            return "No PubMed query was provided."

        search_params: Dict[str, Any] = {
            "db": "pubmed", "term": query, "retmode": "json",
            "retmax": max(1, min(int(retmax), 20)),
        }
        if self.email:
            search_params["email"] = self.email

        try:
            response = self.session.get(
                f"{self.BASE_URL}/esearch.fcgi", params=search_params, timeout=15
            )
            response.raise_for_status()
            article_ids = response.json().get("esearchresult", {}).get("idlist", [])
            if not article_ids:
                return []

            summary_params: Dict[str, Any] = {
                "db": "pubmed", "id": ",".join(article_ids), "retmode": "json"
            }
            if self.email:
                summary_params["email"] = self.email
            summary_response = self.session.get(
                f"{self.BASE_URL}/esummary.fcgi", params=summary_params, timeout=15
            )
            summary_response.raise_for_status()
            summaries: Dict[str, Any] = summary_response.json().get("result", {})

            structured_records: List[Dict[str, str]] = []
            for article_id in article_ids:
                item = summaries.get(article_id, {})
                structured_records.append(
                    {
                        "title": item.get("title", "Untitled article"),
                        "journal": item.get("fulljournalname") or item.get("source", ""),
                        "publication_date": item.get("pubdate", ""),
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{article_id}/",
                        "source_type": "PubMed",
                    }
                )
            return structured_records
        except Exception as e:
            return f"Error retrieving PubMed articles: {e}"
