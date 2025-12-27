import requests
from typing import List, Optional
from loguru import logger
from datetime import datetime
from .config import settings

class ReadwiseClient:
    API_URL = "https://readwise.io/api/v3/save/"

    def __init__(self):
        self.headers = {
            "Authorization": f"Token {settings.READWISE_TOKEN}",
            "Content-Type": "application/json"
        }

    def save_summary(self, 
                     url: str, 
                     title: str, 
                     summary_html: str, 
                     tags: List[str] = None,
                     author: str = None,
                     public_url: str = None) -> bool:
        """
        Save the summary to Readwise Reader.
        """
        if not settings.READWISE_TOKEN:
            logger.warning("Readwise Token not set. Skipping sync.")
            return False

        payload = {
            "url": url,
            "title": title,
            "html": summary_html, # Provide the summary as the content
            "tags": tags or [],
            "author": author,
            "saved_using": "RaindropAutoAgent"
        }
        
        # If published_date is needed, it can be added to payload['published_date'] (ISO 8601)
        
        try:
            response = requests.post(self.API_URL, headers=self.headers, json=payload)
            response.raise_for_status()
            logger.info(f"Successfully saved to Readwise Reader: {title}")
            return True
        except Exception as e:
            logger.error(f"Readwise Sync Failed: {e}")
            # If 400, maybe log response
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Readwise Response: {e.response.text}")
            return False

readwise_client = ReadwiseClient()
