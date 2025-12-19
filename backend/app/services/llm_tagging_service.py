"""LLM-based document tagging service using GPT-4."""
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Set

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Type for progress callback: (current: int, total: int, doc_title: str) -> None
TaggingProgressCallback = Callable[[int, int, str], None]


class LLMTaggingService:
    """Service for generating tags, summaries, and entities using LLM."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the LLM tagging service.

        Args:
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"  # Fast and cost-effective for tagging

    def extract_metadata_batch(
        self,
        documents: List[Dict[str, str]],
        max_tags: int = 5,
        max_entities: int = 10,
        existing_tags: Optional[Set[str]] = None,
        existing_entities: Optional[Set[str]] = None,
        progress_callback: Optional[TaggingProgressCallback] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Extract metadata (summary, tags, entities) for multiple documents.

        Args:
            documents: List of dicts with 'id' and 'text' keys
            max_tags: Maximum number of tags per document
            max_entities: Maximum number of entities per document
            existing_tags: Set of existing tags to maintain consistency
            existing_entities: Set of existing entities to maintain consistency
            progress_callback: Optional callback for progress updates.
                Called with (current, total, doc_title) for each document.

        Returns:
            Dict mapping document_id -> metadata dict with 'summary', 'tags', 'entities'
        """
        existing_tags = existing_tags or set()
        existing_entities = existing_entities or set()

        results = {}
        total_docs = len(documents)

        for idx, doc in enumerate(documents):
            doc_id = doc["id"]
            text = doc.get("text", "")
            title = doc.get("title", "Untitled")

            # Report progress before processing each document
            if progress_callback:
                progress_callback(idx + 1, total_docs, title)

            if not text.strip():
                logger.warning(f"Empty text for document {doc_id}, skipping")
                results[doc_id] = {
                    "summary": "",
                    "tags": [],
                    "entities": [],
                }
                continue

            try:
                # Extract metadata for this document
                metadata = self._extract_single_document(
                    text=text,
                    title=title,
                    max_tags=max_tags,
                    max_entities=max_entities,
                    existing_tags=existing_tags,
                    existing_entities=existing_entities,
                )

                results[doc_id] = metadata

                # Update existing tags and entities for consistency in future docs
                existing_tags.update(metadata["tags"])
                existing_entities.update(metadata["entities"])

                logger.info(
                    f"Extracted metadata for {doc_id}: "
                    f"{len(metadata['tags'])} tags, {len(metadata['entities'])} entities"
                )

            except Exception as e:
                logger.error(f"Failed to extract metadata for {doc_id}: {e}")
                results[doc_id] = {
                    "summary": "",
                    "tags": [],
                    "entities": [],
                }

        return results

    def _extract_single_document(
        self,
        text: str,
        title: str,
        max_tags: int,
        max_entities: int,
        existing_tags: Set[str],
        existing_entities: Set[str],
    ) -> Dict[str, Any]:
        """Extract metadata for a single document.

        Args:
            text: Document text content
            title: Document title
            max_tags: Maximum number of tags
            max_entities: Maximum number of entities
            existing_tags: Existing tags for consistency
            existing_entities: Existing entities for consistency

        Returns:
            Dict with 'summary', 'tags', 'entities'
        """
        # Truncate text if too long (GPT-4o-mini has 128k context but let's be conservative)
        max_chars = 10000
        truncated_text = text[:max_chars] if len(text) > max_chars else text

        # Build the prompt
        system_prompt = self._build_system_prompt(
            max_tags, max_entities, existing_tags, existing_entities
        )
        user_prompt = self._build_user_prompt(title, truncated_text)

        try:
            # Call GPT-4o-mini with JSON mode
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # Very low temperature for precise, relevant output
                max_tokens=500,
            )

            # Parse JSON response
            result = json.loads(response.choices[0].message.content)

            return {
                "summary": result.get("summary", ""),
                "tags": result.get("tags", [])[:max_tags],
                "entities": result.get("entities", [])[:max_entities],
            }

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            raise

    def _build_system_prompt(
        self,
        max_tags: int,
        max_entities: int,
        existing_tags: Set[str],
        existing_entities: Set[str],
    ) -> str:
        """Build the system prompt for metadata extraction."""
        existing_tags_str = ", ".join(sorted(existing_tags)) if existing_tags else "None yet"
        existing_entities_str = (
            ", ".join(sorted(existing_entities)) if existing_entities else "None yet"
        )

        return f"""You are a document analysis assistant. Your task is to extract high-quality metadata from documents.

**CRITICAL: QUALITY OVER QUANTITY**
- Only create tags that are genuinely important and relevant
- Only extract entities that are mentioned MULTIPLE times or are CENTRAL to the document
- It's better to have 1-2 excellent tags than {max_tags} mediocre ones
- If a document doesn't have clear themes, use fewer tags

For each document, provide:

1. **Summary**: A concise 1-2 sentence summary capturing the main point

2. **Tags** (0 to {max_tags} tags - BE SELECTIVE AND BROAD):
   - **CRITICAL: START BROAD** - Use general categories that can be subdivided later
   - Think in CATEGORIES, not specifics (e.g., "resume" not "engineering resume", "engineering" not "mechanical engineering")
   - Include broad document types (e.g., "resume", "report", "documentation", "presentation")
   - Include broad domains (e.g., "engineering", "business", "healthcare", "government", "education")
   - Include language if not English (e.g., "Japanese", "Spanish")
   - DO NOT combine multiple concepts into one tag - keep them separate and broad
   - DO NOT create overly specific tags - these will be created later through subdivision

   ✅ GOOD BROAD TAGS: "resume", "engineering", "manufacturing", "government", "banking", "internship", "design"
   ❌ TOO SPECIFIC: "mechanical engineering internship", "government banking", "chemical engineering resume", "manufacturing project management"
   ❌ TOO GENERIC: "document", "text", "information", "project", "work"

   **Examples:**
   - Resume for software engineer → ["resume", "engineering", "software"]
   - Chemical engineering internship report → ["resume", "engineering", "internship"]
   - Government banking regulation document → ["government", "banking", "regulation"]
   - Mechanical design document → ["design", "engineering"]

3. **Entities** (0 to {max_entities} entities - BE VERY SELECTIVE):
   - Only extract if mentioned 2+ times OR is the central subject
   - Focus on: Important people, organizations, major projects, products
   - Ignore: Generic references, pronouns, minor mentions

   ✅ GOOD ENTITIES: "Google Cloud Platform" (mentioned 5 times), "Dr. Jane Smith" (document author), "Project Phoenix" (main topic)
   ❌ BAD ENTITIES: "the team", "our company", "John" (mentioned once in passing)

**CRITICAL: RELEVANCE FIRST, CONSISTENCY SECOND**
- Tags must be DIRECTLY RELEVANT to THIS document's actual content
- ONLY reuse an existing tag if it's a PERFECT match for this document's theme
- CREATE NEW tags when existing ones don't fit - accuracy beats consistency!
- Use lowercase for multi-word tags (e.g., "machine learning" not "Machine Learning")

**Tag Reuse Guidelines (Existing tags for reference: {existing_tags_str})**
- ✅ GOOD REUSE: Document about computer vision → reuse "computer vision" if it exists
- ❌ BAD REUSE: Document about computer vision → DO NOT reuse "game mechanics" or "event planning" just because they exist
- ✅ CREATE NEW: Document about camera calibration → create "camera calibration" even if not in existing tags
- ❌ FORCE-FIT: DO NOT use generic tags like "hacks", "information", "project" just to reuse something

**Examples of Relevance Over Consistency:**
- Computer vision homework about camera matrices → ["computer vision", "camera calibration", "3D reconstruction"] NOT ["game mechanics", "event planning"]
- Software design document → ["software architecture", "design patterns", "system design"] NOT ["hacks", "upgrades"]
- Qualcomm internship report → ["software engineering", "internship", "embedded systems"] NOT ["game mechanics", "beekeeping"]

**Entity Consistency (Existing entities: {existing_entities_str})**
- ONLY reuse entity names if they refer to the EXACT same person/org/project
- Use full names (e.g., "Amazon Web Services" not "AWS" if full name exists)
- Canonicalize names (e.g., always "John Smith" not "J. Smith")
- DO NOT force-fit entities from other documents

Return JSON:
{{
  "summary": "Brief 1-2 sentence summary",
  "tags": ["only", "important", "tags"],
  "entities": ["Only", "Frequently Mentioned", "Entities"]
}}

Remember: Empty arrays are better than irrelevant tags/entities!"""

    def _build_user_prompt(self, title: str, text: str) -> str:
        """Build the user prompt with document content."""
        return f"""Document Title: {title}

Document Content:
{text}

Extract the summary, tags, and entities as JSON."""
