# FPGA RAG System - Quick Demo Guide

**Status:** ✅ **Production Ready** (as of 2025-10-27)

## What Is This?

A **local-first RAG (Retrieval-Augmented Generation) system** that enables semantic search over **7 PolarFire FPGA documentation PDFs** (828 pages total).

**No internet required. No API keys. Runs locally.**

---

## Key Stats

- **Documents indexed:** 7 PolarFire FPGA guides
- **Total chunks:** 1,655 (optimized with semantic chunking)
- **Embedding model:** BAAI/bge-small-en-v1.5 (384-dim vectors)
- **Token limit:** 400 tokens/chunk (enforced)
- **Search quality:** 0.6-0.7 similarity scores
- **Index time:** ~4 minutes (one-time)

---

## Quick Test

### Option 1: Python Script

```bash
cd ~/fpga_mcp
python scripts/test_indexing.py
```

**What it does:**
- Searches 5 test queries
- Shows results with page numbers and scores
- Displays collection statistics

### Option 2: Direct Search

```bash
cd ~/fpga_mcp
python << 'EOF'
import sys
sys.path.insert(0, 'src')
from fpga_rag.indexing import DocumentEmbedder
from mchp_mcp_core.storage.schemas import SearchQuery

embedder = DocumentEmbedder()

# Try your own query!
query = SearchQuery(query="PCIe transceiver configuration", top_k=5)
results = embedder.vector_store.search(query)

for i, r in enumerate(results, 1):
    print(f"\n{i}. {r.title}")
    print(f"   Page: {r.slide_or_page} | Score: {r.score:.3f}")
    print(f"   {r.snippet[:200]}...")
EOF
```

---

## Indexed Documents

1. **User IO Guide** (294 chunks) - Pin config, I/O standards, LVDS
2. **Clocking Guide** (147 chunks) - CCC/PLL, clock routing
3. **Board Design** (86 chunks) - Power supply, PCB layout
4. **Datasheet** (265 chunks) - Electrical specs, timing
5. **Transceiver Guide** (297 chunks) - SERDES, PCIe protocols
6. **Fabric Guide** (223 chunks) - Logic resources, routing
7. **Memory Controller** (343 chunks) - DDR3/DDR4 configuration

---

## Example Queries

**Good queries** (work well):
- "DDR4 memory controller configuration"
- "PCIe lane setup transceiver"
- "PolarFire clocking resources CCC"
- "GPIO pin voltage levels"
- "SERDES data rate settings"

**Not indexed yet:**
- TCL command reference
- Libero internal help docs
- Application notes

---

## How It Works

### 1. Text Extraction
- PDFs → `pdftotext` → page-by-page text files
- Stored in `~/fpga_mcp/content/{doc_id}/text/`

### 2. Semantic Chunking
- **Section-aware splitting** (preserves document structure)
- **Token-based limits** (400 tokens max per chunk)
- **Overlap:** 60 tokens (15% - optimal for technical docs)
- **Header/footer removal** (auto-detects repeated text)

### 3. Embedding
- Model: `BAAI/bge-small-en-v1.5`
- Generates 384-dimensional vectors
- Stores in ChromaDB at `~/fpga_mcp/chroma/`

### 4. Search
- **Semantic similarity** using cosine distance
- Returns top-K most relevant chunks
- Includes page numbers and document titles

---

## Key Optimizations Implemented

### Problem: Token Limit Violations
**Before:** Character-based chunking → 50% of chunks exceeded 512 token limit
**After:** Token-aware enforcement → 100% of chunks within 400 token limit

### Problem: Low-Quality Chunks
**Before:** Repeated headers/footers in every chunk
**After:** Auto-detection and removal of repeated elements

### Problem: Broken Sections
**Before:** Fixed-size splitting broke sections mid-topic
**After:** Semantic chunking preserves section boundaries

---

## Technical Details

### Stack
- **Vector DB:** ChromaDB (local SQLite)
- **Embeddings:** sentence-transformers
- **Chunking:** mchp-mcp-core (semantic strategy)
- **Text cleaning:** Custom header/footer detection
- **Token counting:** transformers AutoTokenizer

