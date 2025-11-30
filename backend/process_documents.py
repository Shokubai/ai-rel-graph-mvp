"""
Document Processing Script (MVP)

This script processes Google Drive files and prepares them for the knowledge graph.

What it does:
1. Connects to Google Drive using an access token
2. Lists all processable files in a folder (or entire Drive)
3. Downloads each file
4. Extracts text content
5. Saves metadata and text to JSON for further processing

Usage:
    python process_documents.py --token YOUR_ACCESS_TOKEN --folder FOLDER_ID
    python process_documents.py --token YOUR_ACCESS_TOKEN  # Process entire Drive
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.services.drive_service import DriveService
from app.services.text_extraction import TextExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Main processor that orchestrates the document processing pipeline.

    This class coordinates between the Drive service and text extraction
    to convert Google Drive files into structured data.
    """

    def __init__(self, access_token: str):
        """
        Initialize the processor with a Google access token.

        Args:
            access_token: Google OAuth access token
        """
        self.drive_service = DriveService(access_token)
        self.text_extractor = TextExtractor()

    def process_folder(
        self,
        folder_id: str | None = None,
        output_file: str = "extracted_documents.json",
    ) -> List[Dict[str, Any]]:
        """
        Process all files in a Google Drive folder.

        Args:
            folder_id: Google Drive folder ID (None = entire Drive)
            output_file: Path to save the output JSON

        Returns:
            List of processed document dictionaries
        """
        logger.info("=" * 80)
        logger.info("STARTING DOCUMENT PROCESSING")
        logger.info("=" * 80)

        # Step 1: Get list of all files
        logger.info("\n[Step 1/3] Fetching file list from Google Drive...")
        all_files = self.drive_service.list_files_in_folder(folder_id)
        logger.info(f"Found {len(all_files)} total files")

        # Step 2: Filter processable files
        logger.info("\n[Step 2/3] Filtering processable files...")
        processable_files = [
            f for f in all_files if self.drive_service.is_processable_file(f.get("mimeType", ""))
        ]
        logger.info(f"Found {len(processable_files)} processable files")

        if not processable_files:
            logger.warning("No processable files found!")
            return []

        # Step 3: Process each file
        logger.info("\n[Step 3/3] Processing files...")
        processed_documents = []

        for idx, file_metadata in enumerate(processable_files, 1):
            file_id = file_metadata["id"]
            file_name = file_metadata["name"]
            mime_type = file_metadata["mimeType"]

            logger.info(f"\n--- Processing {idx}/{len(processable_files)}: {file_name} ---")

            try:
                # Download file content
                logger.info(f"  → Downloading...")
                file_content = self.drive_service.download_file(file_id, mime_type)

                # Extract text
                logger.info(f"  → Extracting text...")
                raw_text = self.text_extractor.extract_text(file_content, mime_type, file_name)

                # Clean text
                logger.info(f"  → Cleaning text...")
                cleaned_text = self.text_extractor.clean_text(raw_text)

                # Get word count
                word_count = self.text_extractor.get_word_count(cleaned_text)
                logger.info(f"  ✓ Extracted {word_count} words")

                # Build document object
                document = {
                    "id": file_id,
                    "title": file_name,
                    "url": file_metadata.get("webViewLink", ""),
                    "mimeType": mime_type,
                    "text_content": cleaned_text,
                    "metadata": {
                        "author": file_metadata.get("owners", [{}])[0].get(
                            "emailAddress", "Unknown"
                        ),
                        "modified_at": file_metadata.get("modifiedTime", ""),
                        "size_bytes": file_metadata.get("size"),
                        "word_count": word_count,
                        "processed_at": datetime.now().isoformat(),
                    },
                }

                processed_documents.append(document)

            except Exception as e:
                logger.error(f"  ✗ Failed to process {file_name}: {str(e)}")
                continue

        # Save results
        logger.info(f"\n{'=' * 80}")
        logger.info(f"PROCESSING COMPLETE")
        logger.info(f"Successfully processed: {len(processed_documents)}/{len(processable_files)}")
        logger.info(f"Saving to: {output_file}")

        self._save_to_json(processed_documents, output_file)

        return processed_documents

    def _save_to_json(self, documents: List[Dict[str, Any]], output_file: str) -> None:
        """
        Save processed documents to a JSON file.

        Args:
            documents: List of document dictionaries
            output_file: Path to output file
        """
        output_path = Path(output_file)

        # Create directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save with pretty printing
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Saved {len(documents)} documents to {output_file}")

        # Print summary statistics
        total_words = sum(doc["metadata"]["word_count"] for doc in documents)
        logger.info(f"\nSummary:")
        logger.info(f"  Total documents: {len(documents)}")
        logger.info(f"  Total words: {total_words:,}")
        logger.info(f"  Average words per document: {total_words // len(documents):,}")


def main() -> None:
    """
    Main entry point for the script.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Process Google Drive files and extract text content"
    )
    parser.add_argument(
        "--token",
        required=True,
        help="Google OAuth access token",
    )
    parser.add_argument(
        "--folder",
        default=None,
        help="Google Drive folder ID (optional - processes entire Drive if not specified)",
    )
    parser.add_argument(
        "--output",
        default="extracted_documents.json",
        help="Output file path (default: extracted_documents.json)",
    )

    args = parser.parse_args()

    # Initialize processor
    processor = DocumentProcessor(access_token=args.token)

    # Process documents
    try:
        processor.process_folder(
            folder_id=args.folder,
            output_file=args.output,
        )
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
