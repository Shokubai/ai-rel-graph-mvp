"""Tests for SemanticProcessingService."""
import pytest
import numpy as np
from sqlalchemy.orm import Session

from app.models.file import File
from app.models.relationship import FileRelationship
from app.models.cluster import Cluster, FileCluster
from app.services.semantic import SemanticProcessingService


@pytest.fixture
def semantic_service():
    """Create semantic processing service."""
    return SemanticProcessingService(
        model_name="all-MiniLM-L6-v2",
        similarity_threshold=0.5,
    )


@pytest.fixture
def sample_texts():
    """Sample texts for testing."""
    return [
        "Machine learning is a subset of artificial intelligence. It focuses on learning from data.",
        "Deep learning uses neural networks with multiple layers. It's a powerful ML technique.",
        "Python is a popular programming language. It's used for web development and data science.",
        "JavaScript is essential for web development. It runs in browsers and on servers.",
        "Financial reports show quarterly earnings. Investors analyze these documents carefully.",
    ]


@pytest.fixture
def test_files(db: Session, sample_texts):
    """Create test files with text content."""
    files = []
    for i, text in enumerate(sample_texts):
        file = File(
            google_drive_id=f"test_file_{i}",
            name=f"test_{i}.txt",
            mime_type="text/plain",
            size_bytes=len(text),
            text_content=text,
            processing_status="pending",
        )
        db.add(file)
        files.append(file)

    db.commit()
    for file in files:
        db.refresh(file)

    return files


class TestEmbeddingGeneration:
    """Test embedding generation."""

    def test_generate_embeddings_basic(self, semantic_service, sample_texts):
        """Test basic embedding generation."""
        embeddings = semantic_service.generate_embeddings(
            sample_texts, show_progress=False
        )

        assert embeddings.shape == (len(sample_texts), 384)
        assert embeddings.dtype == np.float32

    def test_generate_embeddings_similarity(self, semantic_service):
        """Test that similar texts have similar embeddings."""
        similar_texts = [
            "Machine learning and artificial intelligence.",
            "AI and machine learning techniques.",
        ]
        different_text = ["Cooking recipes for delicious meals."]

        embeddings = semantic_service.generate_embeddings(
            similar_texts + different_text, show_progress=False
        )

        # Compute cosine similarity
        from sklearn.metrics.pairwise import cosine_similarity

        sim_matrix = cosine_similarity(embeddings)

        # Similar texts should have high similarity
        similar_similarity = sim_matrix[0, 1]
        assert similar_similarity > 0.7

        # Different texts should have lower similarity
        different_similarity = sim_matrix[0, 2]
        assert different_similarity < similar_similarity

    def test_model_lazy_loading(self, semantic_service):
        """Test that model is lazy-loaded."""
        # Model should not be loaded initially
        assert semantic_service._model is None

        # Accessing model property loads it
        model = semantic_service.model
        assert model is not None
        assert semantic_service._model is not None


