"""
Graph Visualization Script for AIRelGraph.

Visualizes the document graph from the semantic_graph_demo database
using matplotlib and networkx.

Usage:
    python visualize_graph.py                    # Spring layout (default)
    python visualize_graph.py --layout circular  # Circular cluster layout
    python visualize_graph.py --stats            # Show statistics only
    python visualize_graph.py --save output.png  # Save to file
"""
import argparse
import os
import sys
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.models.file import File
from app.models.relationship import FileRelationship
from app.models.cluster import Cluster, FileCluster

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/semantic_graph_demo"
)


def load_graph_data(session):
    """Load graph data from database."""
    print("📊 Loading graph data from database...")

    # Load files
    files = session.query(File).all()
    file_dict = {str(f.id): f for f in files}

    # Load relationships
    relationships = session.query(FileRelationship).all()

    # Load clusters
    file_clusters = {}
    clusters = session.query(Cluster).all()

    for cluster in clusters:
        cluster_files = (
            session.query(File)
            .join(FileCluster)
            .filter(FileCluster.cluster_id == cluster.id)
            .all()
        )
        for f in cluster_files:
            file_clusters[str(f.id)] = (cluster.id, cluster.label)

    print(f"✅ Loaded {len(files)} files, {len(relationships)} relationships, {len(clusters)} clusters\n")

    return files, relationships, file_clusters, clusters


def build_networkx_graph(files, relationships, file_clusters):
    """Build NetworkX graph from database data."""
    G = nx.Graph()

    # Add nodes
    for file in files:
        cluster_id, cluster_label = file_clusters.get(str(file.id), (None, "Unclustered"))
        G.add_node(
            str(file.id),
            name=file.name,
            cluster_id=cluster_id,
            cluster_label=cluster_label,
        )

    # Add edges
    for rel in relationships:
        G.add_edge(
            str(rel.source_file_id),
            str(rel.target_file_id),
            weight=rel.shared_tag_count,
            similarity=rel.similarity_score,
        )

    return G


def get_cluster_colors(clusters):
    """Generate distinct colors for each cluster."""
    # Use tab20 colormap for up to 20 distinct colors
    cmap = plt.cm.get_cmap('tab20')
    colors = {}

    for idx, cluster in enumerate(clusters):
        colors[cluster.id] = cmap(idx % 20)

    # Gray for unclustered
    colors[None] = (0.7, 0.7, 0.7, 1.0)

    return colors


def visualize_spring_layout(G, file_clusters, cluster_colors, output_file=None):
    """Visualize graph with spring (force-directed) layout."""
    print("🎨 Generating spring layout visualization...")

    plt.figure(figsize=(20, 16))

    # Compute layout
    pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)

    # Draw nodes by cluster
    for cluster_id, color in cluster_colors.items():
        nodes = [n for n in G.nodes() if G.nodes[n]['cluster_id'] == cluster_id]
        if nodes:
            node_sizes = [100 + 50 * G.degree(n) for n in nodes]
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=nodes,
                node_color=[color],
                node_size=node_sizes,
                alpha=0.8,
            )

    # Draw edges
    nx.draw_networkx_edges(
        G, pos,
        edge_color='gray',
        width=[0.5 + e[2]['weight'] * 0.3 for e in G.edges(data=True)],
        alpha=0.3,
    )

    # Draw labels (for small graphs)
    if len(G.nodes()) <= 20:
        labels = {n: G.nodes[n]['name'][:15] for n in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels, font_size=8)

    # Create legend
    legend_patches = []
    cluster_labels_seen = set()

    for node in G.nodes():
        cluster_id = G.nodes[node]['cluster_id']
        cluster_label = G.nodes[node]['cluster_label']

        if cluster_label not in cluster_labels_seen:
            cluster_labels_seen.add(cluster_label)
            color = cluster_colors.get(cluster_id, (0.7, 0.7, 0.7, 1.0))
            legend_patches.append(mpatches.Patch(color=color, label=cluster_label))

    plt.legend(handles=legend_patches, loc='upper left', fontsize=10)

    plt.title("Document Graph - Spring Layout\n(Node size = connections, Edge thickness = shared tags)",
              fontsize=16, pad=20)
    plt.axis('off')
    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"✅ Saved to {output_file}")
    else:
        plt.show()

    plt.close()


