"""Tag hierarchy service for building multi-level tag structures."""
import json
import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class TagHierarchyService:
    """Service for building and managing hierarchical tag structures.

    This service analyzes tag distribution and automatically creates
    parent-child tag relationships when tags become too broad.
    """

    def __init__(
        self,
        split_threshold: int = 10,
        cross_cutting_threshold: int = 5,
        api_key: Optional[str] = None,
    ):
        """Initialize the tag hierarchy service.

        Args:
            split_threshold: Minimum documents per tag to consider splitting (default: 10)
            cross_cutting_threshold: Minimum docs with tag combo to create cross-cutting tag (default: 5)
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
        """
        self.split_threshold = split_threshold
        self.cross_cutting_threshold = cross_cutting_threshold
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"

    def analyze_tag_distribution(
        self, nodes: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Count how many documents have each tag.

        Args:
            nodes: List of graph nodes with tags

        Returns:
            Dictionary mapping tag -> document count
        """
        tag_counts = Counter()

        for node in nodes:
            tags = node.get("tags", [])
            # Handle both old flat structure and new hierarchical structure
            if isinstance(tags, list):
                tag_counts.update(tags)
            elif isinstance(tags, dict):
                # New hierarchical structure
                low_level = tags.get("low_level", [])
                tag_counts.update(low_level)

        logger.info(f"Analyzed {len(nodes)} documents, found {len(tag_counts)} unique tags")
        return dict(tag_counts)

    def should_split_tag(
        self, tag: str, count: int, existing_hierarchy: Dict[str, Any]
    ) -> bool:
        """Determine if a tag should be split into sub-tags.

        Args:
            tag: The tag to check
            count: Number of documents with this tag
            existing_hierarchy: Current tag hierarchy (to avoid re-splitting)

        Returns:
            True if tag should be split
        """
        # Don't split if below threshold
        if count < self.split_threshold:
            return False

        # Don't split if already a parent tag
        if tag in existing_hierarchy and existing_hierarchy[tag].get("type") == "high_level":
            return False

        logger.info(f"Tag '{tag}' has {count} documents (>= {self.split_threshold}), considering split")
        return True

    def suggest_sub_tags(
        self,
        parent_tag: str,
        documents: List[Dict[str, Any]],
        max_sub_tags: int = 4,
    ) -> Optional[List[str]]:
        """Use LLM to suggest sub-categories for a broad tag.

        Args:
            parent_tag: The tag to split
            documents: Documents that have this tag
            max_sub_tags: Maximum number of sub-tags to create

        Returns:
            List of sub-tag names, or None if LLM says not to split
        """
        # Sample up to 15 documents for LLM analysis
        sample_docs = documents[:15] if len(documents) > 15 else documents

        # Build prompt with summaries
        doc_summaries = []
        for i, doc in enumerate(sample_docs, 1):
            title = doc.get("title", "Untitled")
            summary = doc.get("summary", "")
            doc_summaries.append(f"{i}. {title}\n   Summary: {summary}")

        summaries_text = "\n".join(doc_summaries)

        system_prompt = f"""You are a document categorization expert. Your task is to analyze whether a tag should be split into more specific sub-categories.

You will be given:
1. A current tag: "{parent_tag}"
2. Sample documents that have this tag
3. The number of total documents with this tag: {len(documents)}

Your job is to determine:
- Should this tag be split? (Some tags are fine as-is, even with many documents)
- If yes, what are 2-{max_sub_tags} more specific sub-categories?

**When NOT to split:**
- Document type tags: "meeting notes", "design document", "final report"
- Language tags: "Japanese", "Spanish", "French"
- Time period tags: "Q3 2024", "2023", "Fall 2024"
- Already specific tags: "camera calibration", "humanitarian data ethics"
- Tags where documents are naturally diverse and don't cluster into themes

**When TO split:**
- Broad domain tags with distinct subcategories: "software engineering" → ["web development", "embedded systems", "machine learning"]
- General tags that cover multiple sub-fields: "finance" → ["corporate finance", "personal banking", "investment"]
- Industry tags with specializations: "healthcare" → ["clinical research", "hospital administration", "medical devices"]

**Requirements for sub-tags:**
- Must be mutually exclusive where possible
- Should be more specific than the parent tag
- Use lowercase, multi-word format (e.g., "machine learning" not "Machine Learning")
- Should cover the main themes in the sample documents
- Aim for 2-4 sub-tags (not just 2, not more than {max_sub_tags})

Return JSON:
{{
  "should_split": true/false,
  "reason": "Brief explanation of decision",
  "sub_tags": ["specific tag 1", "specific tag 2"] // Empty array if should_split=false
}}

Example 1 (SHOULD split):
Tag: "software engineering", 15 documents
Documents cover: React apps, embedded C firmware, ML models, DevOps pipelines
Response: {{"should_split": true, "reason": "Documents span distinct software domains", "sub_tags": ["web development", "embedded systems", "machine learning", "devops"]}}

Example 2 (SHOULD NOT split):
Tag: "meeting notes", 20 documents
Documents cover: Various meeting types across different topics
Response: {{"should_split": false, "reason": "Document type tag - naturally diverse content", "sub_tags": []}}

Example 3 (SHOULD NOT split):
Tag: "computer vision", 12 documents
Documents cover: Various CV topics but all related to vision
Response: {{"should_split": false, "reason": "Already specific technical field - cohesive theme", "sub_tags": []}}
"""

        user_prompt = f"""Tag to analyze: "{parent_tag}"
Total documents with this tag: {len(documents)}

Sample document summaries:
{summaries_text}

Should this tag be split into sub-categories? If yes, suggest the sub-tags."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=300,
            )

            result = json.loads(response.choices[0].message.content)

            should_split = result.get("should_split", False)
            sub_tags = result.get("sub_tags", [])
            reason = result.get("reason", "")

            if should_split and sub_tags:
                logger.info(
                    f"LLM suggests splitting '{parent_tag}' into {len(sub_tags)} sub-tags: {sub_tags}. "
                    f"Reason: {reason}"
                )
                return sub_tags
            else:
                logger.info(f"LLM suggests NOT splitting '{parent_tag}'. Reason: {reason}")
                return None

        except Exception as e:
            logger.error(f"Failed to suggest sub-tags for '{parent_tag}': {e}")
            return None

    def reassign_documents_to_subtags(
        self,
        parent_tag: str,
        sub_tags: List[str],
        documents: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        """Use LLM to reassign documents from parent tag to sub-tags.

        Args:
            parent_tag: Original broad tag
            sub_tags: New specific sub-tags
            documents: Documents that currently have parent_tag

        Returns:
            Dictionary mapping document_id -> list of selected sub-tags (or empty list to keep none)
        """
        reassignments = {}

        # Process in batches to avoid token limits
        batch_size = 10
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            try:
                batch_result = self._reassign_batch(parent_tag, sub_tags, batch)
                reassignments.update(batch_result)
            except Exception as e:
                logger.error(f"Failed to reassign batch {i}-{i+len(batch)}: {e}")
                # On error, assign no sub-tags (safer than guessing)
                for doc in batch:
                    reassignments[doc["id"]] = []

        logger.info(
            f"Reassigned {len(documents)} documents from '{parent_tag}' to sub-tags. "
            f"{sum(1 for tags in reassignments.values() if tags)} documents received sub-tags."
        )

        return reassignments

    def _reassign_batch(
        self,
        parent_tag: str,
        sub_tags: List[str],
        documents: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        """Reassign a batch of documents using LLM."""
        # Build document descriptions
        doc_descriptions = []
        for doc in documents:
            title = doc.get("title", "Untitled")
            summary = doc.get("summary", "")
            doc_descriptions.append({
                "id": doc["id"],
                "title": title,
                "summary": summary,
            })

        system_prompt = f"""You are a document categorization expert. You will reassign documents from a broad tag to more specific sub-tags.

Original tag: "{parent_tag}"
New sub-tags: {', '.join(f'"{tag}"' for tag in sub_tags)}

For each document, select which sub-tag(s) apply based on the title and summary.

Rules:
- A document can have 0, 1, or multiple sub-tags (if it spans multiple sub-categories)
- If none of the sub-tags fit well, return empty array (better to have no tag than wrong tag)
- Be selective - only assign sub-tags that are clearly relevant

Return JSON array:
[
  {{"id": "doc_id_1", "selected_tags": ["sub tag 1"]}},
  {{"id": "doc_id_2", "selected_tags": []}},
  {{"id": "doc_id_3", "selected_tags": ["sub tag 1", "sub tag 2"]}}
]
"""

        user_prompt = f"""Documents to reassign:
{json.dumps(doc_descriptions, indent=2)}

For each document, select the appropriate sub-tag(s) from: {sub_tags}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1000,
        )

        result = json.loads(response.choices[0].message.content)

        # Parse result (handle both array and object with "reassignments" key)
        if isinstance(result, list):
            assignments = result
        else:
            assignments = result.get("reassignments", result.get("documents", []))

        # Convert to dict
        reassignments = {}
        for item in assignments:
            doc_id = item.get("id")
            selected = item.get("selected_tags", [])
            if doc_id:
                reassignments[doc_id] = selected

        return reassignments

    def find_cross_cutting_tags(
        self,
        nodes: List[Dict[str, Any]],
        high_level_tags: Set[str],
    ) -> List[Tuple[str, str, int]]:
        """Find pairs of high-level tags that frequently appear together.

        Args:
            nodes: Graph nodes with hierarchical tags
            high_level_tags: Set of current high-level tags

        Returns:
            List of (tag1, tag2, count) tuples where count >= cross_cutting_threshold
        """
        # Count tag pair occurrences
        pair_counts = Counter()

        for node in nodes:
            tags = node.get("tags", {})
            node_high_tags = tags.get("high_level", []) if isinstance(tags, dict) else []

            # Find all pairs of high-level tags on this document
            node_high_tags = list(set(node_high_tags))  # Deduplicate
            if len(node_high_tags) >= 2:
                # Only consider pairs (not triplets or more)
                for i in range(len(node_high_tags)):
                    for j in range(i + 1, len(node_high_tags)):
                        pair = tuple(sorted([node_high_tags[i], node_high_tags[j]]))
                        pair_counts[pair] += 1

        # Filter by threshold
        cross_cutting = [
            (tag1, tag2, count)
            for (tag1, tag2), count in pair_counts.items()
            if count >= self.cross_cutting_threshold
        ]

        cross_cutting.sort(key=lambda x: x[2], reverse=True)  # Sort by count

        logger.info(
            f"Found {len(cross_cutting)} cross-cutting tag pairs "
            f"(threshold: {self.cross_cutting_threshold})"
        )

        return cross_cutting

    def create_cross_cutting_tag(
        self, tag1: str, tag2: str, documents: List[Dict[str, Any]]
    ) -> str:
        """Create a combined low-level tag from two high-level tags.

        Args:
            tag1: First high-level tag
            tag2: Second high-level tag
            documents: Documents that have both tags

        Returns:
            Name of the cross-cutting low-level tag
        """
        # Simple approach: combine the tag names
        # Example: "banking" + "government" -> "government banking"
        # Use alphabetical order for consistency
        combined = f"{tag1} {tag2}" if tag1 < tag2 else f"{tag2} {tag1}"

        logger.info(
            f"Created cross-cutting tag '{combined}' from '{tag1}' + '{tag2}' "
            f"({len(documents)} documents)"
        )

        return combined

    def build_hierarchy(
        self, nodes: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Build complete tag hierarchy from flat-tagged nodes.

        This is the main orchestration method that:
        1. Analyzes tag distribution
        2. Identifies tags to split
        3. Suggests and applies sub-tags
        4. Finds cross-cutting combinations
        5. Restructures nodes with hierarchical tags

        Args:
            nodes: Graph nodes with flat tags

        Returns:
            Tuple of (updated_nodes, tag_hierarchy_metadata)
        """
        logger.info("=" * 80)
        logger.info("BUILDING TAG HIERARCHY")
        logger.info("=" * 80)

        # Step 1: Analyze current tag distribution
        logger.info("\n[Step 1/5] Analyzing tag distribution...")
        tag_counts = self.analyze_tag_distribution(nodes)

        # Initialize hierarchy metadata
        hierarchy = {}

        # Step 2: Identify tags to split
        logger.info(f"\n[Step 2/5] Identifying tags to split (threshold: {self.split_threshold})...")
        tags_to_split = []
        for tag, count in tag_counts.items():
            if self.should_split_tag(tag, count, hierarchy):
                tags_to_split.append((tag, count))

        tags_to_split.sort(key=lambda x: x[1], reverse=True)  # Split largest tags first
        logger.info(f"Found {len(tags_to_split)} tags to potentially split: {[t[0] for t in tags_to_split]}")

        # Step 3: Split tags and reassign documents
        logger.info("\n[Step 3/5] Splitting tags and reassigning documents...")
        tag_reassignments = {}  # Maps parent_tag -> {doc_id -> [sub_tags]}

        for parent_tag, count in tags_to_split:
            # Get documents with this tag
            docs_with_tag = [
                node for node in nodes
                if parent_tag in node.get("tags", [])
            ]

            logger.info(f"\n  Analyzing '{parent_tag}' ({len(docs_with_tag)} documents)...")

            # Ask LLM for sub-tag suggestions
            sub_tags = self.suggest_sub_tags(parent_tag, docs_with_tag)

            if sub_tags:
                # LLM says to split - reassign documents
                logger.info(f"  Reassigning documents to sub-tags...")
                reassignments = self.reassign_documents_to_subtags(
                    parent_tag, sub_tags, docs_with_tag
                )

                tag_reassignments[parent_tag] = {
                    "sub_tags": sub_tags,
                    "reassignments": reassignments,
                }

                # Update hierarchy metadata
                hierarchy[parent_tag] = {
                    "type": "high_level",
                    "children": sub_tags,
                    "document_count": count,
                }

                for sub_tag in sub_tags:
                    sub_count = sum(
                        1 for doc_id, tags in reassignments.items()
                        if sub_tag in tags
                    )
                    hierarchy[sub_tag] = {
                        "type": "low_level",
                        "parent": parent_tag,
                        "document_count": sub_count,
                    }
            else:
                logger.info(f"  Keeping '{parent_tag}' as-is (LLM recommends not splitting)")

        # Step 4: Find cross-cutting tags
        logger.info("\n[Step 4/5] Finding cross-cutting tag combinations...")

        # First, restructure nodes with current hierarchy
        temp_nodes = self._apply_hierarchy_to_nodes(nodes, tag_reassignments, hierarchy)

        # Find high-level tags
        high_level_tags = {tag for tag, meta in hierarchy.items() if meta["type"] == "high_level"}

        # Find cross-cutting pairs
        cross_cutting_pairs = self.find_cross_cutting_tags(temp_nodes, high_level_tags)

        for tag1, tag2, count in cross_cutting_pairs:
            # Create combined tag
            combined_tag = self.create_cross_cutting_tag(tag1, tag2, [])

            # Add to hierarchy
            hierarchy[combined_tag] = {
                "type": "low_level",
                "parents": [tag1, tag2],  # Note: plural "parents"
                "document_count": count,
                "cross_cutting": True,
            }

            logger.info(f"  Created cross-cutting tag: '{combined_tag}' ({count} documents)")

        # Step 5: Apply hierarchy to all nodes
        logger.info("\n[Step 5/5] Applying hierarchy to all nodes...")
        updated_nodes = self._apply_hierarchy_to_nodes(
            nodes, tag_reassignments, hierarchy, cross_cutting_pairs
        )

        # Summary
        high_level_count = sum(1 for m in hierarchy.values() if m["type"] == "high_level")
        low_level_count = sum(1 for m in hierarchy.values() if m["type"] == "low_level")
        cross_cutting_count = sum(1 for m in hierarchy.values() if m.get("cross_cutting"))

        logger.info("\n" + "=" * 80)
        logger.info("HIERARCHY BUILD COMPLETE")
        logger.info(f"  High-level tags: {high_level_count}")
        logger.info(f"  Low-level tags: {low_level_count}")
        logger.info(f"  Cross-cutting tags: {cross_cutting_count}")
        logger.info("=" * 80)

        return updated_nodes, hierarchy

    def _apply_hierarchy_to_nodes(
        self,
        nodes: List[Dict[str, Any]],
        tag_reassignments: Dict[str, Dict[str, Any]],
        hierarchy: Dict[str, Any],
        cross_cutting_pairs: Optional[List[Tuple[str, str, int]]] = None,
    ) -> List[Dict[str, Any]]:
        """Apply hierarchical tag structure to nodes.

        Transforms flat tags into hierarchical structure:
        {
          "tags": {
            "high_level": ["Banking", "Government"],
            "low_level": ["personal banking", "government regulation"]
          }
        }
        """
        cross_cutting_pairs = cross_cutting_pairs or []
        cross_cutting_map = {
            (tag1, tag2): self.create_cross_cutting_tag(tag1, tag2, [])
            for tag1, tag2, _ in cross_cutting_pairs
        }

        updated_nodes = []

        for node in nodes:
            node_copy = node.copy()
            old_tags = node.get("tags", [])

            # Initialize hierarchical structure
            high_level_tags = set()
            low_level_tags = set()

            for tag in old_tags:
                # Check if this tag was split
                if tag in tag_reassignments:
                    # Tag was promoted to high-level
                    high_level_tags.add(tag)

                    # Add assigned sub-tags
                    doc_id = node["id"]
                    reassignments = tag_reassignments[tag]["reassignments"]
                    sub_tags = reassignments.get(doc_id, [])
                    low_level_tags.update(sub_tags)
                else:
                    # Tag remains low-level
                    low_level_tags.add(tag)

            # Check for cross-cutting tags
            high_level_list = list(high_level_tags)
            if len(high_level_list) >= 2:
                for i in range(len(high_level_list)):
                    for j in range(i + 1, len(high_level_list)):
                        pair = tuple(sorted([high_level_list[i], high_level_list[j]]))
                        if pair in cross_cutting_map:
                            low_level_tags.add(cross_cutting_map[pair])

            # Update node with hierarchical tags
            node_copy["tags"] = {
                "high_level": sorted(list(high_level_tags)),
                "low_level": sorted(list(low_level_tags)),
            }

            updated_nodes.append(node_copy)

        return updated_nodes
