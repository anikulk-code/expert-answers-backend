#!/usr/bin/env python3
"""
Incrementally refresh the AskSwami Q&A corpus from the YouTube playlist.

Stages (run all by default, or pick one with --stage):

  chapters    Find playlist videos we haven't seen, extract their chapters from
              the video description, merge into askswami_chapters.json
  questions   Project askswami_chapters.json -> askswami_questions.json,
              filtering out "Intro" chapter markers (they are not questions)
  cosmos      Insert questions that aren't in Cosmos yet (deduped by video_link)
  embeddings  Report/backfill documents that have no embedding

DRY RUN BY DEFAULT. Nothing is written to disk or to Cosmos unless you pass
--apply. This script never deletes or overwrites existing Cosmos documents.

Examples:
    python scripts/refresh_corpus.py                     # see what would change
    python scripts/refresh_corpus.py --apply             # do it
    python scripts/refresh_corpus.py --apply --limit 5   # write only 5 new docs
    python scripts/refresh_corpus.py --stage chapters    # just check for new videos
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

CHAPTERS_PATH = os.path.join(REPO_ROOT, "askswami_chapters.json")
QUESTIONS_PATH = os.path.join(REPO_ROOT, "askswami_questions.json")
EMBEDDINGS_SCRIPT = os.path.join(REPO_ROOT, "scripts", "add_embeddings_to_questions.py")

# Vocabulary used to spot chapter titles that mark a section rather than ask a
# question. A title counts as a marker only when *every* word in it comes from
# this set, so any substantive word ("meditation", "heart", "Brahman") keeps the
# row as a question.
#
# Two weaker rules were tried and rejected against the real data:
#   - "title has no trailing '?'" would drop 61 legitimate questions phrased as
#     statements, e.g. "Dealing with sleepiness during meditation."
#   - "chapter starts at 0:00" would drop "On Vedantic meditation.", a real
#     question that happens to open its video.
# The naming also drifts over time -- older videos say "Intro", 2026 ones say
# "Invocation and opening" -- so exact string matching goes stale.
MARKER_WORDS = {
    "a", "and", "announcement", "announcements", "begin", "begins", "chant",
    "chanting", "chants", "closing", "conclusion", "end", "greeting",
    "greetings", "intro", "introduction", "invocation", "opening", "prayer",
    "prayers", "preliminaries", "q", "q&a", "qa", "remarks", "session",
    "start", "the", "welcome", "with",
}


def is_section_marker(title: str) -> bool:
    """True when the title is a section marker rather than a question."""
    words = re.findall(r"[a-z&]+", (title or "").strip().lower())
    return bool(words) and all(w in MARKER_WORDS for w in words)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def banner(text: str) -> None:
    print()
    print("=" * 70)
    print(text)
    print("=" * 70)


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def chapter_sort_key(row: Dict[str, Any]):
    """Sort key matching the existing askswami_chapters.json ordering.

    Used with reverse=True, which yields publishedAt descending and, within a
    video, chapter_seconds descending. That second part is incidental rather
    than intentional, but it is the existing on-disk order and reproducing it
    keeps the diff to genuinely new rows.
    """
    try:
        dt = datetime.datetime.fromisoformat(row["publishedAt"].replace("Z", "+00:00"))
    except Exception:
        dt = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    return (dt, row.get("chapter_seconds", 0))


def is_question_row(chapter_row: Dict[str, Any]) -> bool:
    title = (chapter_row.get("chapter_title") or "").strip()
    return bool(title) and not is_section_marker(title)


# --------------------------------------------------------------------------
# stage: chapters
# --------------------------------------------------------------------------

def stage_chapters(apply: bool, refetch_all: bool) -> List[Dict[str, Any]]:
    banner("STAGE 1/4  chapters -- fetch new videos from the playlist")

    from app.ManualScripts.TempChapterExtractor import (
        PLAYLIST_ID,
        YOUTUBE_API_KEY,
        extract_chapters_from_description,
        fetch_all_playlist_video_ids,
        fetch_video_snippets,
    )

    if not YOUTUBE_API_KEY:
        print("ERROR: YOUTUBE_API_KEY is not set. Add it to .env and retry.")
        sys.exit(1)

    existing: List[Dict[str, Any]] = load_json(CHAPTERS_PATH, [])
    known_video_ids: Set[str] = {r["video_id"] for r in existing}
    print(f"On disk: {len(existing)} chapter rows across {len(known_video_ids)} videos")

    print(f"Listing playlist {PLAYLIST_ID} ...")
    playlist_video_ids = fetch_all_playlist_video_ids(PLAYLIST_ID)
    print(f"Playlist currently has {len(playlist_video_ids)} videos")

    if refetch_all:
        target_ids = playlist_video_ids
        print(f"--refetch-all: re-fetching all {len(target_ids)} videos")
    else:
        target_ids = [v for v in playlist_video_ids if v not in known_video_ids]
        print(f"New videos not yet in askswami_chapters.json: {len(target_ids)}")

    if not target_ids:
        print("\nNothing to fetch -- chapters file is already current.")
        return existing

    print(f"Fetching snippets for {len(target_ids)} video(s) ...")
    videos = fetch_video_snippets(target_ids)

    new_rows: List[Dict[str, Any]] = []
    videos_with_no_chapters: List[Tuple[str, str]] = []

    for v in videos:
        snippet = v.get("snippet", {})
        video_id = v.get("id")
        video_title = snippet.get("title", "")
        description = snippet.get("description", "")
        published_at = snippet.get("publishedAt", "")
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        chapters = extract_chapters_from_description(description)
        if not chapters:
            videos_with_no_chapters.append((video_id, video_title))
            continue

        for ts, chapter_title, seconds in chapters:
            new_rows.append({
                "playlist_id": PLAYLIST_ID,
                "video_id": video_id,
                "video_title": video_title,
                "publishedAt": published_at,
                "video_url": video_url,
                "chapter_title": chapter_title,
                "chapter_timestamp": ts,
                "chapter_seconds": seconds,
                "chapter_url": f"{video_url}&t={seconds}s",
                "description": description,
            })

    refetched_ids = {v.get("id") for v in videos}
    merged = [r for r in existing if r["video_id"] not in refetched_ids] + new_rows
    merged.sort(key=chapter_sort_key, reverse=True)

    question_rows = [r for r in new_rows if is_question_row(r)]
    skipped = len(new_rows) - len(question_rows)

    print()
    print(f"  videos fetched        : {len(videos)}")
    print(f"  new chapter rows      : {len(new_rows)}")
    print(f"    -> real questions   : {len(question_rows)}")
    print(f"    -> section markers  : {skipped} (filtered out at the questions stage)")
    print(f"  chapters file total   : {len(existing)} -> {len(merged)}")

    # A video whose description doesn't use a recognized timestamp format
    # yields zero chapters and would otherwise vanish silently.
    if videos_with_no_chapters:
        print()
        print(f"  !! {len(videos_with_no_chapters)} video(s) produced NO chapters --")
        print("     their descriptions likely use an unrecognized timestamp format.")
        print("     Check these by hand before trusting this run:")
        for vid, title in videos_with_no_chapters:
            print(f"       {vid}  {title[:60]}")

    if new_rows:
        print()
        print("  sample of new rows:")
        for r in new_rows[:5]:
            print(f"    [{r['chapter_timestamp']}] {r['chapter_title'][:64]}")

    if apply:
        write_json(CHAPTERS_PATH, merged)
        print(f"\n  WROTE {CHAPTERS_PATH}")
        print("  REMINDER: commit this file and push to main. get_playlist_id() reads")
        print("  it at runtime, so until it ships, new answers return playlistId: null.")
        print("  (.github/workflows deploys to Azure on push to main -- a commit left")
        print("  on a side branch won't deploy until it is merged.)")
    else:
        print("\n  [dry run] askswami_chapters.json not modified. Pass --apply to write.")

    # Returned so later stages see what this stage *would* produce. Without
    # this, a dry run reports "0 new questions" because nothing hit disk.
    return merged


# --------------------------------------------------------------------------
# stage: questions
# --------------------------------------------------------------------------

def stage_questions(apply: bool,
                    chapters: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    banner("STAGE 2/4  questions -- project chapters into askswami_questions.json")

    if chapters is None:
        chapters = load_json(CHAPTERS_PATH, [])
    if not chapters:
        print("No chapters file found -- run the chapters stage first.")
        return []

    existing: List[Dict[str, Any]] = load_json(QUESTIONS_PATH, [])
    existing_urls = {q.get("url") for q in existing}

    projected = [
        {
            "question": r["chapter_title"].strip(),
            "url": r["chapter_url"],
            "timestamp": r["chapter_timestamp"],
        }
        for r in chapters
        if is_question_row(r)
    ]

    filtered_out = len(chapters) - len(projected)
    added = [q for q in projected if q["url"] not in existing_urls]
    projected_urls = {q["url"] for q in projected}
    removed = [q for q in existing if q.get("url") not in projected_urls]

    print(f"  chapter rows            : {len(chapters)}")
    print(f"  section markers dropped : {filtered_out}")
    print(f"  questions file          : {len(existing)} -> {len(projected)}")
    print(f"    newly added           : {len(added)}")
    print(f"    dropped               : {len(removed)}")

    if removed:
        print()
        print("  dropped entries (section markers already in the old file):")
        for q in removed[:5]:
            print(f"    {q.get('question', '')[:64]}")
        if len(removed) > 5:
            print(f"    ... and {len(removed) - 5} more")

    if added:
        print()
        print("  sample of newly added questions:")
        for q in added[:5]:
            print(f"    [{q['timestamp']}] {q['question'][:64]}")

    if apply:
        write_json(QUESTIONS_PATH, projected)
        print(f"\n  WROTE {QUESTIONS_PATH}")
    else:
        print("\n  [dry run] askswami_questions.json not modified. Pass --apply to write.")

    return projected


# --------------------------------------------------------------------------
# stage: cosmos
# --------------------------------------------------------------------------

def exit_on_cosmos_error(e: Exception) -> None:
    """Turn the common Cosmos connection failures into actionable advice.

    The firewall case in particular is expected when running from a new machine
    or a changed IP, and a raw stack trace buries the one thing worth knowing.
    """
    message = str(e)
    print()
    if "Forbidden" in message and "firewall" in message.lower():
        print("Cosmos DB refused the connection: this machine's IP is not allowed.")
        print("Add your current IP to the account's firewall allowlist:")
        print("  Azure Portal -> your Cosmos account -> Networking ->")
        print("  Public access -> add your IP (or enable 'Allow access from Azure Portal')")
        print("See COSMOS_DB_FIREWALL_FIX.md for the full walkthrough.")
        print()
        print("Local file stages still work meanwhile:")
        print("  python scripts/refresh_corpus.py --stage chapters --apply")
        print("  python scripts/refresh_corpus.py --stage questions --apply")
    elif "Unauthorized" in message or "authorization" in message.lower():
        print("Cosmos DB rejected the credentials. Check AZURE_COSMOS_KEY in .env.")
    else:
        print(f"Cosmos DB error: {message.splitlines()[0]}")
    sys.exit(1)


def fetch_existing_video_links(container) -> Set[str]:
    """Pull every video_link already in Cosmos in a single query.

    One cross-partition scan beats one query per candidate question, which is
    what the older migration script does.
    """
    query = "SELECT VALUE c.video_link FROM c WHERE IS_DEFINED(c.video_link)"
    links = container.query_items(query=query, enable_cross_partition_query=True)
    return {link for link in links if link}


def build_question_doc(question_text: str, url: str, canonical_text: str,
                       topics: List[str], entities: List[Dict],
                       playlist_link: Optional[str]) -> Dict[str, Any]:
    """Build a Cosmos document matching the shape written by
    scripts/migrate_questions_to_cosmos.py (see COSMOS_SCHEMA.md)."""
    from app.services.cosmos_service import normalize_question

    full_video_link = url.split("&t=")[0] if "&t=" in url else url
    normalized = normalize_question(question_text)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return {
        "id": str(uuid.uuid4()),
        "domain": "philosophy",
        "questionText": question_text,
        "normalizedText": normalized,
        "canonical_text": canonical_text,
        "topics": topics,
        "entities": entities,
        "tags": [],
        "video_link": url,
        "full_video_link": full_video_link,
        "playlist_link": playlist_link,
        "embedding": None,          # backfilled by the embeddings stage
        "embeddingModel": None,
        "embeddingDim": None,
        "voteUp": 0,
        "timesAsked": 1,
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
        # backward-compatibility mirrors, kept in sync by the app's writers
        "question": question_text,
        "question_normalized": normalized,
        "votes": 0,
        "created_at": now,
        "updated_at": now,
    }


def stage_cosmos(apply: bool, limit: Optional[int],
                 questions: Optional[List[Dict[str, Any]]] = None) -> None:
    banner("STAGE 3/4  cosmos -- insert questions that aren't in the database yet")

    from app.services.cosmos_service import get_cosmos_container
    from app.services.llm_service import get_playlist_id
    from app.services.question_processor import process_question

    if questions is None:
        questions = load_json(QUESTIONS_PATH, [])

    # Re-apply the marker filter here as well as in the questions stage. Running
    # `--stage cosmos` on its own reads whatever is on disk, and an unrefreshed
    # askswami_questions.json still carries section markers -- without this,
    # that path would insert them as questions.
    markers = [q for q in questions if is_section_marker(q.get("question", ""))]
    if markers:
        questions = [q for q in questions if not is_section_marker(q.get("question", ""))]
        print(f"  filtered out {len(markers)} section marker(s) from the questions file")
        print("  (run --stage questions --apply to clean up the file itself)")

    if not questions:
        print("No questions file found -- run the questions stage first.")
        return

    print("Reading existing video_links from Cosmos ...")
    try:
        container = get_cosmos_container()
        existing_links = fetch_existing_video_links(container)
    except Exception as e:
        exit_on_cosmos_error(e)
    print(f"  Cosmos holds {len(existing_links)} distinct video_link values")

    todo = [q for q in questions if q.get("url") not in existing_links]
    print(f"  questions in file     : {len(questions)}")
    print(f"  already in Cosmos     : {len(questions) - len(todo)}")
    print(f"  to insert             : {len(todo)}")

    if limit is not None and len(todo) > limit:
        todo = todo[:limit]
        print(f"  --limit {limit}: only the first {len(todo)} will be processed")

    if not todo:
        print("\nNothing to insert -- Cosmos is already current.")
        return

    if not apply:
        print()
        print("  sample of documents that WOULD be written:")
        for q in todo[:5]:
            print(f"    [{q['timestamp']}] {q['question'][:64]}")
        print(f"\n  [dry run] Cosmos not modified. Pass --apply to insert {len(todo)} document(s).")
        print("  Note: each insert costs one process_question() LLM call.")
        return

    written = 0
    failed = 0
    llm_fallbacks = 0

    for i, q in enumerate(todo, start=1):
        question_text = (q.get("question") or "").strip()
        url = q.get("url") or ""
        if not question_text or not url:
            print(f"  [{i}/{len(todo)}] skipped -- missing question text or url")
            continue

        try:
            processed = process_question(question_text)
            canonical_text = processed["canonical_text"]
            topics = processed["topics"]
            entities = processed["entities"]
        except Exception as e:
            # Match the migration script's behaviour: degrade rather than abort.
            # The embedding is what drives retrieval, so an empty topics list is
            # survivable -- but count these so they're visible.
            print(f"  [{i}/{len(todo)}] LLM processing failed ({e}); using fallback values")
            canonical_text = question_text.lower()
            topics = []
            entities = []
            llm_fallbacks += 1

        playlist_link = None
        video_id = None
        base_url = url.split("&t=")[0] if "&t=" in url else url
        if "watch?v=" in base_url:
            video_id = base_url.split("watch?v=")[1].split("&")[0]
        if video_id:
            try:
                playlist_id = get_playlist_id(video_id)
                if playlist_id:
                    playlist_link = f"https://www.youtube.com/playlist?list={playlist_id}"
            except Exception:
                pass  # playlist lookup is best-effort

        doc = build_question_doc(question_text, url, canonical_text, topics,
                                 entities, playlist_link)

        try:
            container.create_item(body=doc)
            written += 1
            print(f"  [{i}/{len(todo)}] inserted: {question_text[:58]}")
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(todo)}] FAILED: {question_text[:48]} -- {e}")

        if i % 10 == 0:
            time.sleep(0.5)  # courtesy pause, matches the migration script

    print()
    print(f"  inserted      : {written}")
    print(f"  failed        : {failed}")
    if llm_fallbacks:
        print(f"  LLM fallbacks : {llm_fallbacks} (documents written with empty topics/entities)")
    if written:
        print("\n  These documents have embedding: null -- run the embeddings stage next.")


# --------------------------------------------------------------------------
# stage: embeddings
# --------------------------------------------------------------------------

def stage_embeddings(apply: bool) -> None:
    banner("STAGE 4/4  embeddings -- backfill documents with no embedding")

    from app.services.cosmos_service import get_cosmos_container

    query = """
    SELECT VALUE COUNT(1) FROM c
    WHERE NOT IS_ARRAY(c.embedding)
       OR ARRAY_LENGTH(c.embedding) = 0
    """
    try:
        container = get_cosmos_container()
        missing = list(container.query_items(query=query, enable_cross_partition_query=True))
    except Exception as e:
        exit_on_cosmos_error(e)
    count = missing[0] if missing else 0
    print(f"  documents missing an embedding: {count}")

    if count == 0:
        print("\nNothing to backfill.")
        return

    # Questions submitted through the upvote queue have no video_link and no
    # embedding. They're picked up here too, which is harmless, but worth
    # naming so the count isn't mistaken for newly ingested answers.
    try:
        queue_query = """
        SELECT VALUE COUNT(1) FROM c
        WHERE (NOT IS_ARRAY(c.embedding) OR ARRAY_LENGTH(c.embedding) = 0)
          AND (NOT IS_DEFINED(c.video_link) OR IS_NULL(c.video_link))
        """
        queued = list(container.query_items(query=queue_query,
                                            enable_cross_partition_query=True))
        queue_count = queued[0] if queued else 0
        if queue_count:
            print(f"    of which {queue_count} are user-submitted queue questions "
                  f"(no video_link)")
    except Exception:
        pass  # informational only

    if not apply:
        print("\n  [dry run] No embeddings generated. With --apply this runs:")
        print(f"    python {os.path.relpath(EMBEDDINGS_SCRIPT, REPO_ROOT)}")
        return

    print(f"\n  Delegating to {os.path.relpath(EMBEDDINGS_SCRIPT, REPO_ROOT)} ...")
    print("  (embeds full questionText with text-embedding-3-large @ 3072 dims)")
    result = subprocess.run([sys.executable, EMBEDDINGS_SCRIPT], cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"\n  Embedding backfill exited with code {result.returncode}")
        sys.exit(result.returncode)


# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incrementally refresh the AskSwami Q&A corpus.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--apply", action="store_true",
                        help="actually write changes (default is a dry run)")
    parser.add_argument("--stage", default="all",
                        choices=["all", "chapters", "questions", "cosmos", "embeddings"],
                        help="run a single stage instead of the whole pipeline")
    parser.add_argument("--limit", type=int, default=None,
                        help="cap how many new documents the cosmos stage writes")
    parser.add_argument("--refetch-all", action="store_true",
                        help="re-fetch every playlist video, not just unseen ones "
                             "(use when a video description was edited after publishing)")
    args = parser.parse_args()

    mode = "APPLY -- changes will be written" if args.apply else "DRY RUN -- nothing will be written"
    banner(f"Corpus refresh  [{mode}]")

    # Results are threaded between stages so that a dry run reports what the
    # pipeline *would* do, rather than what the untouched files currently say.
    chapters = None
    questions = None

    if args.stage in ("all", "chapters"):
        chapters = stage_chapters(args.apply, args.refetch_all)
    if args.stage in ("all", "questions"):
        questions = stage_questions(args.apply, chapters)
    if args.stage in ("all", "cosmos"):
        stage_cosmos(args.apply, args.limit, questions)
    if args.stage in ("all", "embeddings"):
        stage_embeddings(args.apply)

    banner("Done")
    if not args.apply:
        print("This was a dry run. Re-run with --apply to make these changes.")
    else:
        print("Commit askswami_chapters.json and push to main -- get_playlist_id()")
        print("reads it at runtime for the playlistId field, and the Azure deploy")
        print("workflow only triggers on main.")
        print()
        print("Optional follow-up: python scripts/analyze_topics_from_db.py")
        print("to see whether MAIN_TAGS_DB in app/routers/tags.py needs new entries.")


if __name__ == "__main__":
    main()
