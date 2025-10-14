"""
Unified Demo Script for AIRelGraph.

Demonstrates ML-based semantic tag extraction with automatic consolidation.
Uses KeyBERT for semantic tag extraction and consolidates similar tags.

Usage:
    python demo.py                          # 11 realistic synthetic documents
    python demo.py --large                  # 100 synthetic documents
    python demo.py --kaggle 50              # 50 real Kaggle PDFs
    python demo.py --min-tags 2             # Custom minimum shared tags
    python demo.py --no-consolidate         # Skip tag consolidation step
"""
import argparse
import os
import sys
import time
import tracemalloc
import re
import warnings
from pathlib import Path
from typing import List, Dict

import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.models.file import File
from app.core.database import Base
from app.services.semantic import SemanticProcessingService


# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/semantic_graph_demo"
)


def setup_database(engine):
    """Create fresh database."""
    print("🔧 Setting up database...")
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        # No longer need pgvector extension for tag-based system
        conn.commit()
    Base.metadata.create_all(engine)
    print("✅ Database ready\n")


def generate_synthetic_documents(num_docs: int = 100) -> List[Dict]:
    """Generate synthetic documents for testing."""
    print(f"📝 Generating {num_docs} synthetic documents...")

    templates = [
        "machine learning neural networks deep learning artificial intelligence",
        "financial analysis quarterly report budget revenue profit margins",
        "software development python programming code review best practices",
        "medical research clinical trials patient outcomes treatment protocols",
        "marketing strategy customer engagement social media digital advertising",
        "human resources employee benefits workplace policies recruitment",
        "legal compliance regulations contract review intellectual property",
        "environmental sustainability climate change renewable energy conservation",
    ]

    documents = []
    for i in range(num_docs):
        template_idx = i % len(templates)
        base_text = templates[template_idx]

        # Add variation
        variation = f" Document {i+1} contains additional information about {base_text.split()[0]}. "
        variation += f"This section discusses key aspects related to {base_text.split()[1]}. "
        variation += f"Further details about {base_text.split()[-1]} are provided below."

        full_text = base_text + variation + " " + base_text

        documents.append({
            "google_drive_id": f"synthetic_{i+1:06d}",
            "name": f"document_{i+1:06d}.txt",
            "mime_type": "text/plain",
            "size_bytes": len(full_text),
            "text_content": full_text,
        })

    print(f"✅ Generated {len(documents)} documents\n")
    return documents


