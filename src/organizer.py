import time
from typing import List, Dict, Any
from loguru import logger
from .config import settings
from .raindrop import RaindropClient
from .llm import LLMProvider

class RaindropOrganizer:
    def __init__(self, raindrop_client: RaindropClient, llm: LLMProvider):
        self.raindrop = raindrop_client
        self.llm = llm

    def run(self):
        """
        Main execution method to organize Unsorted items.
        """
        logger.info("--- 🗂 Starting Raindrop Organizer ---")
        
        # 1. Fetch all collections to know where to move items
        logger.info("Fetching all collections...")
        collections = self.raindrop.get_collections()
        if not collections:
            logger.error("No collections found. Aborting organization.")
            return

        # 2. Fetch Unsorted items
        logger.info("Fetching Unsorted items...")
        # API uses collectionID = -1 for Unsorted
        unsorted_items = self.raindrop.get_candidate_bookmarks(collection_id=-1, per_page=10) # Start small
        
        if not unsorted_items:
            logger.info("No items found in Unsorted.")
            return

        logger.info(f"Found {len(unsorted_items)} items to organize.")
        
        # 3. Process each item
        for item in unsorted_items:
            try:
                self._process_item(item, collections)
                # Respect API limits/LLM limits
                time.sleep(1) 
            except Exception as e:
                logger.error(f"Error processing item {item.get('title', 'Unknown')}: {e}")

    def _process_item(self, item: Dict[str, Any], collections: Dict[int, str]):
        r_id = item['_id']
        title = item.get('title', '')
        note = item.get('excerpt', '') or item.get('note', '') or ''
        link = item.get('link', '')

        logger.info(f"Analyzing: {title} ({link})")
        
        # Ask LLM for best collection
        target_cid = self.llm.classify_bookmark(title=title, note=note, collections=collections)
        
        if target_cid is None:
            logger.warning(f"  -> No suitable collection found (or uncertain). Skipping.")
            return

        if target_cid not in collections:
            logger.warning(f"  -> LLM returned unknown collection ID {target_cid}. Skipping.")
            return
            
        target_name = collections[target_cid]
        
        # Execute Move
        if settings.DRY_RUN:
            logger.success(f"  [DRY RUN] Would move to: {target_name} ({target_cid})")
        else:
            success = self.raindrop.move_bookmark(r_id, target_cid)
            if success:
                logger.success(f"  -> Moved to: {target_name}")
            else:
                logger.error(f"  -> Failed to move to: {target_name}")
