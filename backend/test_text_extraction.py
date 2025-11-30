"""
Simple Test Script for Text Extraction

This script helps developers test the text extraction module
without needing to connect to Google Drive.

Usage:
    python test_text_extraction.py path/to/test/file.pdf
"""

import argparse
import sys
from pathlib import Path

from app.services.text_extraction import TextExtractor


def test_file(file_path: str) -> None:
    """
    Test text extraction on a local file.

    Args:
        file_path: Path to the file to test
    """
    path = Path(file_path)

    if not path.exists():
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)

    # Determine MIME type from extension
    mime_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".txt": "text/plain",
    }

    extension = path.suffix.lower()
    mime_type = mime_types.get(extension)

    if not mime_type:
        print(f"❌ Error: Unsupported file type: {extension}")
        print(f"Supported types: {', '.join(mime_types.keys())}")
        sys.exit(1)

    print(f"📄 Testing file: {path.name}")
    print(f"🔧 MIME type: {mime_type}")
    print(f"📊 Size: {path.stat().st_size:,} bytes")
    print("=" * 80)

    # Read file content
    with open(path, "rb") as f:
        content = f.read()

    # Extract text
    extractor = TextExtractor()

    try:
        print("\n⚙️  Extracting text...")
        raw_text = extractor.extract_text(content, mime_type, path.name)

        print("✓ Text extraction successful!")
        print(f"\n📝 Raw text length: {len(raw_text)} characters")

        # Clean text
        print("\n⚙️  Cleaning text...")
        clean_text = extractor.clean_text(raw_text)
        print("✓ Text cleaning successful!")

        # Get word count
        word_count = extractor.get_word_count(clean_text)

        print("\n" + "=" * 80)
        print("📊 RESULTS")
        print("=" * 80)
        print(f"Raw text length:    {len(raw_text):,} characters")
        print(f"Cleaned text length: {len(clean_text):,} characters")
        print(f"Word count:          {word_count:,} words")

        # Show preview
        preview_length = 500
        print(f"\n📖 Preview (first {preview_length} characters):")
        print("-" * 80)
        print(clean_text[:preview_length])
        if len(clean_text) > preview_length:
            print(f"\n... ({len(clean_text) - preview_length:,} more characters)")
        print("-" * 80)

        print("\n✅ Test completed successfully!")

    except Exception as e:
        print(f"\n❌ Error during extraction: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test text extraction on a local file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_text_extraction.py document.pdf
  python test_text_extraction.py report.docx
  python test_text_extraction.py data.xlsx
        """,
    )
    parser.add_argument("file", help="Path to the file to test")

    args = parser.parse_args()
    test_file(args.file)


if __name__ == "__main__":
    main()
