#!/bin/bash
# Quick script to run the schema demo

set -e

echo "🚀 Running AIRelGraph Schema Demo"
echo ""

# Check if database exists, if not create it
echo "📦 Setting up demo database..."
docker exec ai-rel-graph-postgres psql -U postgres -c "CREATE DATABASE semantic_graph_demo;" 2>/dev/null || echo "✓ Database already exists"

# Run the demo
echo ""
echo "🎬 Running demo script..."
echo ""
docker exec ai-rel-graph-backend python demo_schema.py

echo ""
echo "✨ Demo complete!"
echo ""
echo "To explore the database:"
echo "  docker exec -it ai-rel-graph-postgres psql -U postgres -d semantic_graph_demo"
echo ""
echo "To reset the demo:"
echo "  docker exec ai-rel-graph-postgres psql -U postgres -c \"DROP DATABASE semantic_graph_demo; CREATE DATABASE semantic_graph_demo;\""
