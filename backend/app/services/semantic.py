"""
Tag-Based Processing Service.

Provides core tag-based document analysis functionality:
- ML-based semantic tag extraction using KeyBERT
- Tag consolidation to merge similar tags
- Relationship creation based on shared tag count
- Community-based clustering using tag similarity graph
- Semantic topic naming for clusters
"""
from typing import List, Tuple, Dict, Set, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.file import File
from app.models.relationship import FileRelationship
from app.models.cluster import Cluster, FileCluster
from app.models.tag import Tag
from app.models.file_tag import FileTag
from app.services.ml_tag_extraction import MLTagExtractionService
from app.services.tag_consolidation import TagConsolidationService


class SemanticProcessingService:
    """Service for tag-based document analysis and clustering."""

    def __init__(
        self,
        min_shared_tags: int = 2,  # Minimum shared tags for relationships
        max_tags_per_doc: int = 15,  # Maximum tags per document
        consolidation_threshold: float = 0.6,  # Similarity threshold for tag merging
        diversity: float = 0.7,  # Diversity parameter for KeyBERT
    ):
        """
        Initialize the ML-based tag processing service.

        Args:
            min_shared_tags: Minimum number of shared tags to create a relationship
            max_tags_per_doc: Maximum number of tags to extract per document
            consolidation_threshold: Similarity threshold for merging similar tags (0.0-1.0)
            diversity: Diversity parameter for KeyBERT MMR (0.0-1.0, higher = more diverse)
        """
        self.min_shared_tags = min_shared_tags
        self.tag_extractor = MLTagExtractionService(
            max_tags_per_doc=max_tags_per_doc,
            diversity=diversity,
        )
        self.tag_consolidator = TagConsolidationService(
            similarity_threshold=consolidation_threshold,
        )

    def extract_and_store_tags(
        self,
        session: Session,
        files: List[File],
        show_progress: bool = True,
    ) -> Dict[str, List[Tuple[Tag, float]]]:
        """
        Extract tags from files and store them in database.

        Args:
            session: Database session
            files: List of File objects with text_content
            show_progress: Whether to show progress updates

        Returns:
            Dictionary mapping file_id to list of (Tag, relevance_score) tuples
        """
        file_tags_map = {}

        for idx, file in enumerate(files):
            if show_progress and (idx % 10 == 0 or idx == len(files) - 1):
                print(f"Extracting tags: {idx + 1}/{len(files)}")

            # Extract tags from text using ML model
            extracted_tags = self.tag_extractor.extract_tags(file.text_content or "")

            if not extracted_tags:
                file.processing_status = "completed"
                continue

            # Store tags in database
            file_tag_objects = []
            seen_tags = set()  # Track tags already added for this file

            for tag_name, relevance_score in extracted_tags:
                # Skip if we've already added this tag for this file
                if tag_name in seen_tags:
                    continue
                seen_tags.add(tag_name)

                # Get or create tag
                tag = session.query(Tag).filter(Tag.name == tag_name).first()

                if not tag:
                    # Store embedding for consolidation later
                    embedding = self.tag_extractor.get_embedding(tag_name)
                    tag = Tag(
                        name=tag_name,
                        category=None,  # Category will be auto-discovered from clusters
                        usage_count=0,
                        embedding=embedding.tolist() if embedding is not None else None,
                    )
                    session.add(tag)
                    session.flush()

                # Check if file-tag association already exists
                existing = session.query(FileTag).filter(
                    FileTag.file_id == file.id,
                    FileTag.tag_id == tag.id
                ).first()

                if existing:
                    # Update relevance score if this one is higher
                    if relevance_score > existing.relevance_score:
                        existing.relevance_score = relevance_score
                    file_tag_objects.append((tag, existing.relevance_score))
                else:
                    # Increment usage count
                    tag.usage_count += 1

                    # Create file-tag association
                    file_tag = FileTag(
                        file_id=file.id,
                        tag_id=tag.id,
                        relevance_score=relevance_score,
                    )
                    session.add(file_tag)
                    file_tag_objects.append((tag, relevance_score))

            file_tags_map[str(file.id)] = file_tag_objects
            file.processing_status = "completed"

        session.commit()
        return file_tags_map

    def create_relationships_with_graph(
        self,
        session: Session,
        files: List[File],
        min_shared: Optional[int] = None,
    ) -> Tuple[List[FileRelationship], Dict[int, Set[int]]]:
        """
        Create tag-based relationships and build adjacency graph.

        Args:
            session: Database session
            files: List of File objects
            min_shared: Minimum shared tags (uses instance default if None)

        Returns:
            Tuple of (relationships list, adjacency dict)
        """
        if min_shared is None:
            min_shared = self.min_shared_tags

        # Build tag sets for each file
        file_tag_sets: Dict[str, Set[str]] = {}

        for file in files:
            # Query tags for this file
            file_tags = (
                session.query(Tag)
                .join(FileTag)
                .filter(FileTag.file_id == file.id)
                .all()
            )
            file_tag_sets[str(file.id)] = {tag.name for tag in file_tags}

        relationships = []
        adjacency: Dict[int, Set[int]] = {i: set() for i in range(len(files))}

        # Create relationships based on shared tags
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                file_i_tags = file_tag_sets[str(files[i].id)]
                file_j_tags = file_tag_sets[str(files[j].id)]

                # Count shared tags
                shared_tags = file_i_tags & file_j_tags
                shared_count = len(shared_tags)

                if shared_count >= min_shared:
                    # Calculate normalized similarity score (Jaccard similarity)
                    union_tags = file_i_tags | file_j_tags
                    similarity_score = shared_count / len(union_tags) if union_tags else 0.0

                    rel = FileRelationship(
                        source_file_id=files[i].id,
                        target_file_id=files[j].id,
                        shared_tag_count=shared_count,
                        similarity_score=float(similarity_score),
                        relationship_type="tag_similarity",
                    )
                    relationships.append(rel)
                    session.add(rel)

                    # Add to adjacency graph
                    adjacency[i].add(j)
                    adjacency[j].add(i)

        session.commit()
        return relationships, adjacency

    def community_detection_louvain(
        self, adjacency: Dict[int, Set[int]], num_nodes: int, resolution: float = 0.5
    ) -> List[int]:
        """
        Run Louvain community detection algorithm.

        Args:
            adjacency: Adjacency dict mapping node index to set of neighbor indices
            num_nodes: Total number of nodes
            resolution: Resolution parameter (lower = fewer, larger clusters; default 0.5)

        Returns:
            List of cluster labels for each node
        """
        try:
            import networkx as nx
            from networkx.algorithms import community

            # Build NetworkX graph
            G = nx.Graph()
            G.add_nodes_from(range(num_nodes))

            for node, neighbors in adjacency.items():
                for neighbor in neighbors:
                    if node < neighbor:  # Avoid duplicates
                        G.add_edge(node, neighbor)

            # Run Louvain community detection with lower resolution for fewer clusters
            communities = community.louvain_communities(G, resolution=resolution, seed=42)

            # Convert to labels array
            labels = [-1] * num_nodes
            for cluster_id, comm in enumerate(communities):
                for node in comm:
                    labels[node] = cluster_id

            return labels

        except ImportError:
            # Fallback to connected components
            return self._connected_components_clustering(adjacency, num_nodes)

    def _connected_components_clustering(
        self, adjacency: Dict[int, Set[int]], num_nodes: int
    ) -> List[int]:
        """
        Simple connected components clustering (fallback).

        Args:
            adjacency: Adjacency dict
            num_nodes: Total number of nodes

        Returns:
            List of cluster labels
        """
        labels = [-1] * num_nodes
        cluster_id = 0
        visited: Set[int] = set()

        def dfs(node: int, current_cluster: int):
            visited.add(node)
            labels[node] = current_cluster
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, current_cluster)

        for node in range(num_nodes):
            if node not in visited:
                dfs(node, cluster_id)
                cluster_id += 1

        return labels

    def generate_cluster_name_from_tags(
        self, session: Session, cluster_files: List[File], max_tags: int = 3
    ) -> str:
        """
        Generate a semantic cluster name based on most common tags.
        Category is auto-discovered from the cluster's semantic content.

        Args:
            session: Database session
            cluster_files: List of files in the cluster
            max_tags: Maximum number of tags to include in name

        Returns:
            Generated cluster name based on semantic tags
        """
        try:
            file_ids = [f.id for f in cluster_files]

            # Query top tags for cluster files (by usage frequency)
            cluster_tags = (
                session.query(Tag, func.count(FileTag.file_id).label("count"))
                .join(FileTag)
                .filter(FileTag.file_id.in_(file_ids))
                .group_by(Tag.id)
                .order_by(func.count(FileTag.file_id).desc())
                .limit(max_tags + 5)  # Get a few extra to choose from
                .all()
            )

            if not cluster_tags:
                return f"Document Cluster ({len(cluster_files)} docs)"

            # Extract top tags (capitalize for readability)
            top_tags = []
            for tag, count in cluster_tags:
                if len(top_tags) >= max_tags:
                    break
                # Capitalize multi-word phrases properly
                tag_display = " ".join(word.capitalize() for word in tag.name.split())
                top_tags.append(tag_display)

            # Build semantic cluster name
            if top_tags:
                tag_str = " & ".join(top_tags)
                # Truncate if too long
                if len(tag_str) > 60:
                    tag_str = tag_str[:57] + "..."
                return f"{tag_str} ({len(cluster_files)} docs)"

            return f"Document Cluster ({len(cluster_files)} docs)"

        except Exception as e:
            print(f"Warning: Cluster naming failed: {e}")
            return f"Document Cluster ({len(cluster_files)} docs)"

    def create_clusters_from_communities(
        self,
        session: Session,
        files: List[File],
        adjacency: Dict[int, Set[int]],
    ) -> List[Tuple[Cluster, List[File]]]:
        """
        Create clusters using community detection on relationship graph.

        Args:
            session: Database session
            files: List of File objects
            adjacency: Adjacency graph from relationships

        Returns:
            List of (Cluster, files) tuples
        """
        num_nodes = len(files)

        # Run community detection
        labels = self.community_detection_louvain(adjacency, num_nodes)

        unique_labels = set(labels)
        clusters_with_files = []

        # Create clusters from communities
        for cluster_id in sorted(unique_labels):
            cluster_indices = [i for i, label in enumerate(labels) if label == cluster_id]
            cluster_files = [files[i] for i in cluster_indices]

            # Generate cluster name from tags
            cluster_label = self.generate_cluster_name_from_tags(session, cluster_files)

            # Create cluster
            cluster = Cluster(label=cluster_label)
            session.add(cluster)
            session.flush()

            # Create file-cluster mappings
            for file in cluster_files:
                file_cluster = FileCluster(file_id=file.id, cluster_id=cluster.id)
                session.add(file_cluster)

            clusters_with_files.append((cluster, cluster_files))

        session.commit()
        return clusters_with_files

    def process_documents(
        self,
        session: Session,
        files: List[File],
        min_shared: Optional[int] = None,
        show_progress: bool = True,
        consolidate_tags: bool = True,
    ) -> Dict[str, any]:
        """
        Full ML-based tag processing pipeline for documents.

        Args:
            session: Database session
            files: List of File objects (must have text_content)
            min_shared: Minimum shared tags for relationships (uses instance default if None)
            show_progress: Whether to show progress updates
            consolidate_tags: Whether to consolidate similar tags after extraction

        Returns:
            Dictionary with processing results:
            - file_tags: dict mapping file_id to list of (Tag, relevance) tuples
            - relationships: list of FileRelationship objects
            - clusters: list of (Cluster, files) tuples
            - adjacency: adjacency graph dict
            - consolidated_tags: dict mapping child -> parent tag names (if consolidation enabled)
        """
        # Step 1: Extract and store tags using ML
        if show_progress:
            print("Step 1: Extracting semantic tags using ML...")

        file_tags = self.extract_and_store_tags(session, files, show_progress=show_progress)

        # Step 2: Consolidate similar tags
        consolidated_mapping = {}
        if consolidate_tags:
            if show_progress:
                print("\nStep 2: Consolidating similar tags...")
            consolidated_mapping = self.tag_consolidator.consolidate_tags(
                session, show_progress=show_progress
            )

        # Step 3: Create relationships based on shared tags
        if show_progress:
            step_num = 3 if consolidate_tags else 2
            print(f"\nStep {step_num}: Creating relationships based on shared tags...")

        relationships, adjacency = self.create_relationships_with_graph(
            session, files, min_shared=min_shared
        )

        # Step 4: Create clusters using community detection
        if show_progress:
            step_num = 4 if consolidate_tags else 3
            print(f"Step {step_num}: Clustering documents by tag similarity...")

        clusters_with_files = self.create_clusters_from_communities(
            session, files, adjacency
        )

        if show_progress:
            print(f"\n✓ Processed {len(files)} documents")
            if consolidated_mapping:
                print(f"✓ Consolidated {len(consolidated_mapping)} similar tags")
            print(f"✓ Created {len(relationships)} relationships")
            print(f"✓ Discovered {len(clusters_with_files)} clusters")

        return {
            "file_tags": file_tags,
            "relationships": relationships,
            "clusters": clusters_with_files,
            "adjacency": adjacency,
            "consolidated_tags": consolidated_mapping,
        }
