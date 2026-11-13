# Misinformation Detector

**A FastAPI prototype that pulls claims out of a news article, fact-checks
each one, and scores how credible the content looks.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![spaCy](https://img.shields.io/badge/spaCy-09A3D4?style=flat-square&logo=spacy&logoColor=white)](https://spacy.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

> This is the MIT-licensed mirror of
> [`vivek797029/Misinformation-Detector`](https://github.com/vivek797029/Misinformation-Detector),
> maintained under `Harshit-3114`. The upstream repository is unchanged.

---

## What it does

Give it a URL, a block of text, or an image. It:

1. **Extracts claims** from the text using spaCy dependency parsing.
2. **Fact-checks each claim** against Google's Fact Check Tools API — or, when
   no API key is set, against a small built-in claims database using semantic
   similarity.
3. **Inspects an uploaded image** for signs of manipulation or metadata
   stripping.
4. **Scores each claim** from 0 to 100 and renders the result as a card.

The whole thing is one FastAPI app with a server-rendered Jinja2 page. There
is no JavaScript framework and no database.

> **This is a prototype.** The built-in claims database has six entries. It is
> designed to show the full pipeline working end to end, and to be the
> starting point for a real fact-checking backend — not to be a production
> fact-checker on its own.

## The pipeline

```
URL ──▶ newspaper3k ──┐
                      ├──▶ spaCy claim extraction ──▶ fact-check ──▶ score ──▶ HTML
text ─────────────────┘                                    ▲
                                                           │
                                          Google Fact Check API
                                          (or semantic match
                                           over the demo DB)
image ──▶ Pillow / EXIF checks ──▶ image suspicion ────────┘
```

## Claim extraction

`models/claim_detector.py` runs `en_core_web_sm` over the text and keeps a
sentence when it is:

- at least six words long, **and**
- tagged with a nominal subject (`nsubj` or `nsubjpass`), **and**
- tagged with a verb (`pos_ == "VERB"`).

That filter is what separates a *claim* from a fragment of prose — a
sub-heading or a byline has no subject-verb pair and gets dropped. At most
six claims are returned.

If nothing matches the filter at all, the extractor falls back to the first
six non-empty lines, so the app still returns something rather than an empty
page.

## Fact-checking

`services/factcheck.py` tries two paths, in order:

**1. Google Fact Check Tools API.** If `GOOGLE_FC_API_KEY` is set, the claim
is sent to `claims:search` and the first matching review is used — its
`textualRating` and source URL are returned verbatim. The key is optional;
without it this path is skipped.

**2. Semantic match against the demo database.** The claim is embedded with
`sentence-transformers` (`all-MiniLM-L6-v2`) and compared, by cosine
similarity, against six seeded claims:

| Claim | Rating |
|---|---|
| Vaccines cause autism | False |
| 5G networks spread COVID-19 | False |
| Drinking water can cure diabetes | False |
| Eating carrots improves night vision | Partly True |
| The vaccine contains microchips | False |
| Climate change is primarily caused by human activity | True |

A match is only accepted at **0.55 similarity or above**. Below that the
claim comes back as `Unverified` with no source — a low-confidence nearest
neighbour is a worse answer than an honest "not in the database".

The demo database is a plain list in `services/factcheck.py`. Replacing it
with a real corpus is the single change that turns this prototype into
something useful.

## Image checks

`services/media_check.py` opens the upload with Pillow and accumulates a
suspicion score:

| Signal | Points | Why |
|---|---|---|
| No EXIF metadata | +30 | Metadata may have been stripped, which can indicate a re-save or a synthetic image — but it is also what most social-media uploads look like |
| File under 50 KB | +10 | Heavy compression or a generated thumbnail |
| Either dimension under 400 px | +10 | Too small for most legitimate news imagery |

| Score | Verdict |
|---|---|
| 40 and above | Possibly AI-generated / metadata stripped |
| 20 to 39 | Suspicious — review manually |
| Below 20 | Likely Authentic |

These are heuristics, and the app says so — the verdict is advisory, not a
determination.

## Scoring

`services/score.py` turns a fact-check rating into a number:

| Rating | Base score |
|---|---|
| True | 90 |
| False | 15 |
| Partly True / Misleading | 45 |
| Unverified / None | 55 |
| Anything else | 50 |

Two adjustments are applied on top:

- **Match confidence.** A strong semantic match nudges the score up by
  `int((match_score − 0.5) × 20)`.
- **Image suspicion.** The image's suspicion score is subtracted at half
  weight, so a suspect image drags the credibility of every claim down
  without dominating the result.

The final score is clamped to 0–100 and rendered green at 70+, yellow at
45+, red below.

## Running it

```bash
git clone https://github.com/Harshit-3114/Misinformation-Detector.git
cd Misinformation-Detector

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Start the server

```bash
uvicorn app:app --reload
```

Then open <http://localhost:8000>.

On macOS or Linux, `./run.sh` does the same thing but picks the first free
port between 8000 and 8010, killing anything already holding one.

### Configuration

Everything works with no configuration. To use the real fact-check API:

```bash
export GOOGLE_FC_API_KEY=your_key_here
```

Get a key from the [Google Fact Check Tools
documentation](https://developers.google.com/fact-check/tools/api). The first
model download (`all-MiniLM-L6-v2`) is cached locally after the first run.

## API

| Route | Method | Body | Returns |
|---|---|---|---|
| `/` | `GET` | — | The form |
| `/analyze` | `POST` | `url`, `text` and/or `file` (multipart form) | The form with claim cards and, if an image was uploaded, the image report |

`/analyze` accepts all three inputs at once: a URL supplies the article text,
explicit text overrides it, and an uploaded image is checked separately.

## Files

| Path | What it is |
|---|---|
| `app.py` | The FastAPI app — routes, input handling, orchestration |
| `models/claim_detector.py` | spaCy claim extraction |
| `services/factcheck.py` | Google Fact Check API + semantic fallback |
| `services/media_check.py` | Pillow / EXIF image heuristics |
| `services/score.py` | Rating → credibility score |
| `templates/index.html` | The single Jinja2 page |
| `static/style.css` | Styling |
| `run.sh` | Free-port launcher for 8000–8010 |

## Known limitations

- The built-in claims database has six entries. Anything outside them is
  `Unverified` unless you configure the Google API.
- The claim filter is a syntactic heuristic. It finds sentences shaped like
  claims; it does not understand whether a claim is false.
- Image checks cannot detect a well-made generative image. They look for
  traces of handling, not evidence of synthesis.
- There is no rate limiting, no auth and no persistence.

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Harshit Shyamsukha.