def visualize_circular_layout(G, clusters, cluster_colors, output_file=None):
    """Visualize graph with circular cluster layout."""
    print("🎨 Generating circular cluster layout...")

    plt.figure(figsize=(20, 16))

    # Group nodes by cluster
    cluster_nodes = {}
    for node in G.nodes():
        cluster_id = G.nodes[node]['cluster_id']
        if cluster_id not in cluster_nodes:
            cluster_nodes[cluster_id] = []
        cluster_nodes[cluster_id].append(node)

    # Position clusters in circles
    pos = {}
    num_clusters = len(cluster_nodes)

    for idx, (cluster_id, nodes) in enumerate(cluster_nodes.items()):
        # Cluster center on a large circle
        angle = 2 * 3.14159 * idx / num_clusters
        center_x = 10 * (1 + 0.5 * num_clusters) * (0.5 + 0.5 * idx / max(num_clusters - 1, 1))
        center_y = 10 * (1 + 0.5 * num_clusters) * (0.5 + 0.5 * idx / max(num_clusters - 1, 1))

        # Arrange nodes in a circle around center
        radius = 2 + 0.5 * len(nodes)
        for node_idx, node in enumerate(nodes):
            node_angle = 2 * 3.14159 * node_idx / len(nodes)
            pos[node] = (
                center_x + radius * plt.np.cos(node_angle),
                center_y + radius * plt.np.sin(node_angle),
            )

    # Draw nodes by cluster
    for cluster_id, color in cluster_colors.items():
        nodes = [n for n in G.nodes() if G.nodes[n]['cluster_id'] == cluster_id]
        if nodes:
            node_sizes = [100 + 50 * G.degree(n) for n in nodes]
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=nodes,
                node_color=[color],
                node_size=node_sizes,
                alpha=0.8,
            )

    # Draw edges
    nx.draw_networkx_edges(
        G, pos,
        edge_color='gray',
        width=[0.5 + e[2]['weight'] * 0.3 for e in G.edges(data=True)],
        alpha=0.2,
    )

    # Create legend
    legend_patches = []
    cluster_labels_seen = set()

    for node in G.nodes():
        cluster_label = G.nodes[node]['cluster_label']
        cluster_id = G.nodes[node]['cluster_id']

        if cluster_label not in cluster_labels_seen:
            cluster_labels_seen.add(cluster_label)
            color = cluster_colors.get(cluster_id, (0.7, 0.7, 0.7, 1.0))
            legend_patches.append(mpatches.Patch(color=color, label=cluster_label))

    plt.legend(handles=legend_patches, loc='upper left', fontsize=10)

    plt.title("Document Graph - Circular Cluster Layout\n(Each cluster in its own circle)",
              fontsize=16, pad=20)
    plt.axis('off')
    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"✅ Saved to {output_file}")
    else:
        plt.show()

    plt.close()


