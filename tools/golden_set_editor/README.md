# Temporary Golden Set Editor

A standalone, zero-dependency browser editor for `eval/golden_set.json`. It is deliberately isolated from the FastAPI and React applications.

## Run

From `expert-answers-backend`:

```bash
python3 tools/golden_set_editor/server.py
```

Then open <http://127.0.0.1:8765>.

The editor:

- classifies each test as `answered`, `related_only`, or `unanswered`;
- stores direct matches in `expected_answers` and non-required matches in `expected_related`;
- searches the local `askswami_questions.json` corpus when adding expected matches;
- validates the document before saving;
- writes `eval/golden_set.json` atomically; and
- creates timestamped copies in `eval/backups/` before every save.

## GPT-5.6 Sol semantic search

Set an OpenAI API key before starting the editor:

```bash
export OPENAI_API_KEY="your-key-here"
python3 tools/golden_set_editor/server.py
```

The **Search with Sol** button calls `gpt-5.6-sol` through the local Python server. The key is never sent to browser JavaScript or written to the golden set.

The evaluation runner scores `expected_outcome`, direct `expected_answers`, and
`expected_related`, while remaining compatible with older golden-set entries.
