"""OpenAI embedding service for semantic similarity."""
import logging
from typing import List, Optional

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating OpenAI embeddings."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the embedding service.

        Args:
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "text-embedding-3-small"  # Fast and cost-effective

    def get_embedding(self, text: str, max_length: int = 8000) -> List[float]:
        """Generate embedding for a text.

        Args:
            text: The text to embed
            max_length: Maximum character length (truncate if longer)

        Returns:
            List of floats representing the embedding vector
        """
        # Truncate if too long
        if len(text) > max_length:
            logger.warning(f"Text length {len(text)} exceeds max {max_length}, truncating")
            text = text[:max_length]

        # Skip empty text
        if not text.strip():
            logger.warning("Empty text provided, returning zero vector")
            return [0.0] * 1536  # text-embedding-3-small returns 1536 dimensions

        try:
            response = self.client.embeddings.create(model=self.model, input=text)
            embedding = response.data[0].embedding
            logger.info(f"Generated embedding with {len(embedding)} dimensions")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def get_embeddings_batch(
        self, texts: List[str], max_length: int = 8000, batch_size: int = 200
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts with automatic batching.

        Automatically splits large requests into smaller batches to respect
        OpenAI's 300k token per request limit.

        Args:
            texts: List of texts to embed
            max_length: Maximum character length per text
            batch_size: Maximum number of texts per API call (default: 200)

        Returns:
            List of embedding vectors
        """
        # Truncate texts
        truncated_texts = [
            text[:max_length] if len(text) > max_length else text for text in texts
        ]

        # Filter empty texts and track indices
        valid_indices = []
        valid_texts = []
        for i, text in enumerate(truncated_texts):
            if text.strip():
                valid_indices.append(i)
                valid_texts.append(text)

        if not valid_texts:
            logger.warning("No valid texts to embed")
            return [[0.0] * 1536 for _ in texts]

        # Create result list with zero vectors for empty texts
        embeddings = [[0.0] * 1536 for _ in texts]

        # Process in batches to avoid token limits
        total_batches = (len(valid_texts) + batch_size - 1) // batch_size
        logger.info(f"Processing {len(valid_texts)} texts in {total_batches} batches")

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(valid_texts))

            batch_texts = valid_texts[start_idx:end_idx]
            batch_indices = valid_indices[start_idx:end_idx]

            try:
                # OpenAI batch API
                logger.info(f"Batch {batch_num + 1}/{total_batches}: Processing {len(batch_texts)} texts")
                response = self.client.embeddings.create(model=self.model, input=batch_texts)

                # Fill in valid embeddings for this batch
                for idx, data in zip(batch_indices, response.data):
                    embeddings[idx] = data.embedding

                logger.info(f"Batch {batch_num + 1}/{total_batches}: Successfully generated {len(batch_texts)} embeddings")

            except Exception as e:
                logger.error(f"Batch {batch_num + 1}/{total_batches} failed: {e}")
                # If a batch fails, try with smaller batch size
                if "max_tokens_per_request" in str(e) and batch_size > 50:
                    logger.warning(f"Retrying batch {batch_num + 1} with smaller batch size")
                    # Recursively retry this batch with half the batch size
                    smaller_batch = self.get_embeddings_batch(
                        [texts[i] for i in batch_indices],
                        max_length=max_length,
                        batch_size=batch_size // 2
                    )
                    # Fill in the embeddings from the smaller batch
                    for i, idx in enumerate(batch_indices):
                        embeddings[idx] = smaller_batch[i]
                else:
                    raise

        logger.info(f"Successfully generated {len(valid_texts)} embeddings across {total_batches} batches")
        return embeddings