class TestRelationshipCreation:
    """Test relationship creation."""

    def test_create_relationships_basic(
        self, db: Session, semantic_service, test_files, sample_texts
    ):
        """Test basic relationship creation."""
        # Generate embeddings
        embeddings = semantic_service.generate_embeddings(
            sample_texts, show_progress=False
        )

        # Create relationships
        relationships, adjacency = semantic_service.create_relationships_with_graph(
            session=db,
            files=test_files,
            embeddings=embeddings,
            threshold=0.5,
        )

        # Should have some relationships (ML texts are similar)
        assert len(relationships) > 0

        # Check adjacency graph structure
        assert len(adjacency) == len(test_files)
        assert all(isinstance(v, set) for v in adjacency.values())

        # Verify relationships in database
        db_relationships = db.query(FileRelationship).all()
        assert len(db_relationships) == len(relationships)

    def test_relationships_above_threshold(
        self, db: Session, semantic_service, test_files, sample_texts
    ):
        """Test that only relationships above threshold are created."""
        embeddings = semantic_service.generate_embeddings(
            sample_texts, show_progress=False
        )

        # Use high threshold
        relationships, _ = semantic_service.create_relationships_with_graph(
            session=db,
            files=test_files,
            embeddings=embeddings,
            threshold=0.8,  # Very high threshold
        )

        # Compute all similarities
        from sklearn.metrics.pairwise import cosine_similarity

        sim_matrix = cosine_similarity(embeddings)

        # Count similarities above threshold
        count_above = 0
        for i in range(len(test_files)):
            for j in range(i + 1, len(test_files)):
                if sim_matrix[i, j] >= 0.8:
                    count_above += 1

        assert len(relationships) == count_above

    def test_no_self_relationships(
        self, db: Session, semantic_service, test_files, sample_texts
    ):
        """Test that no self-relationships are created."""
        embeddings = semantic_service.generate_embeddings(
            sample_texts, show_progress=False
        )

        relationships, _ = semantic_service.create_relationships_with_graph(
            session=db, files=test_files, embeddings=embeddings, threshold=0.3
        )

        # Verify no self-relationships
        for rel in relationships:
            assert rel.source_file_id != rel.target_file_id

    def test_adjacency_graph_symmetry(
        self, db: Session, semantic_service, test_files, sample_texts
    ):
        """Test that adjacency graph is symmetric."""
        embeddings = semantic_service.generate_embeddings(
            sample_texts, show_progress=False
        )

        _, adjacency = semantic_service.create_relationships_with_graph(
            session=db, files=test_files, embeddings=embeddings, threshold=0.5
        )

        # Check symmetry
        for i, neighbors in adjacency.items():
            for j in neighbors:
                assert i in adjacency[j], f"Graph not symmetric: {i} -> {j}"


class TestCommunityDetection:
    """Test community detection."""

    def test_louvain_clustering(self, semantic_service):
        """Test Louvain community detection."""
        # Create a simple graph with clear communities
        # Community 1: nodes 0, 1, 2
        # Community 2: nodes 3, 4
        adjacency = {
            0: {1, 2},
            1: {0, 2},
            2: {0, 1},
            3: {4},
            4: {3},
        }

        labels = semantic_service.community_detection_louvain(adjacency, num_nodes=5)

        assert len(labels) == 5
        assert len(set(labels)) >= 2  # At least 2 communities

        # Nodes in same community should have same label
        # (Note: exact community assignment may vary)
        assert labels[0] == labels[1] or labels[0] == labels[2]

    def test_connected_components_fallback(self, semantic_service):
        """Test connected components clustering as fallback."""
        adjacency = {
            0: {1},
            1: {0},
            2: {3},
            3: {2},
            4: set(),  # Isolated node
        }

        labels = semantic_service._connected_components_clustering(adjacency, num_nodes=5)

        assert len(labels) == 5
        # Should have 3 components: {0,1}, {2,3}, {4}
        assert len(set(labels)) == 3


class TestTopicNaming:
    """Test semantic topic naming."""

    def test_topic_naming_basic(self, db: Session, semantic_service):
        """Test basic topic name generation."""
        # Create files with ML content
        ml_texts = [
            "Neural networks are fundamental to deep learning. They consist of layers of interconnected nodes.",
            "Deep learning models require large datasets. Training involves optimizing weights through backpropagation.",
            "Convolutional neural networks excel at image recognition tasks. They use filters to detect patterns.",
        ]

        files = []
        for i, text in enumerate(ml_texts):
            file = File(
                google_drive_id=f"ml_file_{i}",
                name=f"ml_{i}.txt",
                text_content=text,
            )
            db.add(file)
            files.append(file)
        db.commit()

        # Generate topic name
        topic = semantic_service.generate_semantic_topic_name(files)

        assert isinstance(topic, str)
        assert len(topic) > 0
        assert f"({len(files)} docs)" in topic

    def test_topic_naming_insufficient_content(self, db: Session, semantic_service):
        """Test topic naming with insufficient content."""
        file = File(
            google_drive_id="short_file",
            name="short.txt",
            text_content="Short text.",
        )
        db.add(file)
        db.commit()

        topic = semantic_service.generate_semantic_topic_name([file])

        # Should fall back to generic name
        assert "Document Cluster (1 docs)" == topic


