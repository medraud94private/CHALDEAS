# Book Extraction: GPT-5.1 vs Local Model Comparison

## Overview

This report compares entity extraction performance between OpenAI's GPT-5.1-chat-latest and a local model (llama3.1:8b-instruct-q4_0) when processing historical/mythological texts from Project Gutenberg.

## Test Data

4 books processed:
1. **Greek/Roman Mythology** (868KB, 370 chunks)
2. **Plato Republic** (1.2MB, 531 chunks)
3. **Marcus Aurelius Meditations** (738KB, 313 chunks)
4. **Bulfinch Mythology** (675KB, 285 chunks)

Total: 1,499 chunks across all books

---

## Results Summary

| Metric | GPT-5.1-chat-latest | llama3.1:8b (Local) |
|--------|---------------------|---------------------|
| **Total Time** | ~72 min | 369.6 min (6.16 hrs) |
| **Cost** | $4.20 | $0 |
| **Persons Extracted** | 2,032 | 1,367 |
| **Locations Extracted** | 999 | 728 |
| **Speed** | ~21 chunks/min | ~4 chunks/min |

---

## Per-Book Breakdown

### Greek/Roman Mythology

| Entity Type | GPT-5.1 | Local | Ratio |
|-------------|---------|-------|-------|
| Persons | 1,202 | 800 | 66% |
| Locations | 607 | 482 | 79% |
| Concepts | 695 | 638 | 92% |
| Events | 550 | 403 | 73% |
| **Time** | ~15 min | 119 min | 8x slower |
| **Cost** | $1.15 | $0 | - |

### Plato Republic

| Entity Type | GPT-5.1 | Local | Ratio |
|-------------|---------|-------|-------|
| Persons | 393 | 201 | 51% |
| Locations | 169 | 68 | 40% |
| Concepts | 1,593 | 754 | 47% |
| Events | 137 | 36 | 26% |
| **Time** | ~22 min | 96.2 min | 4x slower |
| **Cost** | $1.35 | $0 | - |

### Marcus Aurelius Meditations

| Entity Type | GPT-5.1 | Local | Ratio |
|-------------|---------|-------|-------|
| Persons | 95 | 20 | 21% |
| Locations | 44 | 1 | 2% |
| Concepts | 870 | 37 | 4% |
| Events | 15 | 0 | 0% |
| **Time** | ~14 min | 51.1 min | 4x slower |
| **Cost** | $0.80 | $0 | - |

### Bulfinch Mythology

| Entity Type | GPT-5.1 | Local | Ratio |
|-------------|---------|-------|-------|
| Persons | 925 | 743 | 80% |
| Locations | 402 | 327 | 81% |
| Concepts | 554 | 550 | 99% |
| Events | 468 | 401 | 86% |
| **Time** | ~20 min | 103.3 min | 5x slower |
| **Cost** | $0.90 | $0 | - |

---

## Analysis

### Extraction Quality

1. **Mythology texts** (Greek Myths, Bulfinch): Local model performs relatively well
   - Captures 66-80% of persons, 79-81% of locations
   - Entity-rich texts with clear named entities work better

2. **Philosophy texts** (Plato, Marcus Aurelius): Local model struggles significantly
   - Only 21-51% of persons captured
   - Abstract philosophical texts are harder for smaller models
   - Marcus Aurelius: Almost no entities extracted (20 persons, 1 location)

### Speed vs Cost Trade-off

| Factor | GPT-5.1 | Local |
|--------|---------|-------|
| Processing speed | ~5x faster | Baseline |
| Cost per book | ~$1.00 | $0 |
| Quality (mythology) | 100% | 70-80% |
| Quality (philosophy) | 100% | 20-50% |

### Recommendations

1. **For mythology/history texts**: Local model is viable for cost-sensitive applications
   - 70-80% extraction rate is acceptable for bulk processing
   - Can be post-processed with DB matching to improve coverage

2. **For philosophy/abstract texts**: GPT-5.1 recommended
   - Local model misses too many entities
   - Worth the ~$1/book cost for quality

3. **Hybrid approach**:
   - Use local model for initial bulk processing (free)
   - Run GPT-5.1 on texts where local model extracts < 50 entities
   - Estimated savings: 50-70% of API costs

---

## Technical Details

### GPT-5.1-chat-latest
- Token usage: ~630K input, ~115K output (total)
- Rate: ~$0.003 per chunk
- Max tokens per request: 800

### llama3.1:8b-instruct-q4_0
- Running on Ollama locally
- Temperature: 0.1 (low randomness)
- Timeout: 120s per chunk
- Average time: ~20s per chunk

---

## Files

- GPT-5.1 results: `poc/data/book_samples/extraction_results.json`
- Local results: `poc/data/book_samples/extraction_results_local.json`
- Scripts: `poc/scripts/test_book_extract_openai.py`, `poc/scripts/test_book_extract_local.py`

---

## Conclusion

For Chaldeas source ingestion pipeline:

1. **Recommended**: Use local model for mythology/history books (free, 70-80% coverage)
2. **Philosophy texts**: Pay for GPT-5.1 (better quality justifies cost)
3. **DB-first matching**: Always match against existing DB entities first (free) before LLM extraction
4. **Estimated cost**: Processing 100 books with hybrid approach = ~$30-50 vs ~$100 with GPT-5.1 only
