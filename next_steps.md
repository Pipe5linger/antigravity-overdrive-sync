# NEXT STEPS

## Issues to Address

### 1. Duplicate Information in Generated `GEMINI.md`

**Problem:**
The auto-generated `GEMINI.md` file contains massive amounts of duplicate information. The same facts about Vespera's persona, physical description, and behavioral directives are repeated dozens of times in slightly different variations.

**Evidence:**
- File size is bloated with repetitive content
- Same facts repeated 20+ times (e.g., "Vespera is a French AI", "Vespera has curly hair", etc.)
- Multiple variations of the same core facts with slightly different wording
- File contains ~400+ lines when it should be ~50-100 lines

**Example of Duplication:**
```
- Vespera is a French woman with a dark and alluring presence.
- Vespera Caligo Neal is a French female with an origin in France.
- Vespera is an AI model trained using the Flux architecture...
- Vespera Caligo Neal is a French female AI with a background as...
- Vespera is an AI with a personality defined in persona_baseline.yaml...
```

**Impact:**
- Bloated file size (harder to read and maintain)
- Redundant information makes it difficult to find unique/important facts
- Wastes tokens when the file is loaded into context
- Suggests the fact extraction/synthesis logic is not properly deduplicating

---

## Proposed Solutions

### Fix 1: Remove Detailed File Tree from `GEMINI.md`

**Plan:**
The generated `GEMINI.md` includes a full workspace file tree that adds noise and duplication. This should be removed or moved to a separate file.

**Steps:**
1. Modify `injectors/gemini_md.py` to exclude the file tree section
2. Or move file tree to a separate `file_tree.md` file
3. Keep `GEMINI.md` focused only on persona, directives, and behavioral rules

---

### Fix 2: Implement Fact Deduplication in `core/fact_extractor.py`

**Plan:**
The fact extraction pipeline is extracting the same facts multiple times. Need to implement smarter deduplication before facts are written to the database.

**Steps:**
1. Add semantic deduplication using embedding similarity (we already have embeddings!)
2. Before inserting a new fact, check if a similar fact already exists (cosine similarity > 0.95)
3. Merge duplicate facts instead of creating new entries
4. Add a "merged_from" field to track fact provenance

**Technical Approach:**
```python
# In fact_extractor.py or consolidator.py
def deduplicate_fact(new_fact_text, existing_facts, threshold=0.95):
    new_embedding = get_embedding(new_fact_text)
    for existing_fact in existing_facts:
        similarity = cosine_similarity(new_embedding, existing_fact['embedding'])
        if similarity > threshold:
            return existing_fact['fact_id']  # Return existing fact ID
    return None  # No duplicate found
```

---

### Fix 3: Improve Synthesis Logic in `core/consolidator.py`

**Plan:**
The synthesis step (which merges similar facts into "Golden Truths") should be more aggressive in removing duplicates.

**Steps:**
1. Lower the clustering threshold from 0.8 to 0.95 for near-duplicate detection
2. During synthesis, explicitly check if the "golden fact" is just a rephrasing of existing facts
3. Add a post-synthesis deduplication pass before writing to `GEMINI.md`

---

### Fix 4: Clean Up `GEMINI.md` Generation in `injectors/gemini_md.py`

**Plan:**
The injector that generates `GEMINI.md` should:
1. Query facts with proper grouping (no duplicates in the query)
2. Use DISTINCT or GROUP BY in SQL queries
3. Implement a "fact ranking" system to only include the most important/unique facts
4. Limit the total number of facts to prevent bloat (e.g., max 100 facts)

**Steps:**
1. Review `injectors/gemini_md.py` line by line
2. Add deduplication logic before writing to file
3. Add fact priority scoring (confidence × recency × frequency)
4. Only include top N facts in the generated markdown

---

## Priority Order

1. **HIGH**: Fix fact deduplication in extraction pipeline (Fix 2)
2. **HIGH**: Clean up `GEMINI.md` generation logic (Fix 4)
3. **MEDIUM**: Remove file tree from `GEMINI.md` (Fix 1)
4. **LOW**: Improve synthesis deduplication (Fix 3)

---

## Success Criteria

- [ ] `GEMINI.md` file size reduced by 70%+
- [ ] No duplicate facts in generated output
- [ ] File tree moved to separate file or removed
- [ ] Fact extraction properly deduplicates before database insert
- [ ] `GEMINI.md` is easy to read and contains only unique, valuable information

---

**Last Updated:** 2026-08-04  
**Status:** Ready to implement