def generate_realistic_documents() -> List[Dict]:
    """Generate 11 realistic documents for demo."""
    print("📝 Generating 11 realistic documents...")

    documents = [
        {
            "name": "neural_networks_intro.pdf",
            "mime_type": "application/pdf",
            "text_content": "Neural networks are computational models inspired by biological neural networks. "
                          "Deep learning uses multiple layers to progressively extract higher-level features. "
                          "Backpropagation algorithm is used to train neural networks by adjusting weights.",
        },
        {
            "name": "deep_learning_applications.pdf",
            "mime_type": "application/pdf",
            "text_content": "Deep learning has revolutionized computer vision and natural language processing. "
                          "Convolutional neural networks excel at image recognition tasks. "
                          "Recurrent neural networks are effective for sequential data processing.",
        },
        {
            "name": "machine_learning_overview.pdf",
            "mime_type": "application/pdf",
            "text_content": "Machine learning enables computers to learn from data without explicit programming. "
                          "Supervised learning uses labeled data to train models. "
                          "Unsupervised learning discovers patterns in unlabeled data.",
        },
        {
            "name": "q4_financial_report.xlsx",
            "mime_type": "application/vnd.ms-excel",
            "text_content": "Q4 Financial Report: Revenue increased 15% year-over-year. "
                          "Operating expenses remained flat. Net profit margin improved to 22%. "
                          "Cash flow from operations exceeded projections by 8%.",
        },
        {
            "name": "budget_analysis_2024.xlsx",
            "mime_type": "application/vnd.ms-excel",
            "text_content": "Budget Analysis 2024: Total allocated budget is $2.5M. "
                          "Major expenses include salaries (60%), infrastructure (25%), and marketing (15%). "
                          "Contingency fund set at 10% of total budget.",
        },
        {
            "name": "quarterly_earnings.pdf",
            "mime_type": "application/pdf",
            "text_content": "Quarterly earnings exceeded analyst expectations. "
                          "Revenue growth driven by strong product sales. "
                          "Operating margin improved due to cost optimization initiatives.",
        },
        {
            "name": "team_meeting_notes.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text_content": "Team Meeting Notes: Discussed Q4 strategy and roadmap priorities. "
                          "Action items include finalizing product specifications and updating project timeline. "
                          "Next meeting scheduled for next week.",
        },
        {
            "name": "strategy_document.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text_content": "Strategic Planning Document: Q4 objectives focus on market expansion. "
                          "Key initiatives include product launch and partnership development. "
                          "Success metrics defined for each strategic pillar.",
        },
        {
            "name": "employee_handbook.pdf",
            "mime_type": "application/pdf",
            "text_content": "Employee Handbook: Company policies cover workplace conduct and benefits. "
                          "PTO policy allows 20 days per year. Health insurance coverage begins after 30 days. "
                          "Performance reviews conducted bi-annually.",
        },
        {
            "name": "hr_policies_update.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text_content": "HR Policies Update: Remote work policy updated to allow 3 days per week. "
                          "New parental leave benefits extended to 16 weeks. "
                          "Employee wellness program expanded with mental health resources.",
        },
        {
            "name": "python_coding_standards.md",
            "mime_type": "text/markdown",
            "text_content": "Python Coding Standards: Follow PEP 8 style guidelines. "
                          "Use type hints for function signatures. Write docstrings for all public functions. "
                          "Maintain test coverage above 80%. Use black for code formatting.",
        },
    ]

    for i, doc in enumerate(documents):
        doc["google_drive_id"] = f"realistic_{i+1:03d}"
        doc["size_bytes"] = len(doc["text_content"])

    print(f"✅ Generated {len(documents)} realistic documents\n")
    return documents


def download_kaggle_pdfs(max_files: int) -> List[Dict]:
    """Download and process Kaggle PDF dataset."""
    print(f"📦 Downloading Kaggle PDF dataset...")

    try:
        import kagglehub
        path = kagglehub.dataset_download("manisha717/dataset-of-pdf-files")
        print(f"✅ Dataset downloaded to: {path}\n")
    except Exception as e:
        print(f"❌ Error downloading dataset: {e}")
        print("   Make sure you have Kaggle API credentials set up.")
        print("   See: https://www.kaggle.com/docs/api")
        sys.exit(1)

    print(f"📄 Loading PDF files...")

    # Suppress PyPDF2 warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="PyPDF2")
    import logging
    logging.getLogger("PyPDF2").setLevel(logging.ERROR)

    from PyPDF2 import PdfReader

    dataset_dir = Path(path)
    all_pdfs = list(dataset_dir.rglob("*.pdf"))

    if not all_pdfs:
        print("❌ No PDF files found in dataset")
        sys.exit(1)

    if max_files:
        all_pdfs = all_pdfs[:max_files]

    print(f"   Found {len(all_pdfs)} PDF files")

    documents = []
    for i, pdf_path in enumerate(all_pdfs, 1):
        print(f"   Extracting {i}/{len(all_pdfs)}: {pdf_path.name[:40]}", end="\r")

        try:
            reader = PdfReader(str(pdf_path), strict=False)
            text_parts = []

            max_pages = min(30, len(reader.pages))
            for page_num in range(max_pages):
                try:
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        # Clean text
                        page_text = re.sub(r'\s+', ' ', page_text)
                        page_text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', page_text)
                        text_parts.append(page_text)
                except:
                    continue

            full_text = " ".join(text_parts)
            full_text = " ".join(full_text.split())

            # Limit text length
            if len(full_text) > 10000:
                full_text = full_text[:7000] + " " + full_text[-3000:]

            if len(full_text) < 100:
                continue

            documents.append({
                "google_drive_id": f"kaggle_pdf_{i:06d}",
                "name": pdf_path.name,
                "mime_type": "application/pdf",
                "size_bytes": pdf_path.stat().st_size,
                "text_content": full_text,
            })
        except:
            continue

    print(f"\n✅ Loaded {len(documents)} PDFs with valid text content\n")
    return documents