class TestFullPipeline:
    """Test complete semantic processing pipeline."""

    def test_process_documents_complete(
        self, db: Session, semantic_service, test_files, sample_texts
    ):
        """Test complete document processing pipeline."""
        # Run full pipeline
        results = semantic_service.process_documents(
            session=db,
            files=test_files,
            threshold=0.5,
            show_progress=False,
        )

        # Check all components
        assert "embeddings" in results
        assert "relationships" in results
        assert "clusters" in results
        assert "adjacency" in results

        # Verify embeddings
        assert results["embeddings"].shape == (len(test_files), 384)

        # Verify files have embeddings
        for file in test_files:
            db.refresh(file)
            assert file.embedding is not None
            assert len(file.embedding) == 384
            assert file.processing_status == "completed"

        # Verify relationships
        assert len(results["relationships"]) > 0
        db_relationships = db.query(FileRelationship).all()
        assert len(db_relationships) == len(results["relationships"])

        # Verify clusters
        assert len(results["clusters"]) > 0
        db_clusters = db.query(Cluster).all()
        assert len(db_clusters) == len(results["clusters"])

        # Verify cluster assignments
        cluster_assignments = db.query(FileCluster).all()
        assert len(cluster_assignments) == len(test_files)

    def test_process_documents_low_threshold(
        self, db: Session, semantic_service, test_files, sample_texts
    ):
        """Test processing with low threshold creates more relationships."""
        results = semantic_service.process_documents(
            session=db,
            files=test_files,
            threshold=0.3,  # Low threshold
            show_progress=False,
        )

        # Should create more relationships with lower threshold
        assert len(results["relationships"]) >= 3

    def test_process_documents_high_threshold(
        self, db: Session, semantic_service, test_files, sample_texts
    ):
        """Test processing with high threshold creates fewer relationships."""
        results = semantic_service.process_documents(
            session=db,
            files=test_files,
            threshold=0.8,  # High threshold
            show_progress=False,
        )

        # May create very few relationships
        # But should still complete without errors
        assert isinstance(results["relationships"], list)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_text_list(self, semantic_service):
        """Test handling of empty text list."""
        embeddings = semantic_service.generate_embeddings([], show_progress=False)
        assert embeddings.shape == (0, 384)

    def test_single_file(self, db: Session, semantic_service):
        """Test processing a single file."""
        file = File(
            google_drive_id="single_file",
            name="single.txt",
            text_content="This is a test document.",
        )
        db.add(file)
        db.commit()

        results = semantic_service.process_documents(
            session=db, files=[file], show_progress=False
        )

        # Should have embedding but no relationships
        assert results["embeddings"].shape == (1, 384)
        assert len(results["relationships"]) == 0
        assert len(results["clusters"]) == 1  # Single file forms one cluster

    def test_two_identical_files(self, db: Session, semantic_service):
        """Test processing two identical files."""
        text = "This is identical content."
        files = []
        for i in range(2):
            file = File(
                google_drive_id=f"identical_{i}",
                name=f"identical_{i}.txt",
                text_content=text,
            )
            db.add(file)
            files.append(file)
        db.commit()

        results = semantic_service.process_documents(
            session=db, files=files, threshold=0.5, show_progress=False
        )

        # Should have high similarity
        assert len(results["relationships"]) == 1
        rel = results["relationships"][0]
        assert rel.similarity_score > 0.9  # Nearly identical
