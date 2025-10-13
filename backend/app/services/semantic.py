"""
Semantic Processing Service.

Provides core semantic analysis functionality:
- Embedding generation using sentence-transformers
- Relationship creation based on cosine similarity
- Community-based clustering using graph algorithms
- Semantic topic naming for clusters
"""
import re
from typing import List, Tuple, Dict, Set, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.models.file import File
from app.models.relationship import FileRelationship
from app.models.cluster import Cluster, FileCluster


class SemanticProcessingService:
    """Service for semantic document analysis and clustering."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.5,
        embedding_dimension: int = 384,
    ):
        """
        Initialize the semantic processing service.

        Args:
            model_name: Sentence transformer model name
            similarity_threshold: Minimum similarity for creating relationships
            embedding_dimension: Expected embedding dimension
        """
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.embedding_dimension = embedding_dimension
        self._model: Optional[SentenceTransformer] = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the sentence transformer model."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def generate_embeddings(
        self, texts: List[str], batch_size: int = 16, show_progress: bool = True
    ) -> np.ndarray:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed
            batch_size: Batch size for encoding
            show_progress: Whether to show progress bar

        Returns:
            numpy array of embeddings (shape: [len(texts), embedding_dimension])
        """
        embeddings = self.model.encode(
            texts, show_progress_bar=show_progress, batch_size=batch_size
        )
        return embeddings

    def create_relationships_with_graph(
        self,
        session: Session,
        files: List[File],
        embeddings: np.ndarray,
        threshold: Optional[float] = None,
    ) -> Tuple[List[FileRelationship], Dict[int, Set[int]]]:
        """
        Create semantic relationships and build adjacency graph.

        Args:
            session: Database session
            files: List of File objects
            embeddings: numpy array of embeddings
            threshold: Similarity threshold (uses instance default if None)

        Returns:
            Tuple of (relationships list, adjacency dict)
        """
        if threshold is None:
            threshold = self.similarity_threshold

        # Compute similarity matrix
        similarity_matrix = cosine_similarity(embeddings)

        relationships = []
        adjacency: Dict[int, Set[int]] = {i: set() for i in range(len(files))}

        # Create relationships above threshold
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                similarity = similarity_matrix[i][j]
                if similarity >= threshold:
                    rel = FileRelationship(
                        source_file_id=files[i].id,
                        target_file_id=files[j].id,
                        similarity_score=float(similarity),
                        relationship_type="semantic_similarity",
                    )
                    relationships.append(rel)
                    session.add(rel)

                    # Add to adjacency graph
                    adjacency[i].add(j)
                    adjacency[j].add(i)

        session.commit()
        return relationships, adjacency

    def community_detection_louvain(
        self, adjacency: Dict[int, Set[int]], num_nodes: int
    ) -> List[int]:
        """
        Run Louvain community detection algorithm.

        Args:
            adjacency: Adjacency dict mapping node index to set of neighbor indices
            num_nodes: Total number of nodes

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

            # Run Louvain community detection
            communities = community.louvain_communities(G, resolution=1.0, seed=42)

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

    def generate_semantic_topic_name(
        self, cluster_files: List[File], max_docs: int = 5
    ) -> str:
        """
        Generate a semantic topic name for a cluster.

        Strategy:
        1. Extract sentences from documents
        2. Find most central sentence using embedding similarity
        3. Extract key phrases to create topic name

        Args:
            cluster_files: List of files in the cluster
            max_docs: Maximum number of documents to analyze

        Returns:
            Generated topic name
        """
        try:
            # Collect sentences from documents
            all_sentences = []
            for file in cluster_files[:max_docs]:
                if not file.text_content:
                    continue

                # Split into sentences (simple approach)
                text = file.text_content[:2000]  # First 2K chars
                sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 30]
                all_sentences.extend(sentences[:10])  # Up to 10 sentences per doc

            if len(all_sentences) < 3:
                return f"Document Cluster ({len(cluster_files)} docs)"

            # Encode sentences
            sentence_embeddings = self.model.encode(
                all_sentences, show_progress_bar=False
            )

            # Find most central sentence (closest to centroid)
            centroid = np.mean(sentence_embeddings, axis=0)
            similarities = cosine_similarity([centroid], sentence_embeddings)[0]
            most_central_idx = np.argmax(similarities)
            central_sentence = all_sentences[most_central_idx]

            # Extract key phrases from central sentence
            central_sentence = re.sub(r"\d+", "", central_sentence)  # Remove numbers
            central_sentence = re.sub(
                r"[^\w\s]", " ", central_sentence
            )  # Remove punctuation

            words = central_sentence.split()

            # Filter stopwords and short words
            stopwords = {
                "the",
                "a",
                "an",
                "and",
                "or",
                "but",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "with",
                "by",
                "from",
                "is",
                "are",
                "was",
                "were",
                "been",
                "be",
                "have",
                "has",
                "had",
                "do",
                "does",
                "did",
                "will",
                "would",
                "should",
                "can",
                "could",
                "may",
                "might",
                "must",
                "this",
                "that",
                "these",
                "those",
            }

            meaningful_words = [
                w for w in words if len(w) > 3 and w.lower() not in stopwords
            ]

            if len(meaningful_words) >= 3:
                # Take first 3-4 meaningful words as topic
                topic_words = meaningful_words[:4]
                topic = " ".join([w.capitalize() for w in topic_words])

                # Limit length
                if len(topic) > 50:
                    topic = topic[:47] + "..."

                return f"{topic} ({len(cluster_files)} docs)"
            else:
                # Fallback to first few words of central sentence
                words_to_use = [w.capitalize() for w in words[:4] if len(w) > 2]
                if words_to_use:
                    return f"{' '.join(words_to_use[:3])} ({len(cluster_files)} docs)"

            return f"Document Cluster ({len(cluster_files)} docs)"

        except Exception as e:
            print(f"Warning: Topic naming failed: {e}")
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

            # Generate semantic topic name
            cluster_label = self.generate_semantic_topic_name(cluster_files)

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
        threshold: Optional[float] = None,
        batch_size: int = 16,
        show_progress: bool = True,
    ) -> Dict[str, any]:
        """
        Full semantic processing pipeline for documents.

        Args:
            session: Database session
            files: List of File objects (must have text_content)
            threshold: Similarity threshold (uses instance default if None)
            batch_size: Batch size for embedding generation
            show_progress: Whether to show progress bars

        Returns:
            Dictionary with processing results:
            - embeddings: numpy array
            - relationships: list of FileRelationship objects
            - clusters: list of (Cluster, files) tuples
            - adjacency: adjacency graph dict
        """
        # Step 1: Generate embeddings
        texts = [f.text_content for f in files]
        embeddings = self.generate_embeddings(
            texts, batch_size=batch_size, show_progress=show_progress
        )

        # Step 2: Update files with embeddings
        for file, embedding in zip(files, embeddings):
            file.embedding = embedding.tolist()
            file.processing_status = "completed"
        session.commit()

        # Step 3: Create relationships and build graph
        relationships, adjacency = self.create_relationships_with_graph(
            session, files, embeddings, threshold=threshold
        )

        # Step 4: Create clusters using community detection
        clusters_with_files = self.create_clusters_from_communities(
            session, files, adjacency
        )

        return {
            "embeddings": embeddings,
            "relationships": relationships,
            "clusters": clusters_with_files,
            "adjacency": adjacency,
        }