def create_files(session, documents: List[Dict]) -> List[File]:
    """Create file records in database."""
    print(f"💾 Creating {len(documents)} file records...")
    start_time = time.time()

    files = []
    for doc in documents:
        file = File(
            google_drive_id=doc["google_drive_id"],
            name=doc["name"],
            mime_type=doc["mime_type"],
            size_bytes=doc["size_bytes"],
            text_content=doc["text_content"],
            processing_status="pending",
        )
        files.append(file)
        session.add(file)

    session.commit()

    for file in files:
        session.refresh(file)

    elapsed = time.time() - start_time
    print(f"✅ Created {len(files)} files in {elapsed:.2f}s\n")

    return files


def print_summary(
    num_docs: int,
    embedding_time: float,
    relationship_time: float,
    clustering_time: float,
    num_relationships: int,
    num_clusters: int,
    peak_memory_mb: float,
    clusters_with_files: List,
    data_type: str,
    num_consolidated: int = 0,
):
    """Print processing summary."""
    total_time = embedding_time + relationship_time + clustering_time

    print("\n" + "="*80)
    print(f"⚡ ML-BASED PROCESSING SUMMARY - {data_type}")
    print("="*80)

    print(f"\n📊 Dataset:")
    print(f"   Documents processed: {num_docs}")

    print(f"\n⏱️  Processing Times:")
    print(f"   • ML tag extraction:         {embedding_time:8.2f}s  ({num_docs/embedding_time:6.1f} docs/sec)")
    if num_consolidated > 0:
        print(f"   • Tag consolidation:         (included in extraction)")
    print(f"   • Relationship creation:     {relationship_time:8.2f}s")
    print(f"   • Community detection:       {clustering_time:8.2f}s")
    print(f"   • TOTAL:                     {total_time:8.2f}s")

    print(f"\n🔗 Relationship Graph:")
    max_possible = (num_docs * (num_docs - 1)) // 2
    density = (num_relationships / max_possible * 100) if max_possible > 0 else 0
    print(f"   • Relationships created:  {num_relationships:,}")
    print(f"   • Graph density:          {density:.2f}%")
    print(f"   • Avg connections/doc:    {(num_relationships * 2 / num_docs):.1f}")

    print(f"\n🎯 Community-Based Clusters:")
    sizes = [len(files) for _, files in clusters_with_files]
    print(f"   • Communities found:      {num_clusters}")
    if sizes:
        print(f"   • Smallest cluster:       {min(sizes)} docs")
        print(f"   • Largest cluster:        {max(sizes)} docs")
        print(f"   • Average size:           {np.mean(sizes):.1f} docs")

    print(f"\n💾 Memory Usage:")
    print(f"   • Peak memory:            {peak_memory_mb:.1f} MB")

    print("\n" + "="*80)


def print_clusters(clusters_with_files: List, top_n: int = 10):
    """Print discovered clusters."""
    print("\n" + "="*80)
    print(f"📚 DISCOVERED COMMUNITIES (Top {min(top_n, len(clusters_with_files))})")
    print("="*80)

    # Sort by size
    sorted_clusters = sorted(clusters_with_files, key=lambda x: len(x[1]), reverse=True)

    for i, (cluster, cluster_files) in enumerate(sorted_clusters[:top_n], 1):
        print(f"\n   {i}. 📂 {cluster.label}")

        # Show first 3 files
        print(f"      Files: {', '.join([f.name[:30] for f in cluster_files[:3]])}")
        if len(cluster_files) > 3:
            print(f"             ... and {len(cluster_files) - 3} more")

        # Show content sample
        if cluster_files[0].text_content:
            sample = cluster_files[0].text_content[:100].replace("\n", " ")
            print(f"      Sample: '{sample}...'")

    print("\n" + "="*80)


