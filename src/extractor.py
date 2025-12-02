"""
PDF Text Extraction and Chunking Module

Extracts text from PDF contracts while preserving:
- Page numbers for source attribution
- Section headers and structure
- Paragraph boundaries

Implements chunking strategy for LLM context window management.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber


@dataclass
class TextChunk:
    """A chunk of text with source location metadata."""

    text: str
    start_page: int
    end_page: int
    chunk_index: int
    total_chunks: int
    sections: list[str] = field(default_factory=list)
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)

    @property
    def source_location(self) -> str:
        """Human-readable source location."""
        if self.start_page == self.end_page:
            return f"Page {self.start_page}"
        return f"Pages {self.start_page}-{self.end_page}"


@dataclass
class ExtractionResult:
    """Complete extraction result from a PDF."""

    file_path: str
    total_pages: int
    total_chars: int
    chunks: list[TextChunk]
    raw_text: str
    page_texts: dict[int, str]  # page_num -> text
    sections_found: list[dict]  # list of {name, page, position}

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)


class ContractExtractor:
    """
    Extracts and chunks text from PDF contracts.

    Handles:
    - Multi-page PDFs (tested up to 100+ pages)
    - Section detection for better context preservation
    - Overlapping chunks to avoid splitting clauses
    - Source attribution for verification
    """

    # Section header patterns (common in legal docs)
    SECTION_PATTERNS = [
        r'^(?:ARTICLE|SECTION|PART)\s+[IVXLCDM\d]+[.:]\s*(.+)$',  # ARTICLE I: Title
        r'^(\d+\.)\s+([A-Z][A-Z\s]+)$',  # 1. DEFINITIONS
        r'^(\d+\.\d+)\s+(.+)$',  # 1.1 Subsection
        r'^([A-Z][A-Z\s]{2,})$',  # ALL CAPS HEADERS
        r'^((?:EXHIBIT|SCHEDULE|APPENDIX)\s+[A-Z\d]+)',  # EXHIBIT A
    ]

    # Default chunking parameters
    DEFAULT_CHUNK_SIZE = 4000  # chars (~1000 tokens)
    DEFAULT_OVERLAP = 200  # chars of overlap between chunks
    MIN_CHUNK_SIZE = 500  # don't create tiny chunks

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ):
        """
        Initialize the extractor.

        Args:
            chunk_size: Target size for each chunk in characters.
                       ~4000 chars ≈ 1000 tokens for most LLMs.
            overlap: Number of characters to overlap between chunks
                    to avoid splitting clauses mid-sentence.
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._compiled_patterns = [
            re.compile(p, re.MULTILINE) for p in self.SECTION_PATTERNS
        ]

    def extract(self, pdf_path: str | Path) -> ExtractionResult:
        """
        Extract text from a PDF file.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            ExtractionResult with chunks and metadata.

        Raises:
            FileNotFoundError: If PDF doesn't exist.
            ValueError: If PDF cannot be read or has no text.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        if pdf_path.suffix.lower() != '.pdf':
            raise ValueError(f"Not a PDF file: {pdf_path}")

        # Extract text from each page
        page_texts = {}
        sections_found = []

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                page_texts[page_num] = text

                # Detect sections on this page
                page_sections = self._detect_sections(text, page_num)
                sections_found.extend(page_sections)

        # Combine all text
        raw_text = "\n\n".join(
            f"[Page {num}]\n{text}"
            for num, text in sorted(page_texts.items())
        )

        if not raw_text.strip():
            raise ValueError(
                f"No text extracted from PDF. "
                f"File may be scanned/image-based and require OCR."
            )

        # Create chunks
        chunks = self._create_chunks(page_texts, sections_found)

        return ExtractionResult(
            file_path=str(pdf_path),
            total_pages=total_pages,
            total_chars=len(raw_text),
            chunks=chunks,
            raw_text=raw_text,
            page_texts=page_texts,
            sections_found=sections_found,
        )

    def extract_text_only(self, pdf_path: str | Path) -> str:
        """
        Simple extraction - just get the text, no chunking.

        Useful for small documents or when you need raw text.
        """
        pdf_path = Path(pdf_path)

        with pdfplumber.open(pdf_path) as pdf:
            texts = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    texts.append(text)
            return "\n\n".join(texts)

    def _detect_sections(
        self, text: str, page_num: int
    ) -> list[dict]:
        """Detect section headers in text."""
        sections = []

        for line_num, line in enumerate(text.split('\n')):
            line = line.strip()
            if not line:
                continue

            for pattern in self._compiled_patterns:
                match = pattern.match(line)
                if match:
                    sections.append({
                        'name': line,
                        'page': page_num,
                        'line': line_num,
                    })
                    break

        return sections

    def _create_chunks(
        self,
        page_texts: dict[int, str],
        sections: list[dict],
    ) -> list[TextChunk]:
        """
        Create overlapping chunks from page texts.

        Strategy:
        1. Prefer breaking at paragraph/section boundaries
        2. Use overlap to maintain context across chunks
        3. Track which pages each chunk spans
        """
        chunks = []
        current_chunk_text = ""
        current_start_page = 1
        current_sections = []

        # Build a flat list of (page_num, paragraph, sections_in_para)
        paragraphs = []
        for page_num in sorted(page_texts.keys()):
            text = page_texts[page_num]
            page_sections = [s['name'] for s in sections if s['page'] == page_num]

            # Split into paragraphs (double newline or section boundary)
            para_texts = re.split(r'\n\s*\n', text)

            for para in para_texts:
                para = para.strip()
                if para:
                    # Check if this paragraph contains a section header
                    para_sections = [
                        s for s in page_sections
                        if s in para or para in s
                    ]
                    paragraphs.append((page_num, para, para_sections))

        # Now create chunks from paragraphs
        for page_num, para, para_sections in paragraphs:
            potential_text = current_chunk_text + "\n\n" + para if current_chunk_text else para

            # Check if adding this paragraph exceeds chunk size
            if len(potential_text) > self.chunk_size and current_chunk_text:
                # Save current chunk
                chunks.append(TextChunk(
                    text=current_chunk_text.strip(),
                    start_page=current_start_page,
                    end_page=page_num,
                    chunk_index=len(chunks),
                    total_chunks=0,  # Updated later
                    sections=current_sections.copy(),
                ))

                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk_text)
                current_chunk_text = overlap_text + "\n\n" + para if overlap_text else para
                current_start_page = page_num
                current_sections = para_sections.copy()
            else:
                current_chunk_text = potential_text
                current_sections.extend(para_sections)

        # Don't forget the last chunk
        if current_chunk_text.strip():
            last_page = max(page_texts.keys()) if page_texts else 1
            chunks.append(TextChunk(
                text=current_chunk_text.strip(),
                start_page=current_start_page,
                end_page=last_page,
                chunk_index=len(chunks),
                total_chunks=0,
                sections=current_sections,
            ))

        # Update total_chunks count
        for chunk in chunks:
            chunk.total_chunks = len(chunks)

        return chunks

    def _get_overlap_text(self, text: str) -> str:
        """Get the last N characters for overlap, breaking at sentence boundary."""
        if len(text) <= self.overlap:
            return text

        # Get last `overlap` characters
        overlap_text = text[-self.overlap:]

        # Try to break at a sentence boundary
        sentence_end = max(
            overlap_text.rfind('. '),
            overlap_text.rfind('.\n'),
            overlap_text.rfind('.\t'),
        )

        if sentence_end > 0:
            return overlap_text[sentence_end + 2:]

        # Try breaking at paragraph
        para_break = overlap_text.find('\n\n')
        if para_break > 0:
            return overlap_text[para_break + 2:]

        return overlap_text


def extract_from_text_file(
    text_path: str | Path,
    chunk_size: int = ContractExtractor.DEFAULT_CHUNK_SIZE,
    overlap: int = ContractExtractor.DEFAULT_OVERLAP,
) -> ExtractionResult:
    """
    Extract and chunk from a plain text file.

    Useful for testing with .txt sample contracts.
    Simulates page breaks every ~3000 characters.
    """
    text_path = Path(text_path)

    if not text_path.exists():
        raise FileNotFoundError(f"File not found: {text_path}")

    with open(text_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # Simulate pages (roughly 3000 chars per page like a real contract)
    chars_per_page = 3000
    page_texts = {}
    page_num = 1

    # Split at paragraph boundaries near page size
    paragraphs = raw_text.split('\n\n')
    current_page_text = ""

    for para in paragraphs:
        if len(current_page_text) + len(para) > chars_per_page and current_page_text:
            page_texts[page_num] = current_page_text.strip()
            page_num += 1
            current_page_text = para
        else:
            current_page_text += "\n\n" + para if current_page_text else para

    if current_page_text.strip():
        page_texts[page_num] = current_page_text.strip()

    # Use the extractor's chunking logic
    extractor = ContractExtractor(chunk_size=chunk_size, overlap=overlap)

    # Detect sections
    sections_found = []
    for pnum, text in page_texts.items():
        sections_found.extend(extractor._detect_sections(text, pnum))

    # Create chunks
    chunks = extractor._create_chunks(page_texts, sections_found)

    return ExtractionResult(
        file_path=str(text_path),
        total_pages=len(page_texts),
        total_chars=len(raw_text),
        chunks=chunks,
        raw_text=raw_text,
        page_texts=page_texts,
        sections_found=sections_found,
    )


# Convenience function for CLI usage
def extract_contract(
    file_path: str | Path,
    chunk_size: int = ContractExtractor.DEFAULT_CHUNK_SIZE,
    overlap: int = ContractExtractor.DEFAULT_OVERLAP,
) -> ExtractionResult:
    """
    Extract text from a contract file (PDF or TXT).

    Automatically detects file type and uses appropriate extractor.
    """
    file_path = Path(file_path)

    if file_path.suffix.lower() == '.pdf':
        extractor = ContractExtractor(chunk_size=chunk_size, overlap=overlap)
        return extractor.extract(file_path)
    elif file_path.suffix.lower() in ('.txt', '.text'):
        return extract_from_text_file(file_path, chunk_size, overlap)
    else:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")


if __name__ == "__main__":
    # Simple CLI for testing
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extractor.py <file_path>")
        print("Supported formats: .pdf, .txt")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        result = extract_contract(file_path)

        print(f"\n{'='*60}")
        print(f"Extraction Results: {result.file_path}")
        print(f"{'='*60}")
        print(f"Total pages: {result.total_pages}")
        print(f"Total characters: {result.total_chars:,}")
        print(f"Chunks created: {result.chunk_count}")
        print(f"Sections found: {len(result.sections_found)}")

        if result.sections_found:
            print(f"\nSections detected:")
            for s in result.sections_found[:10]:
                print(f"  - Page {s['page']}: {s['name'][:50]}")
            if len(result.sections_found) > 10:
                print(f"  ... and {len(result.sections_found) - 10} more")

        print(f"\nChunk Summary:")
        for chunk in result.chunks:
            print(f"  Chunk {chunk.chunk_index + 1}/{chunk.total_chunks}: "
                  f"{chunk.source_location}, {chunk.char_count:,} chars")

        print(f"\n{'='*60}")
        print("First chunk preview (500 chars):")
        print(f"{'='*60}")
        print(result.chunks[0].text[:500] + "...")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