### File Structure
```
~/fpga_mcp/
├── chroma/              # Vector database (1,655 chunks)
├── content/             # Extracted text from PDFs
│   └── {doc_id}/
│       └── text/        # Page-by-page text files
├── scripts/
│   ├── test_indexing.py # Demo script
│   └── ingest.py        # Add new documents
├── src/fpga_rag/
│   ├── indexing/
│   │   └── embedder.py  # Main indexing logic
│   └── utils/
│       ├── token_counter.py  # Token-based chunking
│       └── text_cleaning.py  # Header/footer removal
└── DEMO.md              # This file
```

---

## Common Questions

### Q: How do I add more documents?
**A:** Place PDFs in `~/fpga_mcp/incoming/` and run:
```bash
cd ~/fpga_mcp
python scripts/ingest.py
```

### Q: How do I re-index with different parameters?
**A:** Edit `scripts/test_indexing.py` lines 57-59:
```python
total_chunks = embedder.index_all_documents(
    max_tokens=400,      # Adjust chunk size
    overlap_tokens=60,   # Adjust overlap
    use_semantic=True    # Toggle semantic chunking
)
```

### Q: Can I use a different embedding model?
**A:** Yes! Edit `embedder.py` to pass different model name:
```python
self.embedder = EmbeddingModel(model_name="your-model-here")
```

### Q: How do I integrate with Claude Code?
**A:** MCP server already exists at `src/fpga_rag/mcp_server/server.py`.
Configuration needed in Claude Code's MCP settings.

---

## Performance

**Index time:** ~4 minutes (7 documents, 828 pages)
- Text extraction: Already done (one-time)
- Embedding generation: ~3-4 min on CPU
- ChromaDB insertion: <30 seconds

**Search time:** ~0.5 seconds per query
- Embedding query: ~100ms
- Vector search: ~400ms
- Result formatting: negligible

---

## Next Steps (Optional)

1. **Claude Code Integration** - Enable MCP server for Claude CLI
2. **Hybrid Search** - Add BM25 keyword matching alongside vector search
3. **Query Enhancement** - Auto-expand acronyms (DDR → DDR3/DDR4)
4. **Additional Docs** - Index TCL Command Reference and App Notes
5. **Metadata Filtering** - Filter by doc type, FPGA family

---

## Troubleshooting

**Issue: "ChromaDB not available"**
- Run: `pip install chromadb sentence-transformers`

**Issue: "No documents found"**
- Check: `~/fpga_mcp/content/` has extracted text
- Run extraction: `python scripts/ingest.py`

**Issue: "Token warnings during indexing"**
- **This is normal!** Warnings appear during semantic chunking
- Final chunks are validated and split to respect limits
- No warnings during actual embedding = working correctly

---

## Credits

**Developed by:** FPGA MCP Team
**Date:** 2025-10-27
**Optimization:** Token-aware chunking with semantic boundaries
**Documentation:** See `~/mchp-mcp-core/docs/CHUNKING_TOKEN_LIMIT_RECOMMENDATIONS.md`

---

## Quick Demo Script for Coworker

```bash
# 1. Show indexed documents
cd ~/fpga_mcp
python -c "
import sys; sys.path.insert(0, 'src')
from fpga_rag.indexing import DocumentEmbedder
embedder = DocumentEmbedder()
info = embedder.vector_store.get_collection_info()
print(f'📚 Indexed: {info[\"points_count\"]:,} chunks from 7 PolarFire docs')
"

# 2. Run search demo
python scripts/test_indexing.py

# 3. Try custom query
python -c "
import sys; sys.path.insert(0, 'src')
from fpga_rag.indexing import DocumentEmbedder
from mchp_mcp_core.storage.schemas import SearchQuery

embedder = DocumentEmbedder()
query = SearchQuery(query='YOUR QUESTION HERE', top_k=3)
results = embedder.vector_store.search(query)

print(f'\\n🔍 Results for: {query.query}\\n')
for i, r in enumerate(results, 1):
    print(f'{i}. {r.title} (Page {r.slide_or_page})')
    print(f'   Score: {r.score:.3f}')
    print(f'   {r.snippet[:150]}...\\n')
"
```

**That's it!** The system is ready to demo. 🎉
