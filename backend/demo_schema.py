"""
Demo script to showcase the database schema with realistic mock data.

This script demonstrates:
1. Creating files with text content and embeddings
2. Computing semantic similarity relationships
3. Clustering documents by topic
4. Tracking processing jobs

Run with: python demo_schema.py
"""
import os
import sys
import uuid
from datetime import datetime
from typing import List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.models.cluster import Cluster, FileCluster
from app.models.file import File
from app.models.job import ProcessingJob
from app.models.relationship import FileRelationship
from app.core.database import Base

# Database connection
# Use 'postgres' service name when running in Docker, 'localhost' otherwise
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/semantic_graph_demo"
)

# Mock document corpus - realistic Google Drive files
MOCK_DOCUMENTS = [
    # Cluster 1: Machine Learning Research
    {
        "google_drive_id": "1a2b3c4d5e6f",
        "name": "Deep Learning for Computer Vision.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 2_456_789,
        "text_content": """
        Deep learning has revolutionized computer vision tasks. Convolutional neural networks (CNNs)
        have shown remarkable performance in image classification, object detection, and segmentation.
        Transfer learning with pretrained models like ResNet and VGG has become standard practice.
        Recent advances in attention mechanisms and transformer architectures are pushing boundaries.
        """,
    },
    {
        "google_drive_id": "2b3c4d5e6f7g",
        "name": "Neural Network Architectures Survey.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 3_123_456,
        "text_content": """
        A comprehensive survey of neural network architectures. We examine feedforward networks,
        recurrent networks, and convolutional architectures. Modern deep learning relies heavily
        on GPU acceleration and backpropagation optimization. Transformer models have emerged
        as powerful alternatives to traditional RNN architectures for sequence tasks.
        """,
    },
    {
        "google_drive_id": "3c4d5e6f7g8h",
        "name": "Transfer Learning Best Practices.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1_876_543,
        "text_content": """
        Transfer learning enables efficient training with limited data. Pretrained models on ImageNet
        provide excellent feature extractors. Fine-tuning strategies include freezing early layers
        and training only final classification heads. CNNs pretrained on large datasets transfer
        well to domain-specific computer vision tasks.
        """,
    },

    # Cluster 2: Financial Documents
    {
        "google_drive_id": "4d5e6f7g8h9i",
        "name": "Q4 Financial Report 2024.xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "size_bytes": 567_890,
        "text_content": """
        Q4 2024 Financial Summary. Revenue increased 15% year-over-year to $10.5M.
        Operating expenses decreased 8% due to cost optimization. Net profit margin improved
        to 22%. Cash reserves stand at $3.2M. Budget allocation for 2025 shows 30% increase
        in R&D spending and 20% in marketing initiatives.
        """,
    },
    {
        "google_drive_id": "5e6f7g8h9i0j",
        "name": "2025 Budget Proposal.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 234_567,
        "text_content": """
        2025 Budget Proposal. Projected revenue: $12.5M (19% growth). Proposed spending:
        R&D $3.75M, Marketing $2.5M, Operations $4M, Admin $1.25M. Expected profit margin
        of 25%. Cash flow forecasts indicate strong liquidity. Budget aligns with strategic
        growth objectives and market expansion plans.
        """,
    },
    {
        "google_drive_id": "6f7g8h9i0j1k",
        "name": "Expense Report November.xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "size_bytes": 123_456,
        "text_content": """
        November 2024 Expense Report. Travel: $12,450. Software licenses: $8,900.
        Marketing campaigns: $25,600. Office supplies: $3,200. Total monthly expenses: $87,340.
        Within budget allocation. Year-to-date spending tracking shows 92% budget utilization.
        Q4 financial targets remain on track.
        """,
    },

    # Cluster 3: Meeting Notes & Strategy
    {
        "google_drive_id": "7g8h9i0j1k2l",
        "name": "Product Strategy Q1 2025.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 345_678,
        "text_content": """
        Q1 2025 Product Strategy Meeting Notes. Key priorities: launch mobile app, improve
        user onboarding, expand API capabilities. Product roadmap includes AI-powered features
        and enterprise tier. Customer feedback indicates strong demand for integrations.
        Timeline: mobile app beta in January, full launch March 2025.
        """,
    },
    {
        "google_drive_id": "8h9i0j1k2l3m",
        "name": "Team Roadmap Planning.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 289_012,
        "text_content": """
        Roadmap Planning Session. Q1 goals: ship mobile application, enhance API infrastructure,
        onboard 3 enterprise clients. Engineering capacity: 5 engineers. Product priorities
        aligned with strategy. Mobile app development starts December, API v2 in parallel.
        User experience improvements scheduled for Q1 rollout.
        """,
    },

    # Cluster 4: HR & Operations
    {
        "google_drive_id": "9i0j1k2l3m4n",
        "name": "Employee Handbook 2024.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1_234_567,
        "text_content": """
        Company Employee Handbook. Policies on remote work, vacation time, benefits packages.
        Code of conduct and workplace guidelines. Professional development opportunities
        include conference attendance and online learning stipends. Health insurance coverage
        details and retirement plan options. Performance review process occurs quarterly.
        """,
    },
    {
        "google_drive_id": "0j1k2l3m4n5o",
        "name": "Office Policies Update.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 156_789,
        "text_content": """
        Updated Office Policies Effective January 2025. Hybrid work model: 3 days in office,
        2 days remote. Health and safety protocols. Equipment reimbursement policy for home
        offices. Updated vacation accrual rates. Benefits enrollment period in December.
        Employee wellness program launching Q1.
        """,
    },

    # Outlier: Technical Documentation
    {
        "google_drive_id": "1k2l3m4n5o6p",
        "name": "API Documentation v2.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 789_012,
        "text_content": """
        REST API Documentation Version 2.0. Authentication uses OAuth 2.0. Rate limits:
        1000 requests per hour for standard tier. Webhook support for real-time events.
        GraphQL endpoint available at /graphql. SDK libraries for Python, JavaScript, Ruby.
        Comprehensive endpoint reference and code examples included.
        """,
    },
]


