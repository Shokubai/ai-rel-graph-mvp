"""Tag extraction service for automated document categorization."""
import re
from collections import Counter
from typing import Dict, List, Set, Tuple

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer


class TagExtractionService:
    """Service for extracting broad category tags from document text."""

    # Synonym mappings - related terms that should be treated as the same tag
    SYNONYMS = {
        "machine": ["learning", "deep", "artificial", "intelligence", "neural"],
        "learning": ["machine", "deep", "neural", "training", "model"],
        "neural": ["network", "networks", "deep", "learning", "machine"],
        "deep": ["learning", "neural", "network", "machine"],
        "strategy": ["strategic", "planning", "business", "roadmap"],
        "strategic": ["strategy", "planning", "business"],
        "employee": ["employees", "staff", "workforce", "team", "personnel"],
        "financial": ["finance", "budget", "revenue", "fiscal", "economic"],
    }

    # Broad category patterns - documents are classified into these categories
    CATEGORY_PATTERNS = {
        "technology": [
            "software", "hardware", "computer", "algorithm", "code", "programming",
            "database", "network", "server", "cloud", "api", "system", "technical",
            "machine learning", "artificial intelligence", "neural network", "data science",
            "deep learning", "neural networks", "machine", "learning", "neural", "deep",
            "python", "java", "javascript", "development", "engineering", "architecture",
            "model", "training", "algorithm", "computational",
        ],
        "finance": [
            "budget", "financial", "revenue", "expense", "cost", "profit", "loss",
            "accounting", "invoice", "payment", "tax", "investment", "money", "dollar",
            "quarterly", "annual", "fiscal", "funding", "capital", "cash flow",
        ],
        "business": [
            "strategy", "strategic", "market", "customer", "sales", "product", "service", "company",
            "organization", "management", "operations", "business model", "growth",
            "partnership", "vendor", "stakeholder", "roi", "kpi", "metrics",
            "planning", "roadmap", "objectives", "goals", "initiative", "expansion",
            "team", "meeting", "quarterly", "priorities",
        ],
        "human_resources": [
            "employee", "employees", "staff", "hiring", "recruitment", "onboarding", "training",
            "performance", "compensation", "salary", "benefits", "leave", "policy",
            "team", "manager", "hr", "workforce", "talent", "career",
            "remote", "work", "office", "meeting", "handbook", "personnel",
        ],
        "legal": [
            "contract", "agreement", "compliance", "regulation", "law", "legal",
            "terms", "conditions", "liability", "intellectual property", "patent",
            "trademark", "confidential", "nda", "privacy", "gdpr",
        ],
        "marketing": [
            "campaign", "advertising", "branding", "promotion", "social media",
            "content", "seo", "analytics", "engagement", "lead", "conversion",
            "audience", "channel", "email", "creative", "messaging",
        ],
        "operations": [
            "process", "workflow", "procedure", "logistics", "supply chain",
            "inventory", "production", "quality", "efficiency", "optimization",
            "automation", "deployment", "maintenance", "infrastructure",
        ],
        "research": [
            "study", "experiment", "analysis", "hypothesis", "methodology",
            "results", "findings", "conclusion", "literature", "survey",
            "statistical", "data collection", "research", "academic", "paper",
        ],
    }

    def __init__(self, min_tag_frequency: int = 2, max_tags_per_doc: int = 10):
        """Initialize tag extraction service.

        Args:
            min_tag_frequency: Minimum word frequency to be considered as a tag
            max_tags_per_doc: Maximum number of tags to extract per document
        """
        self.min_tag_frequency = min_tag_frequency
        self.max_tags_per_doc = max_tags_per_doc
        self._ensure_nltk_data()
        self.stop_words = set(stopwords.words("english"))

    def _ensure_nltk_data(self):
        """Ensure required NLTK data is downloaded."""
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            nltk.download("punkt", quiet=True)

        try:
            nltk.data.find("tokenizers/punkt_tab")
        except LookupError:
            nltk.download("punkt_tab", quiet=True)

        try:
            nltk.data.find("corpora/stopwords")
        except LookupError:
            nltk.download("stopwords", quiet=True)

    def extract_tags(self, text: str) -> List[Tuple[str, str, float]]:
        """Extract tags from text with category classification.

        Args:
            text: Document text content

        Returns:
            List of tuples (tag_name, category, relevance_score)
        """
        if not text or not text.strip():
            return []

        # Step 1: Identify broad categories
        categories = self._identify_categories(text)

        # Step 2: Extract keyword tags
        keywords = self._extract_keywords(text)

        # Step 3: Combine category tags + keyword tags
        tags = []

        # Add category tags (these are always included if detected)
        for category, score in categories:
            tags.append((category, category, score))

        # Add top keyword tags with their best matching category
        for keyword, score in keywords[:self.max_tags_per_doc]:
            best_category = self._match_keyword_to_category(keyword, categories)
            tags.append((keyword, best_category, score))

        return tags[:self.max_tags_per_doc + len(categories)]

    def _identify_categories(self, text: str) -> List[Tuple[str, float]]:
        """Identify which broad categories this document belongs to.

        Args:
            text: Document text

        Returns:
            List of (category_name, confidence_score) tuples
        """
        text_lower = text.lower()
        category_scores = {}

        for category, keywords in self.CATEGORY_PATTERNS.items():
            # Count how many category keywords appear in the text
            matches = sum(1 for keyword in keywords if keyword in text_lower)
            if matches > 0:
                # Normalize score by category size
                score = matches / len(keywords)
                category_scores[category] = score

        # Return categories sorted by score
        sorted_categories = sorted(
            category_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Only return categories with meaningful scores
        return [(cat, score) for cat, score in sorted_categories if score > 0.05]

    def _extract_keywords(self, text: str) -> List[Tuple[str, float]]:
        """Extract important keywords from text using TF-IDF.

        Args:
            text: Document text

        Returns:
            List of (keyword, score) tuples
        """
        # Tokenize and clean text
        tokens = word_tokenize(text.lower())

        # Filter tokens: remove stopwords, short words, non-alphabetic
        filtered_tokens = [
            token for token in tokens
            if (
                token.isalpha() and
                len(token) > 3 and
                token not in self.stop_words
            )
        ]

        if not filtered_tokens:
            return []

        # Count word frequencies
        word_counts = Counter(filtered_tokens)

        # Filter by minimum frequency
        frequent_words = {
            word: count for word, count in word_counts.items()
            if count >= self.min_tag_frequency
        }

        if not frequent_words:
            # If no words meet frequency threshold, take top words anyway
            frequent_words = dict(word_counts.most_common(self.max_tags_per_doc))

        # Normalize scores (0-1 range)
        max_count = max(frequent_words.values()) if frequent_words else 1
        normalized = [
            (word, count / max_count)
            for word, count in frequent_words.items()
        ]

        # Sort by score
        return sorted(normalized, key=lambda x: x[1], reverse=True)

    def _match_keyword_to_category(
        self,
        keyword: str,
        detected_categories: List[Tuple[str, float]]
    ) -> str:
        """Match a keyword to the most relevant category.

        Args:
            keyword: Keyword to categorize
            detected_categories: List of (category, score) tuples already detected

        Returns:
            Category name (or "general" if no match)
        """
        # Check if keyword appears in any category patterns
        for category, patterns in self.CATEGORY_PATTERNS.items():
            if keyword in patterns:
                return category

        # If no direct match, return the top detected category
        if detected_categories:
            return detected_categories[0][0]

        return "general"

    def extract_tags_batch(
        self,
        texts: List[str]
    ) -> List[List[Tuple[str, str, float]]]:
        """Extract tags from multiple documents.

        Args:
            texts: List of document texts

        Returns:
            List of tag lists, one per document
        """
        return [self.extract_tags(text) for text in texts]