def show_statistics(G, clusters, relationships):
    """Show graph statistics with charts."""
    print("📊 Generating statistics visualization...")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # 1. Documents per cluster
    cluster_sizes = {}
    for node in G.nodes():
        cluster_label = G.nodes[node]['cluster_label']
        cluster_sizes[cluster_label] = cluster_sizes.get(cluster_label, 0) + 1

    sorted_clusters = sorted(cluster_sizes.items(), key=lambda x: x[1], reverse=True)
    cluster_names = [c[0][:30] for c in sorted_clusters]  # Truncate long names
    cluster_counts = [c[1] for c in sorted_clusters]

    axes[0, 0].barh(cluster_names, cluster_counts, color='steelblue')
    axes[0, 0].set_xlabel('Number of Documents', fontsize=12)
    axes[0, 0].set_title('Documents per Cluster', fontsize=14, pad=10)
    axes[0, 0].invert_yaxis()

    # 2. Relationship distribution
    shared_tag_counts = [r.shared_tag_count for r in relationships]
    axes[0, 1].hist(shared_tag_counts, bins=range(min(shared_tag_counts), max(shared_tag_counts) + 2),
                    color='coral', edgecolor='black', alpha=0.7)
    axes[0, 1].set_xlabel('Shared Tag Count', fontsize=12)
    axes[0, 1].set_ylabel('Number of Relationships', fontsize=12)
    axes[0, 1].set_title('Distribution of Shared Tags', fontsize=14, pad=10)

    # 3. Degree distribution
    degrees = [G.degree(n) for n in G.nodes()]
    axes[1, 0].hist(degrees, bins=20, color='mediumseagreen', edgecolor='black', alpha=0.7)
    axes[1, 0].set_xlabel('Node Degree (Number of Connections)', fontsize=12)
    axes[1, 0].set_ylabel('Number of Documents', fontsize=12)
    axes[1, 0].set_title('Connection Distribution', fontsize=14, pad=10)

    # 4. Summary statistics (text)
    axes[1, 1].axis('off')

    avg_degree = sum(degrees) / len(degrees) if degrees else 0
    avg_shared_tags = sum(shared_tag_counts) / len(shared_tag_counts) if shared_tag_counts else 0

    stats_text = f"""
    GRAPH STATISTICS

    Nodes (Documents):     {len(G.nodes())}
    Edges (Relationships): {len(G.edges())}
    Clusters:              {len(clusters)}

    Avg Connections per Doc:  {avg_degree:.2f}
    Avg Shared Tags:          {avg_shared_tags:.2f}

    Largest Cluster:       {max(cluster_counts) if cluster_counts else 0} docs
    Smallest Cluster:      {min(cluster_counts) if cluster_counts else 0} docs

    Graph Density:         {nx.density(G):.4f}
    """

    axes[1, 1].text(0.1, 0.5, stats_text, fontsize=12, verticalalignment='center',
                    family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    plt.suptitle('Document Graph Statistics', fontsize=16, y=0.98)
    plt.tight_layout()

    if hasattr(show_statistics, 'output_file') and show_statistics.output_file:
        plt.savefig(show_statistics.output_file, dpi=150, bbox_inches='tight')
        print(f"✅ Saved to {show_statistics.output_file}")
    else:
        plt.show()

    plt.close()


def main():
    """Main visualization function."""
    parser = argparse.ArgumentParser(description="Visualize AIRelGraph document graph")
    parser.add_argument('--layout', choices=['spring', 'circular'], default='spring',
                       help='Layout algorithm (default: spring)')
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics instead of graph')
    parser.add_argument('--save', type=str, metavar='FILE',
                       help='Save to file instead of showing')
    parser.add_argument('--all', action='store_true',
                       help='Generate all visualizations (spring, circular, stats)')

    args = parser.parse_args()

    # Connect to database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Load data
        files, relationships, file_clusters, clusters = load_graph_data(session)

        if not files:
            print("❌ No files found in database. Run a demo first!")
            return

        # Build graph
        G = build_networkx_graph(files, relationships, file_clusters)

        # Get colors
        cluster_colors = get_cluster_colors(clusters)

        # Generate visualizations
        if args.all:
            print("\n🎨 Generating all visualizations...\n")
            visualize_spring_layout(G, file_clusters, cluster_colors, 'graph_spring.png')
            visualize_circular_layout(G, clusters, cluster_colors, 'graph_circular.png')
            show_statistics.output_file = 'graph_stats.png'
            show_statistics(G, clusters, relationships)
            print("\n✨ All visualizations complete!")
            print("   - graph_spring.png")
            print("   - graph_circular.png")
            print("   - graph_stats.png\n")
        elif args.stats:
            show_statistics.output_file = args.save
            show_statistics(G, clusters, relationships)
        elif args.layout == 'circular':
            visualize_circular_layout(G, clusters, cluster_colors, args.save)
        else:
            visualize_spring_layout(G, file_clusters, cluster_colors, args.save)

    finally:
        session.close()


if __name__ == "__main__":
    main()
