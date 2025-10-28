"""Token counting utilities for accurate chunk sizing.

Uses the same tokenizer as the embedding model for accurate token limits.
"""

from typing import List, Optional

from transformers import AutoTokenizer

# Cache tokenizer instance
_tokenizer_cache = {}


def get_tokenizer(model_name: str = "BAAI/bge-small-en-v1.5") -> AutoTokenizer:
    """
    Get tokenizer for a model (cached).

    Args:
        model_name: Name of the model to get tokenizer for

    Returns:
        AutoTokenizer instance
    """
    if model_name not in _tokenizer_cache:
        _tokenizer_cache[model_name] = AutoTokenizer.from_pretrained(model_name)
    return _tokenizer_cache[model_name]


def count_tokens(text: str, model_name: str = "BAAI/bge-small-en-v1.5") -> int:
    """
    Count tokens in text using the embedding model's tokenizer.

    Args:
        text: Text to count tokens in
        model_name: Model name to get tokenizer from

    Returns:
        Number of tokens
    """
    import logging
    tokenizer = get_tokenizer(model_name)

    # Temporarily suppress transformers logging warnings
    # (we're only counting to determine if splitting is needed, not embedding)
    transformers_logger = logging.getLogger("transformers.tokenization_utils_base")
    old_level = transformers_logger.level
    transformers_logger.setLevel(logging.ERROR)

    try:
        tokens = tokenizer.encode(text, add_special_tokens=False, truncation=False)
    finally:
        transformers_logger.setLevel(old_level)

    return len(tokens)


def chunk_by_tokens(
    text: str,
    max_tokens: int = 1500,
    overlap_tokens: int = 150,
    model_name: str = "BAAI/bge-small-en-v1.5"
) -> List[str]:
    """
    Chunk text by token count with overlap.

    Tries to break at sentence boundaries when possible.

    Args:
        text: Text to chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlap in tokens
        model_name: Model name for tokenizer

    Returns:
        List of text chunks
    """
    tokenizer = get_tokenizer(model_name)

    # Tokenize full text
    tokens = tokenizer.encode(text, add_special_tokens=False)

    if len(tokens) <= max_tokens:
        return [text]

    chunks = []
    start = 0

    while start < len(tokens):
        end = start + max_tokens

        # Get chunk tokens
        chunk_tokens = tokens[start:end]
        chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)

        # Try to break at sentence boundary
        if end < len(tokens):
            # Look for last sentence boundary in chunk
            for sep in ['. ', '.\n', '! ', '?\n']:
                last_sep = chunk_text.rfind(sep)
                if last_sep > len(chunk_text) // 2:  # At least halfway through
                    # Re-tokenize to get accurate split point
                    truncated = chunk_text[:last_sep + len(sep)]
                    truncated_tokens = tokenizer.encode(truncated, add_special_tokens=False)

                    # Safety: ensure we didn't exceed max_tokens after re-tokenization
                    if len(truncated_tokens) <= max_tokens:
                        chunk_text = truncated
                        chunk_tokens = truncated_tokens
                        break
                    # If still too large, try next separator

        # Final safety check: re-tokenize chunk_text to ensure it's within limits
        # (in case no sentence boundary was found or all were too large)
        final_tokens = tokenizer.encode(chunk_text, add_special_tokens=False)
        if len(final_tokens) > max_tokens:
            # Hard truncate to max_tokens
            chunk_tokens = final_tokens[:max_tokens]
            chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)

        chunks.append(chunk_text.strip())

        # Move start with overlap
        if end < len(tokens):
            start = start + len(chunk_tokens) - overlap_tokens
        else:
            break

    return chunks


def estimate_tokens(text: str) -> int:
    """
    Fast estimate of token count without tokenizer.

    Uses approximation: ~1.3 tokens per word for English text.
    Use count_tokens() for accurate counts.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count
    """
    words = len(text.split())
    return int(words * 1.3)


__all__ = [
    "get_tokenizer",
    "count_tokens",
    "chunk_by_tokens",
    "estimate_tokens"
]
