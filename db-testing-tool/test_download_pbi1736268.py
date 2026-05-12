"""
Test script to download all files from a TFS/Azure DevOps work item (e.g., PBI1736268) using db-testing-tool services.
"""
import asyncio
from app.services.tfs_service import fetch_work_item_full_context

async def main():
    item_id = 1736268  # PBI1736268
    print(f"Fetching work item {item_id}...")
    context = await fetch_work_item_full_context(item_id)
    attachments = context.get("attachments", [])
    print(f"Found {len(attachments)} attachments.")
    for att in attachments:
        name = att.get("name")
        url = att.get("url")
        content = att.get("content_text") or att.get("content")
        if content:
            fname = f"downloaded_{name or 'attachment'}"
            with open(fname, "w", encoding="utf-8", errors="replace") as f:
                f.write(content)
            print(f"Downloaded: {fname}")
        else:
            print(f"No content for {name} ({url})")

    hyperlinks = context.get("hyperlinks", [])
    print(f"Found {len(hyperlinks)} hyperlinks.")
    for idx, link in enumerate(hyperlinks, 1):
        url = link.get("url")
        content = link.get("content_text") or link.get("content")
        if content and not content.startswith("[HTTP ") and not content.startswith("[Failed"):
            fname = f"downloaded_hyperlink_{idx}.txt"
            with open(fname, "w", encoding="utf-8", errors="replace") as f:
                f.write(content)
            print(f"Downloaded hyperlink content: {fname} ({url})")
        else:
            print(f"No content for hyperlink {idx} ({url})")
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