def setup_database(engine):
    """Create database and enable pgvector extension."""
    print("🔧 Setting up database...")

    # Drop and recreate database
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Create tables
    Base.metadata.create_all(engine)
    print("✅ Database schema created")


def generate_embeddings(documents: List[dict]) -> List[np.ndarray]:
    """Generate embeddings using sentence-transformers."""
    print("🧠 Generating embeddings with sentence-transformers...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    texts = [doc["text_content"] for doc in documents]
    embeddings = model.encode(texts, show_progress_bar=False)

    print(f"✅ Generated {len(embeddings)} embeddings (384 dimensions each)")
    return embeddings


def create_files(session, documents: List[dict], embeddings: List[np.ndarray]) -> List[File]:
    """Create file records with embeddings."""
    print("📄 Creating file records...")

    files = []
    for doc, embedding in zip(documents, embeddings):
        file = File(
            google_drive_id=doc["google_drive_id"],
            name=doc["name"],
            mime_type=doc["mime_type"],
            size_bytes=doc["size_bytes"],
            text_content=doc["text_content"],
            embedding=embedding.tolist(),
            processing_status="completed",
        )
        files.append(file)
        session.add(file)

    session.commit()
    print(f"✅ Created {len(files)} files")
    return files


def create_relationships(
    session,
    files: List[File],
    embeddings: List[np.ndarray],
    threshold: float = 0.5
) -> List[FileRelationship]:
    """Create semantic similarity relationships."""
    print(f"🔗 Computing relationships (threshold: {threshold})...")

    # Compute cosine similarity matrix
    similarity_matrix = cosine_similarity(embeddings)

    relationships = []
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

    session.commit()
    print(f"✅ Created {len(relationships)} relationships")
    return relationships


def generate_cluster_name(cluster_files: List[File]) -> str:
    """Generate a descriptive cluster name based on file content."""
    from collections import Counter
    import re

    # Combine all text content from cluster
    all_text = " ".join([f.text_content or "" for f in cluster_files])

    # Extract meaningful words (remove common words)
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
        'can', 'could', 'may', 'might', 'must', 'this', 'that', 'these', 'those'
    }

    # Extract words (lowercase, remove punctuation)
    words = re.findall(r'\b[a-zA-Z]{4,}\b', all_text.lower())
    meaningful_words = [w for w in words if w not in stop_words]

    # Get most common words
    word_counts = Counter(meaningful_words)
    top_words = [word for word, count in word_counts.most_common(3)]

    if top_words:
        # Capitalize and join top 2 words
        cluster_name = " & ".join([w.capitalize() for w in top_words[:2]])
        return cluster_name
    else:
        # Fallback to file extensions
        extensions = [f.name.split('.')[-1].upper() for f in cluster_files]
        return f"{Counter(extensions).most_common(1)[0][0]} Documents"


