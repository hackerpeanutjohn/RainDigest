from loguru import logger
from src.config import settings
from src.raindrop import raindrop_client
from src.llm import get_provider
from src.organizer import RaindropOrganizer

def main():
    logger.info("Starting Standalone Raindrop Organizer...")
    
    # Init
    llm = get_provider(settings.DEFAULT_LLM_PROVIDER)
    organizer = RaindropOrganizer(raindrop_client, llm)
    
    # Run
    organizer.run()

if __name__ == "__main__":
    main()