def main():
    """Run demo."""
    parser = argparse.ArgumentParser(description="AIRelGraph ML-Based Tag Processing Demo")
    parser.add_argument("--large", action="store_true", help="Generate 100 synthetic documents")
    parser.add_argument("--kaggle", type=int, metavar="N", help="Process N real Kaggle PDFs")
    parser.add_argument("--min-tags", type=int, default=2, help="Minimum shared tags for relationships (default: 2)")
    parser.add_argument("--no-consolidate", action="store_true", help="Skip tag consolidation step")
    parser.add_argument("--consolidation-threshold", type=float, default=0.6, help="Similarity threshold for tag consolidation (default: 0.6)")

    args = parser.parse_args()

    # Determine dataset type
    if args.kaggle:
        data_type = f"Real Kaggle PDFs (max {args.kaggle})"
        documents = download_kaggle_pdfs(args.kaggle)
    elif args.large:
        data_type = "Synthetic Documents (100)"
        documents = generate_synthetic_documents(100)
    else:
        data_type = "Realistic Documents (11)"
        documents = generate_realistic_documents()

    print("\n" + "="*80)
    print(f"🚀 AIRelGraph ML Demo - {data_type}")
    print(f"   ML Model: KeyBERT (all-MiniLM-L6-v2)")
    print(f"   Minimum Shared Tags: {args.min_tags}")
    print(f"   Tag Consolidation: {'Enabled' if not args.no_consolidate else 'Disabled'}")
    if not args.no_consolidate:
        print(f"   Consolidation Threshold: {args.consolidation_threshold}")
    print("="*80 + "\n")

    tracemalloc.start()

    # Setup database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        setup_database(engine)

        # Create file records
        files = create_files(session, documents)

        # Initialize ML-based tag processing service
        min_shared_tags = args.min_tags
        service = SemanticProcessingService(
            min_shared_tags=min_shared_tags,
            consolidation_threshold=args.consolidation_threshold,
        )

        # Run full ML processing pipeline
        print("🤖 Starting ML-based tag extraction and processing...")
        start_time = time.time()
        results = service.process_documents(
            session=session,
            files=files,
            min_shared=min_shared_tags,
            show_progress=True,
            consolidate_tags=not args.no_consolidate,
        )
        total_processing_time = time.time() - start_time

        # Approximate timing breakdown (for display purposes)
        tag_time = total_processing_time * 0.5  # Tag extraction is the heaviest
        relationship_time = total_processing_time * 0.3
        clustering_time = total_processing_time * 0.2

        # Get memory usage
        current, peak = tracemalloc.get_traced_memory()
        peak_memory_mb = peak / 1024 / 1024
        tracemalloc.stop()

        # Print results
        num_consolidated = len(results.get("consolidated_tags", {}))
        print_summary(
            num_docs=len(documents),
            embedding_time=tag_time,
            relationship_time=relationship_time,
            clustering_time=clustering_time,
            num_relationships=len(results["relationships"]),
            num_clusters=len(results["clusters"]),
            peak_memory_mb=peak_memory_mb,
            clusters_with_files=results["clusters"],
            data_type=data_type,
            num_consolidated=num_consolidated,
        )

        # Show tag consolidation results
        if num_consolidated > 0:
            print("\n" + "="*80)
            print(f"🔗 TAG CONSOLIDATION RESULTS")
            print("="*80)
            print(f"\n   Consolidated {num_consolidated} similar tags")
            print(f"\n   Examples (child → parent):")
            for child, parent in list(results["consolidated_tags"].items())[:5]:
                print(f"      • {child} → {parent}")
            if num_consolidated > 5:
                print(f"      ... and {num_consolidated - 5} more")

        print_clusters(results["clusters"], top_n=10)

        print("\n✨ Demo complete! Database: semantic_graph_demo")
        print("   Note: Tags are ML-extracted and semantically consolidated\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()