def create_clusters(
    session,
    files: List[File],
    embeddings: List[np.ndarray]
) -> List[Tuple[Cluster, List[File]]]:
    """Create clusters using DBSCAN algorithm based on embedding similarity."""
    from sklearn.cluster import DBSCAN

    print("🎯 Creating clusters with DBSCAN...")

    # Convert embeddings to numpy array
    embeddings_array = np.array(embeddings)

    # Use DBSCAN for clustering
    # eps: maximum distance between samples to be considered in same neighborhood
    # min_samples: minimum samples in neighborhood to form core point
    # metric: use cosine distance for semantic similarity
    # INCREASED eps from 0.35 to 0.5 to reduce outliers (more inclusive)
    dbscan = DBSCAN(eps=0.5, min_samples=2, metric='cosine')
    cluster_labels = dbscan.fit_predict(embeddings_array)

    # Get unique cluster IDs (excluding -1 which represents noise/outliers)
    unique_labels = set(cluster_labels)
    unique_labels.discard(-1)  # Remove noise label

    print(f"  • Found {len(unique_labels)} clusters + {list(cluster_labels).count(-1)} outliers")

    clusters_with_files = []

    # Create clusters
    for cluster_id in sorted(unique_labels):
        # Get files in this cluster
        cluster_file_indices = [i for i, label in enumerate(cluster_labels) if label == cluster_id]
        cluster_files = [files[i] for i in cluster_file_indices]

        # Generate descriptive cluster label from content
        cluster_label = generate_cluster_name(cluster_files)

        # Create cluster record
        cluster = Cluster(label=cluster_label)
        session.add(cluster)
        session.flush()

        # Map files to cluster
        for file in cluster_files:
            file_cluster = FileCluster(
                file_id=file.id,
                cluster_id=cluster.id
            )
            session.add(file_cluster)

        clusters_with_files.append((cluster, cluster_files))

    # Handle outliers (noise points) - create individual clusters
    outlier_indices = [i for i, label in enumerate(cluster_labels) if label == -1]
    if outlier_indices:
        for idx in outlier_indices:
            outlier_file = files[idx]
            # Use file name or content-based name
            file_name_base = outlier_file.name.rsplit('.', 1)[0][:40]
            outlier_cluster = Cluster(label=f"Unclustered: {file_name_base}")
            session.add(outlier_cluster)
            session.flush()

            file_cluster = FileCluster(
                file_id=outlier_file.id,
                cluster_id=outlier_cluster.id
            )
            session.add(file_cluster)

            clusters_with_files.append((outlier_cluster, [outlier_file]))

    session.commit()
    print(f"✅ Created {len(clusters_with_files)} total clusters")
    return clusters_with_files


def create_processing_job(session, total_files: int) -> ProcessingJob:
    """Create a completed processing job."""
    print("⚙️ Creating processing job record...")

    job = ProcessingJob(
        folder_id="1abc_demo_folder_xyz",
        status="completed",
        total_files=total_files,
        processed_files=total_files,
        progress_percentage=100,
        completed_at=datetime.utcnow(),
    )
    session.add(job)
    session.commit()

    print(f"✅ Created processing job (ID: {job.id})")
    return job


