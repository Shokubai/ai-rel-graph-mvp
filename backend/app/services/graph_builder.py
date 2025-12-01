"""Graph builder service for creating knowledge graph JSON."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

from app.services.embedding_service import EmbeddingService
from app.services.llm_tagging_service import LLMTaggingService
from app.services.similarity_service import SimilarityService
from app.services.tag_hierarchy_service import TagHierarchyService

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Service for building knowledge graph from processed documents."""

    def __init__(
        self,
        similarity_threshold: float = 0.75,
        max_tags_per_doc: int = 5,
        max_entities_per_doc: int = 10,
        use_top_k_similarity: bool = True,
        top_k_neighbors: int = 2,
        min_similarity: float = 0.3,
        enable_hierarchy: bool = True,
        hierarchy_split_threshold: int = 10,
        hierarchy_cross_cutting_threshold: int = 5,
    ):
        """Initialize graph builder.

        Args:
            similarity_threshold: Minimum similarity to create edge (0.0-1.0) - only used if use_top_k_similarity=False
            max_tags_per_doc: Maximum number of tags per document
            max_entities_per_doc: Maximum number of entities per document
            use_top_k_similarity: If True, use top-K neighbors approach instead of fixed threshold
            top_k_neighbors: Number of top similar documents per document (only used if use_top_k_similarity=True)
            min_similarity: Minimum similarity to create edge in top-K mode (default: 0.3)
            enable_hierarchy: If True, build hierarchical tag structure (default: True)
            hierarchy_split_threshold: Min documents per tag to consider splitting (default: 10)
            hierarchy_cross_cutting_threshold: Min docs with tag combo for cross-cutting (default: 5)
        """
        self.embedding_service = EmbeddingService()
        self.similarity_service = SimilarityService(
            similarity_threshold=similarity_threshold
        )
        self.llm_tagging_service = LLMTaggingService()
        self.similarity_threshold = similarity_threshold
        self.max_tags_per_doc = max_tags_per_doc
        self.max_entities_per_doc = max_entities_per_doc
        self.use_top_k_similarity = use_top_k_similarity
        self.top_k_neighbors = top_k_neighbors
        self.min_similarity = min_similarity
        self.enable_hierarchy = enable_hierarchy
        self.hierarchy_split_threshold = hierarchy_split_threshold
        self.hierarchy_cross_cutting_threshold = hierarchy_cross_cutting_threshold

        # Initialize hierarchy service if enabled
        if self.enable_hierarchy:
            self.tag_hierarchy_service = TagHierarchyService(
                split_threshold=hierarchy_split_threshold,
                cross_cutting_threshold=hierarchy_cross_cutting_threshold,
            )

    def build_graph_from_documents(
        self, documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build complete graph from processed documents.

        Args:
            documents: List of document dicts with structure:
                {
                    'id': str,
                    'title': str,
                    'url': str,
                    'text': str,
                    'author': str,
                    'modified': str (ISO datetime)
                }

        Returns:
            Graph data dict with nodes, edges, and metadata
        """
        logger.info(f"Building graph from {len(documents)} documents")

        if not documents:
            logger.warning("No documents provided")
            return {"nodes": [], "edges": [], "metadata": {}}

        # Step 1: Generate embeddings
        logger.info("Step 1: Generating embeddings...")
        texts = [doc.get("text", "") for doc in documents]
        embeddings = self.embedding_service.get_embeddings_batch(texts)

        # Step 2: Calculate similarity matrix
        logger.info("Step 2: Calculating similarity matrix...")
        similarity_matrix = self.similarity_service.calculate_similarity_matrix(
            embeddings
        )

        # Step 3: Extract metadata (summary, tags, entities) using LLM
        logger.info("Step 3: Extracting metadata with LLM...")
        metadata_docs = [
            {
                "id": doc["id"],
                "text": doc.get("text", ""),
                "title": doc.get("title", "Untitled"),
            }
            for doc in documents
        ]

        # Track existing tags and entities for consistency
        existing_tags: Set[str] = set()
        existing_entities: Set[str] = set()

        metadata_dict = self.llm_tagging_service.extract_metadata_batch(
            metadata_docs,
            max_tags=self.max_tags_per_doc,
            max_entities=self.max_entities_per_doc,
            existing_tags=existing_tags,
            existing_entities=existing_entities,
        )

        # Step 4: Build nodes
        logger.info("Step 4: Building nodes...")
        nodes = []
        for doc in documents:
            doc_id = doc["id"]
            metadata = metadata_dict.get(
                doc_id,
                {"summary": "", "tags": [], "entities": []},
            )

            nodes.append(
                {
                    "id": doc_id,
                    "title": doc.get("title", "Untitled"),
                    "url": doc.get("url", ""),
                    "summary": metadata["summary"],
                    "tags": metadata["tags"],
                    "entities": metadata["entities"],
                    "author": doc.get("author", "Unknown"),
                    "modified": doc.get("modified", ""),
                    "preview": metadata["summary"] or doc.get("text", "")[:200] + "...",
                }
            )

        # Step 4.5: Build tag hierarchy (if enabled)
        tag_hierarchy = {}
        if self.enable_hierarchy:
            logger.info("Step 4.5: Building tag hierarchy...")
            nodes, tag_hierarchy = self.tag_hierarchy_service.build_hierarchy(nodes)

        # Step 5: Build edges
        logger.info("Step 5: Building edges...")
        doc_ids = [doc["id"] for doc in documents]

        if self.use_top_k_similarity:
            # Use top-K neighbors approach for denser graph
            similar_pairs = self.similarity_service.get_top_k_pairs(
                similarity_matrix,
                doc_ids,
                top_k=self.top_k_neighbors,
                min_similarity=self.min_similarity,
            )
        else:
            # Use traditional fixed threshold approach
            similar_pairs = self.similarity_service.get_similar_pairs(
                similarity_matrix, doc_ids, threshold=self.similarity_threshold
            )

        edges = [
            {
                "source": source_id,
                "target": target_id,
                "similarity": similarity,
                "type": "similar",
            }
            for source_id, target_id, similarity in similar_pairs
        ]

        # Step 6: Build metadata
        metadata = {
            "total_documents": len(nodes),
            "total_connections": len(edges),
            "similarity_mode": f"top-{self.top_k_neighbors}" if self.use_top_k_similarity else "threshold",
            "similarity_threshold": self.similarity_threshold if not self.use_top_k_similarity else None,
            "min_similarity": self.min_similarity if self.use_top_k_similarity else None,
            "top_k_neighbors": self.top_k_neighbors if self.use_top_k_similarity else None,
            "hierarchy_enabled": self.enable_hierarchy,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Add tag hierarchy to metadata if enabled
        if self.enable_hierarchy and tag_hierarchy:
            metadata["tag_hierarchy"] = tag_hierarchy

        graph_data = {"nodes": nodes, "edges": edges, "metadata": metadata}

        if self.use_top_k_similarity:
            logger.info(
                f"Graph built: {len(nodes)} nodes, {len(edges)} edges "
                f"(top-{self.top_k_neighbors} mode, min_similarity={self.min_similarity})"
            )
        else:
            logger.info(
                f"Graph built: {len(nodes)} nodes, {len(edges)} edges "
                f"(threshold={self.similarity_threshold})"
            )

        return graph_data

    def save_graph_to_file(
        self, graph_data: Dict[str, Any], output_path: Path
    ) -> None:
        """Save graph data to JSON file.

        Args:
            graph_data: Graph data dict
            output_path: Path to output file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(graph_data, f, indent=2)

        logger.info(f"Saved graph data to {output_path}")

    def load_graph_from_file(self, input_path: Path) -> Dict[str, Any]:
        """Load graph data from JSON file.

        Args:
            input_path: Path to input file

        Returns:
            Graph data dict
        """
        with open(input_path, "r") as f:
            graph_data = json.load(f)

        logger.info(f"Loaded graph data from {input_path}")
        return graph_data
