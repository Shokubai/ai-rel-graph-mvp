"""Tag extraction service using TF-IDF."""
import logging
from typing import Dict, List

from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)


class TagService:
    """Service for extracting keyword tags from documents."""

    def __init__(self, max_tags_per_doc: int = 5):
        """Initialize tag service.

        Args:
            max_tags_per_doc: Maximum number of tags to extract per document
        """
        self.max_tags_per_doc = max_tags_per_doc

    def extract_tags_batch(
        self, documents: List[Dict[str, str]]
    ) -> Dict[str, List[str]]:
        """Extract tags from multiple documents using TF-IDF.

        Args:
            documents: List of dicts with 'id' and 'text' keys

        Returns:
            Dict mapping document_id -> list of tags
        """
        if not documents:
            return {}

        # Extract texts and IDs
        doc_ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]

        # Filter out empty texts
        valid_docs = [(doc_id, text) for doc_id, text in zip(doc_ids, texts) if text.strip()]

        if not valid_docs:
            logger.warning("No valid texts to extract tags from")
            return {doc_id: [] for doc_id in doc_ids}

        valid_ids, valid_texts = zip(*valid_docs)

        try:
            # Use TF-IDF to extract important words
            vectorizer = TfidfVectorizer(
                max_features=self.max_tags_per_doc * len(valid_texts),
                stop_words="english",
                ngram_range=(1, 2),  # Include bigrams
                min_df=1,  # Minimum document frequency
                max_df=0.8,  # Maximum document frequency (ignore very common words)
            )

            # Fit and transform
            tfidf_matrix = vectorizer.fit_transform(valid_texts)
            feature_names = vectorizer.get_feature_names_out()

            # Extract top tags for each document
            tags_dict = {}
            for i, doc_id in enumerate(valid_ids):
                # Get TF-IDF scores for this document
                doc_vector = tfidf_matrix[i].toarray().flatten()

                # Get indices of top scoring features
                top_indices = doc_vector.argsort()[-self.max_tags_per_doc:][::-1]

                # Get the actual tags
                tags = [
                    feature_names[idx]
                    for idx in top_indices
                    if doc_vector[idx] > 0  # Only include non-zero scores
                ]

                tags_dict[doc_id] = tags

            # Add empty tags for invalid docs
            for doc_id in doc_ids:
                if doc_id not in tags_dict:
                    tags_dict[doc_id] = []

            logger.info(f"Extracted tags for {len(tags_dict)} documents")
            return tags_dict

        except Exception as e:
            logger.error(f"Failed to extract tags: {e}")
            # Return empty tags on error
            return {doc_id: [] for doc_id in doc_ids}

    def extract_tags_single(self, text: str) -> List[str]:
        """Extract tags from a single document.

        Args:
            text: The document text

        Returns:
            List of tag strings
        """
        result = self.extract_tags_batch([{"id": "single", "text": text}])
        return result.get("single", [])