def print_summary(session, files, relationships, clusters_with_files, job):
    """Print summary of generated data."""
    print("\n" + "="*80)
    print("📊 DEMO DATA SUMMARY")
    print("="*80)

    # Files by cluster
    print("\n📁 FILES BY CLUSTER (discovered via DBSCAN):")
    for cluster, cluster_files in clusters_with_files:
        print(f"\n  🏷️  {cluster.label} ({len(cluster_files)} files)")
        for file in cluster_files:
            print(f"      • {file.name}")

    # Relationships
    print(f"\n🔗 SEMANTIC RELATIONSHIPS ({len(relationships)} total):")

    # Group relationships by similarity ranges
    high_sim = [r for r in relationships if r.similarity_score >= 0.7]
    medium_sim = [r for r in relationships if 0.5 <= r.similarity_score < 0.7]
    low_sim = [r for r in relationships if 0.3 <= r.similarity_score < 0.5]

    print(f"  • High similarity (≥0.7): {len(high_sim)} relationships")
    print(f"  • Medium similarity (0.5-0.7): {len(medium_sim)} relationships")
    print(f"  • Low similarity (0.3-0.5): {len(low_sim)} relationships")

    # Show top 5 relationships
    print("\n  Top 5 strongest relationships:")
    sorted_rels = sorted(relationships, key=lambda r: r.similarity_score, reverse=True)[:5]
    for rel in sorted_rels:
        source = session.query(File).filter(File.id == rel.source_file_id).first()
        target = session.query(File).filter(File.id == rel.target_file_id).first()
        print(f"    {rel.similarity_score:.3f} | {source.name}")
        print(f"           ↔ {target.name}")

    # Processing Job
    print(f"\n⚙️  PROCESSING JOB:")
    print(f"  • Status: {job.status}")
    print(f"  • Files processed: {job.processed_files}/{job.total_files}")
    print(f"  • Progress: {job.progress_percentage}%")
    print(f"  • Folder ID: {job.folder_id}")

    # Database stats
    print(f"\n📈 DATABASE STATISTICS:")
    print(f"  • Files: {session.query(File).count()}")
    print(f"  • Relationships: {session.query(FileRelationship).count()}")
    print(f"  • Clusters: {session.query(Cluster).count()}")
    print(f"  • File-Cluster mappings: {session.query(FileCluster).count()}")
    print(f"  • Processing Jobs: {session.query(ProcessingJob).count()}")

    print("\n" + "="*80)
    print("✨ Demo complete! The schema is populated with realistic data.")
    print("="*80)


def demonstrate_queries(session, files):
    """Demonstrate useful queries on the schema."""
    print("\n" + "="*80)
    print("🔍 EXAMPLE QUERIES")
    print("="*80)

    # Query 1: Find files in first cluster
    print("\n1️⃣  Find all files in the first cluster:")
    first_cluster = session.query(Cluster).filter(~Cluster.label.like("Unclustered%")).first()
    if first_cluster:
        print(f"   Cluster: {first_cluster.label}")
        cluster_files = session.query(File).join(FileCluster).filter(
            FileCluster.cluster_id == first_cluster.id
        ).all()
        for f in cluster_files:
            print(f"   • {f.name}")

    # Query 2: Find highly related documents
    print("\n2️⃣  Find all relationships with similarity > 0.7:")
    high_sim_rels = session.query(FileRelationship).filter(
        FileRelationship.similarity_score > 0.7
    ).all()
    print(f"   Found {len(high_sim_rels)} high-similarity relationships")

    # Query 3: Files by status
    print("\n3️⃣  Files by processing status:")
    status_counts = session.query(
        File.processing_status
    ).distinct().all()
    for (status,) in status_counts:
        count = session.query(File).filter(File.processing_status == status).count()
        print(f"   • {status}: {count} files")

    # Query 4: Find related documents for a specific file
    print("\n4️⃣  Find all documents related to 'Q4 Financial Report':")
    financial_report = session.query(File).filter(
        File.name.like("%Q4 Financial%")
    ).first()

    if financial_report:
        related_rels = session.query(FileRelationship).filter(
            (FileRelationship.source_file_id == financial_report.id) |
            (FileRelationship.target_file_id == financial_report.id)
        ).all()

        for rel in related_rels:
            other_id = (rel.target_file_id if rel.source_file_id == financial_report.id
                       else rel.source_file_id)
            other_file = session.query(File).filter(File.id == other_id).first()
            print(f"   • {other_file.name} (similarity: {rel.similarity_score:.3f})")

    print("\n" + "="*80)


def main():
    """Run the demo."""
    print("\n🚀 AIRelGraph Schema Demo\n")

    # Create engine
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Setup
        setup_database(engine)

        # Generate embeddings
        embeddings = generate_embeddings(MOCK_DOCUMENTS)

        # Create files
        files = create_files(session, MOCK_DOCUMENTS, embeddings)

        # Create relationships (lower threshold to capture more connections)
        relationships = create_relationships(session, files, embeddings, threshold=0.3)

        # Create clusters
        clusters_with_files = create_clusters(session, files, embeddings)

        # Create job
        job = create_processing_job(session, len(files))

        # Print summary
        print_summary(session, files, relationships, clusters_with_files, job)

        # Demonstrate queries
        demonstrate_queries(session, files)

    finally:
        session.close()


if __name__ == "__main__":
    main()
