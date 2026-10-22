#!/usr/bin/env python3
"""Fetch a YouTube transcript into transcripts/ as normalized markdown + segments."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "transcripts"

VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")
URL_PATTERNS = [
    r"[?&]v=([A-Za-z0-9_-]{11})",
    r"youtu\.be/([A-Za-z0-9_-]{11})",
    r"/shorts/([A-Za-z0-9_-]{11})",
    r"/embed/([A-Za-z0-9_-]{11})",
    r"/live/([A-Za-z0-9_-]{11})",
]
VTT_TS = re.compile(r"(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d{3})")


def extract_video_id(value: str) -> str | None:
    value = value.strip()
    if VIDEO_ID_RE.fullmatch(value):
        return value
    for pattern in URL_PATTERNS:
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    return None


def slugify(text: str, fallback: str = "unknown", max_len: int = 60) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:max_len].rstrip("-") or fallback


def fmt_ts(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def iso_date(upload_date: str) -> str:
    if re.fullmatch(r"\d{8}", upload_date or ""):
        return f"{upload_date[0:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    return ""


def find_exe(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    scripts = Path(sys.executable).parent
    for candidate in (scripts / f"{name}.exe", scripts / name):
        if candidate.exists():
            return str(candidate)
    return None


def fetch_metadata(url: str) -> dict:
    exe = find_exe("yt-dlp")
    if not exe:
        return {}
    try:
        proc = subprocess.run(
            [exe, "--dump-single-json", "--no-warnings", "--skip-download", url],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        if proc.returncode != 0:
            return {}
        info = json.loads(proc.stdout)
    except Exception as exc:
        print(f"metadata lookup failed: {exc}", file=sys.stderr)
        return {}

    return {
        "title": info.get("title") or "",
        "channel": info.get("channel") or info.get("uploader") or "",
        "published": iso_date(info.get("upload_date") or ""),
        "duration": info.get("duration"),
        "manual_langs": sorted((info.get("subtitles") or {}).keys()),
        "auto_langs": sorted((info.get("automatic_captions") or {}).keys()),
    }


def fetch_via_api(video_id: str, langs: list[str]) -> dict | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        print("youtube-transcript-api not installed; falling back to yt-dlp", file=sys.stderr)
        return None

    def pack(snippets, language, generated, method):
        segments = []
        for snippet in snippets:
            text = clean_text(snippet.text if hasattr(snippet, "text") else snippet.get("text", ""))
            start = float(snippet.start if hasattr(snippet, "start") else snippet.get("start", 0.0))
            duration = float(
                getattr(snippet, "duration", 0.0)
                if hasattr(snippet, "duration")
                else snippet.get("duration", 0.0)
            )
            if text:
                segments.append({"text": text, "start": start, "duration": duration})
        return {
            "segments": segments,
            "language": language,
            "is_generated": bool(generated),
            "method": method,
        }

    try:
        api = YouTubeTranscriptApi()
        try:
            fetched = api.fetch(video_id, languages=langs)
        except Exception as first_error:
            try:
                listing = api.list(video_id)
                chosen = next(iter(listing))
                fetched = chosen.fetch()
            except Exception:
                raise first_error
        return pack(
            list(fetched),
            getattr(fetched, "language_code", langs[0]),
            getattr(fetched, "is_generated", False),
            "youtube-transcript-api",
        )
    except AttributeError:
        try:
            raw = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
            return pack(raw, langs[0], False, "youtube-transcript-api")
        except Exception as exc:
            print(f"youtube-transcript-api failed: {exc}", file=sys.stderr)
            return None
    except Exception as exc:
        print(f"youtube-transcript-api failed: {exc}", file=sys.stderr)
        return None


def parse_vtt(text: str) -> list[dict]:
    def parse_ts(value: str) -> float:
        match = VTT_TS.search(value)
        if not match:
            return 0.0
        hours, minutes, seconds, millis = match.groups()
        return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000

    segments = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
        if not lines:
            continue
        index = 0
        if "-->" not in lines[0]:
            if len(lines) < 2:
                continue
            index = 1
        if "-->" not in lines[index]:
            continue
        start_raw, end_raw = lines[index].split("-->", 1)
        body_lines = list(dict.fromkeys(lines[index + 1 :]))
        body = clean_text(" ".join(body_lines))
        if not body:
            continue
        start = parse_ts(start_raw)
        end = parse_ts(end_raw)
        segments.append({"text": body, "start": start, "duration": max(0.0, end - start)})
    return segments


def fetch_via_ytdlp(url: str, langs: list[str], manual_langs: list[str]) -> dict | None:
    exe = find_exe("yt-dlp")
    if not exe:
        print("yt-dlp not installed", file=sys.stderr)
        return None

    lang_expr = ",".join([f"{lang}.*" for lang in langs] + list(langs))
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            exe,
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            lang_expr,
            "--sub-format",
            "vtt",
            "--no-warnings",
            "-o",
            str(Path(tmp) / "%(id)s.%(ext)s"),
            url,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        files = sorted(Path(tmp).glob("*.vtt"))
        if not files:
            stderr = (proc.stderr or "").strip()
            print(f"yt-dlp wrote no subtitles: {stderr[:300]}", file=sys.stderr)
            return None
        selected = next(
            (candidate for lang in langs for candidate in files if f".{lang}." in candidate.name),
            files[0],
        )
        segments = parse_vtt(selected.read_text(encoding="utf-8", errors="replace"))
        parts = selected.name.split(".")
        language = parts[-2] if len(parts) >= 3 else langs[0]
        generated = not any(
            language == manual or language.startswith(f"{manual}-") or manual.startswith(f"{language}-")
            for manual in manual_langs
        )
        return {
            "segments": segments,
            "language": language,
            "is_generated": generated,
            "method": "yt-dlp",
        }


def dedupe_segments(segments: list[dict]) -> list[dict]:
    result: list[dict] = []
    for segment in segments:
        text = segment["text"].strip()
        if not text:
            continue
        start = float(segment["start"])
        end = start + float(segment.get("duration", 0.0))
        if result:
            previous = result[-1]
            if text == previous["text"]:
                previous["end"] = max(previous["end"], end)
                continue
            if text.startswith(previous["text"]):
                remainder = text[len(previous["text"]) :].strip()
                previous["end"] = max(previous["end"], end)
                if not remainder:
                    continue
                text = remainder
            elif previous["text"].endswith(text):
                previous["end"] = max(previous["end"], end)
                continue
        result.append({"start": start, "end": end, "text": text})
    return result


def build_paragraphs(segments: list[dict], max_gap: float = 2.5, max_chars: int = 700) -> list[dict]:
    paragraphs: list[dict] = []
    current: dict | None = None
    for segment in segments:
        if current is None:
            current = {"start": segment["start"], "end": segment["end"], "text": segment["text"]}
            continue
        gap = segment["start"] - current["end"]
        if gap > max_gap or len(current["text"]) + len(segment["text"]) > max_chars:
            paragraphs.append(current)
            current = {"start": segment["start"], "end": segment["end"], "text": segment["text"]}
        else:
            current["text"] = f"{current['text']} {segment['text']}".strip()
            current["end"] = max(current["end"], segment["end"])
    if current:
        paragraphs.append(current)
    return paragraphs


def render_markdown(meta: dict, result: dict, segments: list[dict], paragraphs: list[dict]) -> str:
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    title = meta.get("title") or "(untitled)"
    duration = meta.get("duration")
    lines = [
        "---",
        f"video_id: {meta['video_id']}",
        f"url: {meta['url']}",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f'channel: "{(meta.get("channel") or "unknown").replace(chr(34), chr(39))}"',
        f"published: {meta.get('published') or 'unknown'}",
        f"fetched_at: {fetched_at}",
        f"language: {result['language']}",
        f"auto_generated: {'true' if result['is_generated'] else 'false'}",
        f"source: {result['method']}",
        f"duration: {fmt_ts(duration) if duration else 'unknown'}",
        "---",
        "",
        f"# {title}",
        "",
    ]
    if result["is_generated"]:
        lines += [
            "> Auto-generated captions: punctuation, names, tickers, and numbers are",
            "> unreliable. Verify every figure against the segment sidecar or the video.",
            "",
        ]
    for paragraph in paragraphs:
        lines.append(f"**[{fmt_ts(paragraph['start'])}]** {paragraph['text']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and normalize a YouTube transcript.")
    parser.add_argument("source", help="YouTube URL or 11-character video ID")
    parser.add_argument("--lang", action="append", dest="langs", help="Preferred language code; repeatable")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output root directory")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing transcript")
    args = parser.parse_args()

    video_id = extract_video_id(args.source)
    if not video_id:
        print("Could not parse a YouTube video id from the input.", file=sys.stderr)
        return 2

    url = f"https://www.youtube.com/watch?v={video_id}"
    langs = args.langs or ["en"]

    metadata = fetch_metadata(url)
    result = fetch_via_api(video_id, langs)
    if result is None:
        result = fetch_via_ytdlp(url, langs, metadata.get("manual_langs", []))

    if result is None or not result["segments"]:
        print("No usable captions found. The video may have captions disabled or be unavailable.", file=sys.stderr)
        return 3

    segments = dedupe_segments(result["segments"])
    paragraphs = build_paragraphs(segments)

    meta = {
        "video_id": video_id,
        "url": url,
        "title": metadata.get("title", ""),
        "channel": metadata.get("channel", ""),
        "published": metadata.get("published", ""),
        "duration": metadata.get("duration"),
    }

    channel_slug = slugify(meta["channel"], fallback="unknown")
    date_part = (meta["published"] or datetime.now(timezone.utc).date().isoformat()).replace("-", "")
    title_slug = slugify(meta["title"], fallback=video_id)
    out_dir = Path(args.out).expanduser().resolve() / channel_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"{date_part}-{title_slug}"
    md_path = base.with_suffix(".md")
    segments_path = base.with_suffix(".segments.json")

    if md_path.exists() and not args.force:
        print(f"Already exists: {md_path}\nRe-run with --force to overwrite.", file=sys.stderr)
        return 4

    markdown = render_markdown(meta, result, segments, paragraphs)
    md_path.write_text(markdown, encoding="utf-8")

    digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    sidecar = {
        "video_id": video_id,
        "url": url,
        "title": meta["title"],
        "channel": meta["channel"],
        "published": meta["published"],
        "language": result["language"],
        "is_generated": result["is_generated"],
        "method": result["method"],
        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "sha256": digest,
        "segments": segments,
    }
    segments_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"transcript: {md_path}")
    print(f"segments:   {segments_path}")
    print(f"language:   {result['language']} ({'auto' if result['is_generated'] else 'manual'})")
    print(f"segments:   {len(segments)}  sha256: {digest[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
