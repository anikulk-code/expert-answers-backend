# Scripts

## refresh_corpus.py — routine corpus refresh

**This is the script to run when the AskSwami playlist has new sessions.** It is
incremental, re-runnable, and dry-run by default. It never deletes or overwrites
existing Cosmos documents.

### Usage

```bash
# See what would change (safe, writes nothing)
python scripts/refresh_corpus.py

# Do it
python scripts/refresh_corpus.py --apply

# Write only the first 5 new documents, to sanity-check before the full run
python scripts/refresh_corpus.py --apply --limit 5

# Just check whether the playlist has new videos
python scripts/refresh_corpus.py --stage chapters
```

### Options

- `--apply`: actually write. Without it, every stage reports and changes nothing.
- `--stage {all,chapters,questions,cosmos,embeddings}`: run one stage (default `all`)
- `--limit N`: cap how many new documents the `cosmos` stage writes
- `--refetch-all`: re-fetch every playlist video, not just unseen ones. Use when a
  video's description was edited after publishing.

### Stages

1. **chapters** — pages the playlist, finds videos not already in
   `askswami_chapters.json`, and extracts their chapters by regex-parsing
   timestamps out of each video description. (YouTube's Data API exposes no
   chapter markers, so the description is the only source.) Merges and re-sorts
   the file. **Any video that yields zero chapters is reported loudly** — that
   means its description uses an unrecognized timestamp format and a whole
   session would otherwise vanish silently.
2. **questions** — projects `askswami_chapters.json` into
   `askswami_questions.json`, dropping section markers (see below).
3. **cosmos** — inserts questions not already present, deduped by `video_link`.
   Reads every existing `video_link` in one query rather than one query per
   candidate. Each insert costs one `process_question()` LLM call.
4. **embeddings** — reports documents with no embedding and delegates to
   `add_embeddings_to_questions.py` under `--apply`.

### Section markers

Chapter lists include entries that aren't questions — older videos say `Intro`,
2026 videos say `Invocation and opening`. A title is treated as a marker only
when *every* word in it comes from a small marker vocabulary, so any substantive
word keeps the row as a question.

Two simpler rules were tried and rejected against real data:

- *"title has no trailing `?`"* would drop 61 legitimate questions phrased as
  statements, e.g. `Dealing with sleepiness during meditation.`
- *"chapter starts at 0:00"* would drop `On Vedantic meditation.`, a real
  question that happens to open its video.

Markers already in Cosmos from earlier runs are left alone; the filter only
applies going forward.

### After running

**Commit `askswami_chapters.json` and push to `main`.** `get_playlist_id()`
reads it from disk at runtime (`answers.py`, four call sites in `tags.py`), so
until the refreshed file ships, every new answer returns `playlistId: null`.

This is automatic, not a manual deploy:
`.github/workflows/main_expertanswersapi.yml` deploys the whole repo to the
`expertanswersapi` Azure Web App on push to `main`, and the file is tracked. The
one gotcha is the branch — a commit parked on a side branch doesn't deploy until
it's merged to `main`.

Optionally run `analyze_topics_from_db.py` afterwards to see whether
`MAIN_TAGS_DB` in `app/routers/tags.py` needs entries for newly introduced topics.

### Requirements

- `YOUTUBE_API_KEY`, `OPENAI_API_KEY`, and the `AZURE_COSMOS_*` vars in `.env`
- Your current IP allowed through the Cosmos firewall (see
  `COSMOS_DB_FIREWALL_FIX.md`) — the script reports this clearly if not.

---

## add_embeddings_to_questions.py

Backfills embeddings for documents that don't have one, found via
`embedding = null OR NOT IS_ARRAY(...) OR ARRAY_LENGTH(...) = 0`. Because
`refresh_corpus.py` writes new documents with `embedding: null`, this picks them
up automatically.

Embeds the full `questionText` (deliberately not `canonical_text`) with
`text-embedding-3-large` at 3072 dimensions. The query side matches this, so
**keep the model and dimension in sync** if you ever change them.

```bash
python scripts/add_embeddings_to_questions.py --dry-run
python scripts/add_embeddings_to_questions.py
python scripts/add_embeddings_to_questions.py --force   # re-embed everything
```

Options: `--dry-run`, `--model`, `--limit N`, `--batch-size N`,
`--skip-existing` (default on), `--force`.

---

## migrate_questions_to_cosmos.py — one-time bootstrap

Loads all of `askswami_questions.json` into Cosmos. Idempotent (skips questions
whose `normalizedText` already exists), but it is a **bootstrap** tool: for
routine updates prefer `refresh_corpus.py`, which only touches new content and
dedupes on `video_link`.

```bash
python scripts/migrate_questions_to_cosmos.py --dry-run
python scripts/migrate_questions_to_cosmos.py
python scripts/migrate_questions_to_cosmos.py --limit 10
```

Options: `--dry-run`, `--limit N`, `--batch-size N`, `--questions-file PATH`.

---

## Other scripts

| Script | Purpose | Safe to re-run |
|---|---|---|
| `analyze_topics_from_db.py` | Prints topic frequency from Cosmos. Read-only. | yes |
| `setup_vector_index.py` | One-time container creation with the vector + full-text policies. | n/a |
| `test_vector_search.py`, `diagnose_search_issues.py`, `test_question_processor.py` | Diagnostics, read-only. | yes |
| `delete_all_questions.py` | Deletes every document. Requires typing `DELETE ALL`. | destructive |
| `1_setup_data.py` | **Do not use.** Checks for an existing document by a UUID it just generated, so the check never matches and every run re-inserts the whole corpus. Superseded by `refresh_corpus.py`. | no |
| `2_add_embeddings.py` | Minimal earlier version of `add_embeddings_to_questions.py`; prefer that one. | yes |
| `regenerate_topics.py`, `regenerate_tags_from_db.py` | Rewrite `askswami_chapters_tagged.json`, which nothing reads at runtime. Both also write their "backup" *after* mutating, so the backups aren't real snapshots. | see note |
