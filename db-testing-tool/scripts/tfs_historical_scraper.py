"""TFS Historical Scraper - Downloads Work Items, Test Cases, & Attachments for AI Training."""
import asyncio
import argparse
import sys
import logging
from pathlib import Path

# Add the root app directory to sys.path so we can import the FastAPI backend modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.tfs_service import run_wiql_query, fetch_work_item_full_context
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def scrape_tfs_data(project: str, work_item_types: list, limit: int, path_filter: str):
    if not settings.TFS_BASE_URL or not settings.TFS_PAT:
        logger.error("TFS_BASE_URL and TFS_PAT must be configured in .env")
        return

    # Format the IN clause for work item types
    types_formatted = ", ".join([f"'{t}'" for t in work_item_types])
    
    # Base WIQL to find historical test cases, PBIs, and Bugs
    wiql = f"""
    SELECT [System.Id], [System.Title], [System.WorkItemType], [System.AreaPath]
    FROM WorkItems
    WHERE [System.WorkItemType] IN ({types_formatted})
    """

    if path_filter:
        # Allow targeting specific iteration paths (e.g., CDSIntegration\CDSCCAL)
        wiql += f" AND ([System.AreaPath] UNDER '{path_filter}' OR [System.IterationPath] UNDER '{path_filter}')"
        
    wiql += " ORDER BY [System.ChangedDate] DESC"

    logger.info(f"Executing WIQL on project '{project}':\n{wiql}")
    
    items = await run_wiql_query(project, wiql)
    
    if not items or (isinstance(items, list) and len(items) > 0 and "error" in items[0]):
        logger.error(f"Failed to fetch items or received error: {items}")
        return

    items = items[:limit]
    logger.info(f"Found {len(items)} items matching criteria. Starting deep extraction...")

    success_count = 0
    batch_size = 5  # Process in small batches to respect TFS API rate limits
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        tasks = []
        
        for item in batch:
            item_id = item.get("id")
            if item_id:
                logger.info(f"Scraping [{item.get('work_item_type')}] {item_id}: {item.get('title')}")
                # Inherently downloads attachments, scrapes web links, extracts SQL, and RAG-saves the file
                tasks.append(fetch_work_item_full_context(item_id, project))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    logger.error(f"Failed to process item: {res}")
                else:
                    success_count += 1
        
        await asyncio.sleep(1) # Delay between batches

    logger.info(f"Scraping complete! Successfully hydrated and saved {success_count}/{len(items)} items.")
    logger.info("Training data is located in: data/training_corpus/tfs_scrapes/")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape TFS historical data for AI training.")
    parser.add_argument("--project", type=str, default="CDSIntegration", help="TFS Project name (e.g., CDSIntegration, Lighthouse)")
    parser.add_argument("--types", type=str, default="Test Case,Product Backlog Item,Bug", help="Comma-separated Work Item Types")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum number of items to scrape")
    parser.add_argument("--path", type=str, default="", help="Optional AreaPath or IterationPath filter")

    args = parser.parse_args()
    types_list = [t.strip() for t in args.types.split(",")]
    
    asyncio.run(scrape_tfs_data(args.project, types_list, args.limit, args.path))