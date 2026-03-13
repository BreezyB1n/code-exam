# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a coding exam: build a search engine web app that parses, indexes, and searches 10 HTML-format On-Call SOP documents in `data/`. The project has three progressive phases.

## Phases

- **Phase 1**: HTML parsing + keyword search (`POST /documents`, `GET /search`, `GET /`)
- **Phase 2**: Inverted index + TF-IDF scoring, multi-keyword intersection
- **Phase 3**: Semantic search via embeddings (`mode=semantic` vs `mode=keyword`)

## API Contract

```
POST /documents   — body: {id, html} → 201 {id, title}
GET  /search?q=   — returns {query, results: [{id, title, snippet, score}]}
GET  /search?q=&mode=semantic|keyword
GET  /            — returns search UI (input, button, results list)
```

## HTML Parsing Rules

- Extract title from `<title>` tag
- Strip all HTML tags for plain text; **exclude** `<script>` and `<style>` content from indexing
- Decode HTML entities (`&amp;`, `&lt;`, `&#39;`, etc.)

## TF-IDF Formula (Phase 2)

```
TF(t,d)  = count(t in d) / total_words(d)
IDF(t)   = log(total_docs / docs_containing_t)
score    = TF × IDF
multi-kw = Σ score(ti, d), intersection only
Tokenize: split on whitespace + punctuation, lowercase
```

## Data Files

`data/doc1.html` through `data/doc10.html` — ten department SOP documents with deliberate edge cases: `<script>`/`<style>` tags, HTML entities, malformed HTML, deep nesting.

Load all docs via `POST /documents` with id = filename without extension (e.g., `doc1`).

## Key Validation Cases

| Query | Expected |
|---|---|
| `故障` | all 10 docs |
| `GPU` | doc8 only |
| `replication` | empty (it's in a `<script>` tag in doc2) |
| `&` | doc3, doc6, doc8, doc10 (decoded entity) |
| `on-call` | all 10 docs |

# Interactive Planning
1. Before writing any code, describe your method and wait for approval.

2. If the requirements I provide are vague, please raise clarification questions before writing code.

3. After completing any code writing, list edge cases and suggest test cases to cover them.

4. If the task requires modifications to more than 3 files, stop and break it down into smaller tasks.

5. When a bug occurs, write a test that can reproduce the bug first, then fix it until the test passes.

6. Each time I correct you, reflect on what you did wrong and make a plan to never make the same mistake again.
