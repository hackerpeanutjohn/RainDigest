import requests
from typing import List, Dict, Any
from urllib.parse import urlparse
from loguru import logger
from .config import settings

class RaindropClient:
    BASE_URL = "https://api.raindrop.io/rest/v1"

    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.RAINDROP_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": settings.APP_USER_AGENT
        }

    def check_connection(self):
        """
        Verify token.
        OLD behavior: Just checks connection.
        """
        # This is kept for backward compat if needed, but we will mostly use get_roots.
        try:
            url = f"{self.BASE_URL}/user/stats"
            requests.get(url, headers=self.headers).raise_for_status()
            return True
        except:
            return False

    def get_collections(self) -> Dict[int, str]:
        """
        Get ALL collections (Roots + Nested).
        Returns Dict[id, title]
        """
        cols = {}
        try:
            # 1. Get Roots
            url_roots = f"{self.BASE_URL}/collections"
            resp_roots = requests.get(url_roots, headers=self.headers)
            resp_roots.raise_for_status()
            for item in resp_roots.json().get('items', []):
                cols[item['_id']] = item['title']

            # 2. Get Children (All nested)
            url_children = f"{self.BASE_URL}/collections/childrens"
            resp_children = requests.get(url_children, headers=self.headers)
            resp_children.raise_for_status()
            for item in resp_children.json().get('items', []):
                cols[item['_id']] = item['title']
                
            return cols
        except Exception as e:
            logger.error(f"Failed to fetch collections: {e}")
            return {}

    def get_candidate_bookmarks(self, collection_id: int, page: int = 0, per_page: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch bookmarks from a SPECIFIC collection.
        """
        url = f"{self.BASE_URL}/raindrops/{collection_id}"
        params = {
            "page": page,
            "perpage": per_page,
            "sort": "-created"
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])
            
            candidates = []
            for item in items:
                if self._is_video_candidate(item):
                    candidates.append(item)
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error fetching raindrops for col {collection_id}: {e}")
            return []

    def _is_video_candidate(self, item: Dict[str, Any]) -> bool:
        """
        Determine if a bookmark is a likely video candidate.
        Rules:
        1. item['type'] == 'video'
        2. OR URL matches known video sites (Reels, Shorts, etc.)
        """
        # Rule 1: Explicit type
        if item.get("type") == "video":
            return True
        
        # Rule 2: URL heuritstics
        url = item.get("link", "")
        domain = urlparse(url).netloc.lower()
        path = urlparse(url).path.lower()
        
        video_domains = [
            "youtube.com", "youtu.be",
            "vimeo.com",
            "tiktok.com",
            "dailymotion.com",
            "twitch.tv"
        ]
        
        if any(d in domain for d in video_domains):
            return True
            
        # Specific checks for social media video types that might be saved as 'link'
        # Instagram Reels
        if "instagram.com" in domain and "/reel/" in path:
            return True
            
        # Facebook Reels/Watch/Share
        if "facebook.com" in domain and ("/reel/" in path or "/watch" in path or "/videos/" in path or "/share/v/" in path):
            return True
            
        # X/Twitter Video (often just a tweet status, harder to detect without scraping, but let's be conservative)
        
        return False

    def update_bookmark(self, raindrop_id: int, note: str = None, tags: List[str] = None):
        """
        Update the bookmark with summary in note or add tags.
        """
        url = f"{self.BASE_URL}/raindrop/{raindrop_id}"
        payload = {}
        if note:
            payload["please_parse"] = {} # Sometimes needed? No, just 'note'
            payload["note"] = note
        if tags:
            payload["tags"] = tags # This replaces tags. Be careful. Appending is safer logic in caller.
            
        # Implementation Note: Raindrop Update replaces fields. 
        # Ideally we fetch first to append tags, but for now we just support overwriting/setting if provided.
        # If we just want to update note, we send note.
        
        try:
            requests.put(url, headers=self.headers, json=payload)
        except Exception as e:
            logger.error(f"Failed to update bookmark {raindrop_id}: {e}")

raindrop_client = RaindropClient()
