"""ML-based tag extraction service using KeyBERT for semantic meaning."""
from typing import List, Tuple

from keybert import KeyBERT
from sentence_transformers import SentenceTransformer


class MLTagExtractionService:
    """Service for extracting semantic tags from documents using KeyBERT."""

    def __init__(
        self,
        max_tags_per_doc: int = 15,
        diversity: float = 0.7,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        """Initialize ML tag extraction service.

        Args:
            max_tags_per_doc: Maximum number of tags to extract per document
            diversity: Diversity parameter for MMR (0.0-1.0, higher = more diverse)
            model_name: Sentence transformer model to use
        """
        self.max_tags_per_doc = max_tags_per_doc
        self.diversity = diversity

        # Initialize sentence transformer model
        print(f"Loading ML model: {model_name}...")
        self.model = SentenceTransformer(model_name)

        # Initialize KeyBERT with the model
        self.keybert = KeyBERT(model=self.model)
        print("✓ ML model loaded")

    def extract_tags(self, text: str) -> List[Tuple[str, float]]:
        """Extract semantic tags from text using KeyBERT.

        Args:
            text: Document text content

        Returns:
            List of tuples (tag_name, relevance_score)
            Tags can be 1-3 word phrases based on semantic meaning
        """
        if not text or not text.strip():
            return []

        try:
            # Extract keywords using KeyBERT with MMR for diversity
            keywords = self.keybert.extract_keywords(
                text,
                keyphrase_ngram_range=(1, 3),  # Extract 1-3 word phrases
                stop_words="english",
                top_n=self.max_tags_per_doc,
                use_mmr=True,  # Use Maximal Marginal Relevance
                diversity=self.diversity,  # Balance between relevance and diversity
            )

            # KeyBERT returns list of (phrase, score) tuples
            # Normalize to lowercase for consistency
            normalized_tags = [
                (phrase.lower().strip(), float(score)) for phrase, score in keywords
            ]

            return normalized_tags

        except Exception as e:
            print(f"Warning: Tag extraction failed for document: {e}")
            return []

    def extract_tags_batch(
        self, texts: List[str], show_progress: bool = False
    ) -> List[List[Tuple[str, float]]]:
        """Extract tags from multiple documents.

        Args:
            texts: List of document texts
            show_progress: Whether to show progress updates

        Returns:
            List of tag lists, one per document
        """
        results = []
        for idx, text in enumerate(texts):
            if show_progress and (idx % 10 == 0 or idx == len(texts) - 1):
                print(f"Extracting tags: {idx + 1}/{len(texts)}")
            results.append(self.extract_tags(text))
        return results

    def get_embedding(self, text: str):
        """Get embedding vector for a text string.

        Args:
            text: Text to embed

        Returns:
            Numpy array of embedding values
        """
        return self.model.encode(text)

    def get_embeddings_batch(self, texts: List[str]):
        """Get embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            Numpy array of embeddings
        """
        return self.model.encode(texts)
