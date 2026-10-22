---
name: fetch-transcript
description: >
  Download a YouTube transcript from a URL into this repository as a normalized,
  provenance-stamped markdown file plus a per-cue timestamp sidecar. Use when the
  user supplies a YouTube link or video ID and wants it available for framework
  extraction, or when an existing transcript needs re-fetching or repair. Handles
  manual captions, auto-generated captions, and missing-caption failures.
---

# Fetch a transcript

## What this produces

```
transcripts/<channel-slug>/<YYYYMMDD>-<title-slug>.md
transcripts/<channel-slug>/<YYYYMMDD>-<title-slug>.segments.json
```

The `.md` is for reading and extraction. The `.segments.json` is the citation
record: every evidence quote in a framework must be locatable in it by timestamp.

## Procedure

1. Run from the repository root:

   ```
   python scripts/fetch_transcript.py "<youtube-url-or-id>"
   ```

   Options: `--lang en` (repeatable), `--out transcripts`, `--force`.

2. Verify the output before using it:
   - frontmatter has `video_id`, `url`, `title`, `channel`, `fetched_at`,
     `language`, `auto_generated`, `source`
   - the body is non-empty and timestamps increase
   - `auto_generated: true` means punctuation and proper nouns are unreliable;
     the extraction step must treat numbers, tickers, and names as suspect

3. Report the path and whether captions were auto-generated.

## Rules

- **Fetch from your own machine.** YouTube blocks datacenter and CI IPs. Never
  call this from a deployed server or serverless function; fetch locally and
  commit the result.
- **Never edit a fetched transcript in place.** Raw input is immutable. If a
  fetch is wrong, re-fetch with `--force` or write a corrected copy with a new
  filename.
- **Missing captions are not an error to paper over.** If the script exits
  non-zero, report that the video has no usable captions and ask the user to
  supply audio or a different source. Do not synthesize a transcript.
- **Do not summarize while fetching.** Transcription and interpretation are
  separate stages on purpose.

## Fallback chain the script implements

1. `youtube-transcript-api` — preferred; returns segments, language, and
   `is_generated`.
2. `yt-dlp --write-auto-subs --write-subs --skip-download` — used when the
   library is blocked or absent; also supplies title/channel/upload date via
   `--dump-json`.
3. If both fail: stop and report. Speech-to-text (Whisper) is a deliberate,
   user-approved escalation, not an automatic fallback.
