"""RAG pipeline failure reprocessor entrypoint."""

import asyncio
import logging
import sys

from src.blob.client import BlobClient
from src.config import RAGConfig
from src.persistence.repository import Repository
from src.reprocessing.scheduler import process_due_failures

logger = logging.getLogger(__name__)


async def reprocess_failures() -> None:
    """Run one scheduled retry pass for due processing failures."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    repository: Repository | None = None
    blob_client: BlobClient | None = None

    try:
        config = RAGConfig.from_env()
        blob_client = BlobClient(config.storage)
        repository = Repository(
            config.database,
            blob_client=blob_client,
            retry_config=config.retry,
        )
        processed = await process_due_failures(repository, config, blob_client)
        logger.info("Processed %s claimed failures", processed)
    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        sys.exit(1)
    finally:
        if blob_client is not None:
            await blob_client.close()
        if repository is not None:
            await repository.dispose()


if __name__ == "__main__":
    asyncio.run(reprocess_failures())
