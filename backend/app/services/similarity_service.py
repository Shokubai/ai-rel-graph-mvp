"""Similarity calculation service."""
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class SimilarityService:
    """Service for calculating document similarity."""

    def __init__(self, similarity_threshold: float = 0.75):
        """Initialize similarity service.

        Args:
            similarity_threshold: Minimum similarity score to create an edge (0.0-1.0)
        """
        self.similarity_threshold = similarity_threshold

    def calculate_similarity_matrix(
        self, embeddings: List[List[float]]
    ) -> np.ndarray:
        """Calculate cosine similarity matrix from embeddings.

        Args:
            embeddings: List of embedding vectors

        Returns:
            2D numpy array of similarity scores
        """
        if not embeddings:
            return np.array([])

        embeddings_array = np.array(embeddings)
        logger.info(
            f"Calculating similarity matrix for {len(embeddings)} embeddings "
            f"of dimension {embeddings_array.shape[1]}"
        )

        similarity_matrix = cosine_similarity(embeddings_array)
        logger.info(
            f"Calculated similarity matrix of shape {similarity_matrix.shape}"
        )

        return similarity_matrix

    def get_similar_pairs(
        self,
        similarity_matrix: np.ndarray,
        document_ids: List[str],
        threshold: Optional[float] = None,
    ) -> List[Tuple[str, str, float]]:
        """Get pairs of similar documents.

        Args:
            similarity_matrix: 2D array of similarity scores
            document_ids: List of document IDs (same order as matrix)
            threshold: Minimum similarity (uses self.similarity_threshold if None)

        Returns:
            List of (source_id, target_id, similarity_score) tuples
        """
        threshold = threshold if threshold is not None else self.similarity_threshold
        similar_pairs = []

        # Iterate through upper triangle of matrix (avoid duplicates)
        for i in range(len(document_ids)):
            for j in range(i + 1, len(document_ids)):
                similarity = similarity_matrix[i][j]

                if similarity > threshold:
                    similar_pairs.append(
                        (document_ids[i], document_ids[j], float(similarity))
                    )

        logger.info(
            f"Found {len(similar_pairs)} similar pairs "
            f"(threshold={threshold})"
        )

        return similar_pairs

    def get_top_similar(
        self,
        similarity_matrix: np.ndarray,
        document_ids: List[str],
        doc_index: int,
        top_k: int = 5,
    ) -> List[Tuple[str, float]]:
        """Get top K most similar documents to a given document.

        Args:
            similarity_matrix: 2D array of similarity scores
            document_ids: List of document IDs
            doc_index: Index of the document to find similar docs for
            top_k: Number of top similar documents to return

        Returns:
            List of (doc_id, similarity_score) tuples, sorted by similarity
        """
        if doc_index >= len(document_ids):
            return []

        # Get similarities for this document
        similarities = similarity_matrix[doc_index]

        # Get indices of top K (excluding self)
        top_indices = np.argsort(similarities)[::-1]
        top_indices = [idx for idx in top_indices if idx != doc_index][:top_k]

        # Create result list
        results = [
            (document_ids[idx], float(similarities[idx])) for idx in top_indices
        ]

        logger.info(f"Found top {len(results)} similar docs for index {doc_index}")
        return results

    def get_top_k_pairs(
        self,
        similarity_matrix: np.ndarray,
        document_ids: List[str],
        top_k: int = 2,
        min_similarity: float = 0.3,
    ) -> List[Tuple[str, str, float]]:
        """Get similar pairs using top-K neighbors approach.

        For each document, connect to its top K most similar documents.
        This ensures every document has connections, creating a denser graph.

        Args:
            similarity_matrix: 2D array of similarity scores
            document_ids: List of document IDs (same order as matrix)
            top_k: Number of top similar documents per document (default: 2)
            min_similarity: Minimum similarity threshold to avoid nonsense edges (default: 0.3)

        Returns:
            List of (source_id, target_id, similarity_score) tuples
        """
        if len(document_ids) == 0:
            return []

        pairs_set = set()  # Use set to avoid duplicate edges

        for i in range(len(document_ids)):
            # Get similarities for this document
            similarities = similarity_matrix[i]

            # Get indices of top K (excluding self)
            top_indices = np.argsort(similarities)[::-1]
            top_indices = [idx for idx in top_indices if idx != i][:top_k]

            # Create edges to top K neighbors
            for j in top_indices:
                similarity = float(similarities[j])

                # Only create edge if above minimum threshold
                if similarity >= min_similarity:
                    # Always use lower index first to avoid duplicates
                    source_idx = min(i, j)
                    target_idx = max(i, j)
                    pairs_set.add(
                        (document_ids[source_idx], document_ids[target_idx], similarity)
                    )

        similar_pairs = sorted(
            list(pairs_set), key=lambda x: x[2], reverse=True
        )  # Sort by similarity

        logger.info(
            f"Found {len(similar_pairs)} similar pairs using top-{top_k} approach "
            f"(min_similarity={min_similarity})"
        )

        return similar_pairs
