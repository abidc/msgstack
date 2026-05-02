# OpenCode Instructions — Two fixes

---

## Fix 1 — Prevent orphaned houses from failed sync retries

**Files**: `src/store.py`, `src/sources/sync.py`

### Problem

When a Drive file sync fails mid-way (e.g. Pinecone or graph step fails after the house is already written to DB), the partially-created house is left in the database. The next retry only cleans up the house ID stored in the source_file record — but if the failure happened before `upsert_source_file` was called with the new `house_id`, the source_file still points to the old house, and the orphaned new house is never cleaned up. Multiple retries compound this, creating several stale partial houses.

### Fix 1a — Add `delete_houses_by_source_id` to `src/store.py`

Find the `delete_house` method in `src/store.py` (around line 619). Add a new method directly after it:

```python
def delete_houses_by_source_id(self, source_id: str) -> int:
    """Delete all houses with the given source_id. Returns count deleted."""
    with self.session() as s:
        rows = s.query(HouseModel).filter(HouseModel.source_id == source_id).all()
        count = len(rows)
        for row in rows:
            s.delete(row)
        if count:
            s.commit()
            _invalidate_graph()
        return count
```

### Fix 1b — Use it in `src/sources/sync.py` before committing

In `_ingest_file` (around line 207), replace the existing pre-commit cleanup block:

```python
        # Check if a house already exists for this Drive file; if so, delete and recreate
        existing = self.store.get_source_file_by_drive_id(conn["id"], file_info.file_id)
        if existing and existing.get("house_id"):
            try:
                store.delete_house(existing["house_id"])
            except Exception:
                pass
```

With:

```python
        # Delete any houses previously created for this Drive file (including orphans
        # from failed retries that were never linked back to the source_file record).
        store.delete_houses_by_source_id(file_info.file_id)
```

This covers both the tracked house (via source_file.house_id) and any orphaned houses from prior failed attempts, because all houses created from this Drive file share `source_id = file_info.file_id`.

Note: `_commit_structured_house` sets `source_id = filename` where `filename` is `file_info.file_id`, so the `source_id` column matches exactly.

---

## Fix 2 — Parallelize chunk structuring

**File**: `src/pipeline/structure.py`

## Problem

Large documents are split into overlapping 20k-char chunks and each chunk requires one LLM call. Those calls are currently made sequentially (one at a time), so a 200k-char document takes 10+ sequential calls × ~25s each ≈ 4-5 minutes total. They are fully independent and can run in parallel.

## Change required

### 1. Add `ThreadPoolExecutor` import at the top of the file

The file already imports `time`, `os`, `re`, etc. Add one more import alongside them:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
```

### 2. Replace the sequential list comprehension in `structure()` with parallel execution

**Location**: `src/pipeline/structure.py`, inside the `structure()` method, the `else` branch (currently lines 347–350):

```python
        else:
            chunks = self._split_text(text)
            houses = [self._structure_single_chunk(chunk, source_name, prompt_template) for chunk in chunks]
            house = self._merge_structures(houses, source_name)
```

Replace with:

```python
        else:
            chunks = self._split_text(text)
            houses = [None] * len(chunks)
            max_workers = min(len(chunks), 5)  # cap at 5 to avoid rate-limit bursts
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {
                    pool.submit(self._structure_single_chunk, chunk, source_name, prompt_template): i
                    for i, chunk in enumerate(chunks)
                }
                for future in as_completed(futures):
                    houses[futures[future]] = future.result()
            house = self._merge_structures(houses, source_name)
```

**Why `as_completed` with index tracking instead of `map`**: `map` would re-raise exceptions on the wrong chunk and lose order; this approach preserves chunk order for `_merge_structures` while collecting results as they finish.

**Why cap at 5 workers**: OpenAI's default rate limit is ~500 RPM for GPT-4o-mini. 5 concurrent calls is safe; going higher risks 429s.

### 3. No other changes needed

- `_structure_single_chunk` is already thread-safe (it only reads `self.client` and `self.model`, and appends to `self._usage` which is a plain dict).
- Wait — `self._usage` IS shared state. Each `_structure_single_chunk` call does `self._usage["input_tokens"] += ...`. Fix this race condition by making the usage accumulation thread-safe.

Find `_structure_single_chunk` (around line 365) and locate this block inside `_llm_call_with_retry`:

```python
                if hasattr(self, "_usage") and response.usage:
                    self._usage["input_tokens"] += response.usage.prompt_tokens
                    self._usage["output_tokens"] += response.usage.completion_tokens
```

Replace with a thread-safe version using a lock. Add a `threading.Lock` to `__init__`:

**In `__init__`** (around line 331), add one line:

```python
    def __init__(self, openai_api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model
        self._usage_lock = threading.Lock()
```

And add `import threading` to the imports at the top of the file.

**In `_llm_call_with_retry`**, replace the usage accumulation:

```python
                if hasattr(self, "_usage") and response.usage:
                    self._usage["input_tokens"] += response.usage.prompt_tokens
                    self._usage["output_tokens"] += response.usage.completion_tokens
```

With:

```python
                if hasattr(self, "_usage") and response.usage:
                    with self._usage_lock:
                        self._usage["input_tokens"] += response.usage.prompt_tokens
                        self._usage["output_tokens"] += response.usage.completion_tokens
```

## Expected outcome

A 10-chunk document that previously took ~4 minutes will now complete in ~25-35 seconds (the time of the slowest single chunk). After making these changes, restart the server.
