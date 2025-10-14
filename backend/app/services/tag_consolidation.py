"""Tag consolidation service for merging semantically similar tags."""
from typing import Dict, List, Set

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.models.file_tag import FileTag
from app.models.tag import Tag


class TagConsolidationService:
    """Service for consolidating semantically similar tags."""

    def __init__(
        self,
        similarity_threshold: float = 0.6,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        """Initialize tag consolidation service.

        Args:
            similarity_threshold: Minimum cosine similarity to merge tags (0.0-1.0)
            model_name: Sentence transformer model to use
        """
        self.similarity_threshold = similarity_threshold
        print(f"Loading ML model for consolidation: {model_name}...")
        self.model = SentenceTransformer(model_name)
        print("✓ Consolidation model loaded")

    def consolidate_tags(
        self, session: Session, show_progress: bool = True
    ) -> Dict[str, str]:
        """
        Find similar tags and consolidate them into generalized parent tags.
        Child tags are deleted and documents are reassigned to parent tags.

        Args:
            session: Database session
            show_progress: Whether to show progress updates

        Returns:
            Dictionary mapping {child_tag_name -> parent_tag_name}
        """
        if show_progress:
            print("\n🔄 Consolidating similar tags...")

        # Get all unique tags
        all_tags = session.query(Tag).all()

        if len(all_tags) < 2:
            if show_progress:
                print("   No tags to consolidate")
            return {}

        tag_names = [tag.name for tag in all_tags]

        if show_progress:
            print(f"   Analyzing {len(all_tags)} unique tags...")

        # Generate embeddings for all tags
        embeddings = self.model.encode(tag_names, show_progress_bar=show_progress)

        # Compute similarity matrix
        similarity_matrix = cosine_similarity(embeddings)

        # Find clusters of similar tags using greedy approach
        consolidated_mapping: Dict[str, str] = {}
        processed: Set[str] = set()
        merge_count = 0

        for i, tag_i in enumerate(all_tags):
            if tag_i.name in processed:
                continue

            # Find similar tags above threshold
            similar_indices = np.where(similarity_matrix[i] > self.similarity_threshold)[0]
            similar_tags = [
                all_tags[j] for j in similar_indices if j != i and all_tags[j].name not in processed
            ]

            if similar_tags:
                # Choose parent tag (most frequently used tag in the group)
                candidate_tags = [tag_i] + similar_tags
                parent_tag = self._choose_parent_tag(candidate_tags)

                # Merge child tags into parent
                child_tags = [t for t in candidate_tags if t.id != parent_tag.id]

                if child_tags:
                    self._merge_tags(session, parent_tag, child_tags)
                    merge_count += len(child_tags)

                    for child_tag in child_tags:
                        consolidated_mapping[child_tag.name] = parent_tag.name
                        processed.add(child_tag.name)

            processed.add(tag_i.name)

        session.commit()

        if show_progress:
            print(f"   ✓ Consolidated {merge_count} tags into {len(set(consolidated_mapping.values()))} parent tags")
            print(f"   ✓ Remaining unique tags: {len(all_tags) - merge_count}")

        return consolidated_mapping

    def _choose_parent_tag(self, tags: List[Tag]) -> Tag:
        """Choose the most representative tag as parent.

        Prefers tags with:
        1. Higher usage_count (more documents use it)
        2. Shorter name (more general)
        3. No special characters (cleaner)

        Args:
            tags: List of similar tags

        Returns:
            The tag to use as parent
        """
        # Sort by usage count (desc), then name length (asc)
        sorted_tags = sorted(
            tags,
            key=lambda t: (
                -t.usage_count,  # Higher usage first
                len(t.name),  # Shorter names first
                t.name.count("_"),  # Prefer no underscores
            ),
        )
        return sorted_tags[0]

    def _merge_tags(self, session: Session, parent_tag: Tag, child_tags: List[Tag]) -> None:
        """Merge child tags into parent tag.

        - Reassigns all file-tag associations from children to parent
        - Deletes child tags
        - Updates parent usage_count

        Args:
            session: Database session
            parent_tag: Parent tag to consolidate into
            child_tags: Child tags to merge and delete
        """
        for child_tag in child_tags:
            # Get all file associations for this child tag
            file_tags = session.query(FileTag).filter(FileTag.tag_id == child_tag.id).all()

            for file_tag in file_tags:
                # Check if parent already associated with this file
                existing = (
                    session.query(FileTag)
                    .filter(
                        FileTag.file_id == file_tag.file_id, FileTag.tag_id == parent_tag.id
                    )
                    .first()
                )

                if existing:
                    # Keep the higher relevance score
                    existing.relevance_score = max(
                        existing.relevance_score, file_tag.relevance_score
                    )
                    # Delete the duplicate child association
                    session.delete(file_tag)
                else:
                    # Reassign to parent tag
                    file_tag.tag_id = parent_tag.id
                    parent_tag.usage_count += 1

            # Delete the child tag (CASCADE will handle file_tags)
            session.delete(child_tag)

        session.flush()
