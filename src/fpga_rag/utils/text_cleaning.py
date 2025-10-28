"""Text cleaning utilities for removing headers, footers, and noise.

Removes common patterns found in technical PDFs like page numbers,
copyright notices, and repeated headers/footers.
"""

import re
from typing import List, Set


# Common patterns to remove
FOOTER_PATTERNS = [
    # Page numbers with document IDs
    re.compile(r'User Guide\s+DS\d+[A-Z]?\s*-\s*\d+'),
    re.compile(r'Data Sheet\s+DS\d+[A-Z]?\s*-\s*\d+'),
    re.compile(r'Application Note\s+AN\d+\s*-\s*\d+'),

    # Copyright notices
    re.compile(r'©\s*\d{4}\s+Microchip Technology Inc\..*'),
    re.compile(r'Copyright\s*©\s*\d{4}.*Microchip.*'),

    # Repeated document titles at top of pages
    re.compile(r'^(PolarFire|Microchip).*User Guide\s*$', re.MULTILINE),
    re.compile(r'^(PolarFire|Microchip).*Data Sheet\s*$', re.MULTILINE),

    # Page markers
    re.compile(r'Page \d+ of \d+'),
    re.compile(r'\d+\s*/\s*\d+'),  # Page 5/100

    # Common footer elements
    re.compile(r'^\s*\d+\s*$', re.MULTILINE),  # Standalone page numbers
    re.compile(r'Rev\.\s*[A-Z]\s*$'),  # Revision markers at end
]


# Patterns for headers (repeated at top of each page)
HEADER_PATTERNS = [
    re.compile(r'^.*?\(Ask a Question\)\s*\n', re.MULTILINE),  # Interactive elements
]


def clean_page_text(text: str, aggressive: bool = False) -> str:
    """
    Clean a single page of text by removing headers, footers, and noise.

    Args:
        text: Raw page text
        aggressive: If True, more aggressively remove potential noise

    Returns:
        Cleaned text
    """
    if not text.strip():
        return text

    cleaned = text

    # Remove footer patterns
    for pattern in FOOTER_PATTERNS:
        cleaned = pattern.sub('', cleaned)

    # Remove header patterns
    for pattern in HEADER_PATTERNS:
        cleaned = pattern.sub('', cleaned)

    if aggressive:
        # Remove very short lines (likely headers/footers)
        lines = cleaned.split('\n')
        lines = [line for line in lines if len(line.strip()) > 10 or line.strip() == '']
        cleaned = '\n'.join(lines)

    # Clean up excessive whitespace
    cleaned = re.sub(r'\n\n\n+', '\n\n', cleaned)  # Max 2 newlines
    cleaned = re.sub(r'  +', ' ', cleaned)  # Multiple spaces to single
    cleaned = cleaned.strip()

    return cleaned


def detect_repeated_elements(pages: List[str], min_occurrences: int = 3) -> Set[str]:
    """
    Detect text elements that repeat across multiple pages (likely headers/footers).

    Args:
        pages: List of page texts
        min_occurrences: Minimum times an element must appear to be considered repeated

    Returns:
        Set of repeated text snippets to remove
    """
    # Count lines that appear on multiple pages
    line_counts = {}

    for page in pages:
        lines = set(page.split('\n'))
        for line in lines:
            line_clean = line.strip()
            if 10 < len(line_clean) < 100:  # Reasonable header/footer length
                line_counts[line_clean] = line_counts.get(line_clean, 0) + 1

    # Find lines that repeat frequently
    repeated = {
        line for line, count in line_counts.items()
        if count >= min(min_occurrences, len(pages) * 0.7)  # 70% of pages
    }

    return repeated


def clean_document_pages(
    pages: List[tuple[int, str]],  # (page_num, text)
    aggressive: bool = False,
    detect_repeats: bool = True
) -> List[tuple[int, str]]:
    """
    Clean all pages in a document.

    Optionally detects and removes repeated headers/footers across pages.

    Args:
        pages: List of (page_number, text) tuples
        aggressive: More aggressive cleaning
        detect_repeats: Detect repeated elements across pages

    Returns:
        List of (page_number, cleaned_text) tuples
    """
    if not pages:
        return pages

    # Detect repeated elements across pages
    repeated_elements = set()
    if detect_repeats and len(pages) > 3:
        page_texts = [text for _, text in pages]
        repeated_elements = detect_repeated_elements(page_texts)

    # Clean each page
    cleaned_pages = []
    for page_num, text in pages:
        cleaned = clean_page_text(text, aggressive=aggressive)

        # Remove detected repeated elements
        if repeated_elements:
            for repeated in repeated_elements:
                cleaned = cleaned.replace(repeated, '')

        # Final whitespace cleanup
        cleaned = re.sub(r'\n\n\n+', '\n\n', cleaned)
        cleaned = cleaned.strip()

        if cleaned:  # Only keep non-empty pages
            cleaned_pages.append((page_num, cleaned))

    return cleaned_pages


def remove_section_duplicates(text: str, section_title: str) -> str:
    """
    Remove repeated section titles from text.

    Sometimes PDF extractors duplicate section headers.

    Args:
        text: Text containing potential duplicates
        section_title: Section title to deduplicate

    Returns:
        Text with duplicates removed
    """
    if not section_title or section_title not in text:
        return text

    # Remove repeated occurrences (keep first)
    parts = text.split(section_title)
    if len(parts) > 2:
        # Keep first occurrence + rest of text
        return section_title.join([parts[0], section_title, ''.join(parts[2:])])

    return text


__all__ = [
    "clean_page_text",
    "detect_repeated_elements",
    "clean_document_pages",
    "remove_section_duplicates"
]
