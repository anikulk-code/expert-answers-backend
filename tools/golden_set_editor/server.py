#!/usr/bin/env python3
"""Temporary, zero-dependency editor for eval/golden_set.json."""

from __future__ import annotations

import json
import os
import re
import shutil
import ssl
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


TOOL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TOOL_DIR.parents[1]
GOLDEN_SET_PATH = BACKEND_DIR / "eval" / "golden_set.json"
CORPUS_PATH = BACKEND_DIR / "askswami_questions.json"
BACKUP_DIR = BACKEND_DIR / "eval" / "backups"
VALID_OUTCOMES = {"answered", "related_only", "unanswered"}
SOL_MODEL = "gpt-5.6-sol"


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_request_json(handler, max_bytes: int = 100_000):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > max_bytes:
        raise ValueError("Invalid request size.")
    return json.loads(handler.rfile.read(length))


def semantic_search(question: str, limit: int = 12):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured. Restart the editor after exporting it.")

    corpus = read_json(CORPUS_PATH)
    numbered_questions = "\n".join(
        f"{index}. {item.get('question', '').strip()}" for index, item in enumerate(corpus)
    )
    prompt = f"""Find the existing Q&A questions that are most semantically relevant to the user's question.

User question: {question}

Rank direct answers first, then genuinely related questions. Do not rank by shared words alone. Return at most {limit} corpus indices. If nothing is meaningfully related, return an empty list.

Corpus (zero-based index followed by question):
{numbered_questions}
"""
    request_body = {
        "model": SOL_MODEL,
        "reasoning": {"effort": "low"},
        "input": [
            {
                "role": "system",
                "content": "You are a careful semantic retrieval ranker. Return only corpus indices that refer to the supplied corpus.",
            },
            {"role": "user", "content": prompt},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "semantic_search_results",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "indices": {
                            "type": "array",
                            "items": {"type": "integer", "minimum": 0, "maximum": len(corpus) - 1},
                            "maxItems": limit,
                        }
                    },
                    "required": ["indices"],
                    "additionalProperties": False,
                },
            }
        },
        "max_output_tokens": 1000,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        try:
            import certifi
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ssl_context = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=90, context=ssl_context) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        try:
            detail = json.load(error).get("error", {}).get("message", str(error))
        except Exception:
            detail = str(error)
        raise RuntimeError(f"OpenAI API error: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach the OpenAI API: {error.reason}") from error

    output_text = ""
    for output in result.get("output", []):
        for content in output.get("content", []):
            if content.get("type") == "output_text":
                output_text += content.get("text", "")
    if not output_text:
        raise RuntimeError("Sol returned no search results.")
    parsed = json.loads(output_text)
    seen = set()
    matches = []
    for index in parsed.get("indices", []):
        if isinstance(index, int) and 0 <= index < len(corpus) and index not in seen:
            seen.add(index)
            matches.append({"index": index, "question": corpus[index].get("question", "")})
    return matches


def validate(payload: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["The document must be a JSON object."]
    queries = payload.get("queries")
    if not isinstance(queries, list):
        return ["queries must be an array."]

    seen_ids: set[str] = set()
    for index, item in enumerate(queries):
        label = f"Query {index + 1}"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object.")
            continue
        query_id = str(item.get("id", "")).strip()
        if not query_id:
            errors.append(f"{label} is missing an id.")
        elif query_id in seen_ids:
            errors.append(f"{label} has duplicate id '{query_id}'.")
        seen_ids.add(query_id)
        if not str(item.get("query", "")).strip():
            errors.append(f"{label} is missing question text.")
        outcome = item.get("expected_outcome")
        if outcome not in VALID_OUTCOMES:
            errors.append(f"{label} must have expected_outcome answered, related_only, or unanswered.")
        expected = item.get("expected_answers", [])
        related = item.get("expected_related", [])
        if not isinstance(expected, list):
            errors.append(f"{label} expected_answers must be an array.")
            continue
        if not isinstance(related, list):
            errors.append(f"{label} expected_related must be an array.")
            continue
        if outcome == "answered" and not expected:
            errors.append(f"{label} is answered but has no expected answers.")
        if outcome == "related_only" and (expected or not related):
            errors.append(f"{label} must have related questions and no direct answers.")
        if outcome == "unanswered" and (expected or related):
            errors.append(f"{label} is unanswered but still has expected matches.")
        for answer_index, answer in enumerate(expected):
            if not isinstance(answer, dict) or not str(answer.get("question", "")).strip():
                errors.append(f"{label}, expected answer {answer_index + 1}, needs question text.")
        for related_index, answer in enumerate(related):
            if not isinstance(answer, dict) or not str(answer.get("question", "")).strip():
                errors.append(f"{label}, related question {related_index + 1}, needs question text.")
    return errors


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(TOOL_DIR / "static"), **kwargs)

    def log_message(self, format, *args):  # noqa: A002
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_json(self, payload: object, status: int = 200):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/golden-set":
            self.send_json(read_json(GOLDEN_SET_PATH))
            return
        if path == "/api/corpus":
            corpus = read_json(CORPUS_PATH)
            self.send_json([
                {
                    "question": item.get("question", ""),
                    "url": item.get("url", ""),
                    "timestamp": item.get("timestamp", ""),
                }
                for item in corpus
            ])
            return
        if path == "/api/health":
            self.send_json({
                "ok": True,
                "goldenSet": str(GOLDEN_SET_PATH),
                "semanticSearch": {"configured": bool(os.getenv("OPENAI_API_KEY", "").strip()), "model": SOL_MODEL},
            })
            return
        super().do_GET()

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/api/semantic-search":
            self.send_json({"error": "Not found"}, 404)
            return
        try:
            payload = read_request_json(self)
            question = str(payload.get("question", "")).strip()
            if not question:
                raise ValueError("Enter a question to search for.")
            self.send_json({"matches": semantic_search(question), "model": SOL_MODEL})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)
        except RuntimeError as error:
            self.send_json({"error": str(error)}, 502)
        except Exception as error:
            self.send_json({"error": f"Semantic search failed: {error}"}, 500)

    def do_PUT(self):  # noqa: N802
        if urlparse(self.path).path != "/api/golden-set":
            self.send_json({"error": "Not found"}, 404)
            return
        try:
            payload = read_request_json(self, max_bytes=5_000_000)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)
            return

        errors = validate(payload)
        if errors:
            self.send_json({"error": "Validation failed", "details": errors}, 422)
            return

        payload["version"] = "2.0"
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = BACKUP_DIR / f"golden_set-{stamp}.json"
        shutil.copy2(GOLDEN_SET_PATH, backup_path)

        fd, temporary_name = tempfile.mkstemp(prefix="golden-set-", suffix=".json", dir=GOLDEN_SET_PATH.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(temporary_name, GOLDEN_SET_PATH)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

        self.send_json({"ok": True, "backup": str(backup_path), "updated_at": payload["updated_at"]})


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Golden Set Editor: http://127.0.0.1:{args.port}")
    print(f"Editing: {GOLDEN_SET_PATH}")
    print(f"Sol semantic search: {'configured' if os.getenv('OPENAI_API_KEY', '').strip() else 'disabled (set OPENAI_API_KEY)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
