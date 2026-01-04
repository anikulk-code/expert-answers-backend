import os
import re
import json
import datetime
import requests
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # set this env var
PLAYLIST_ID = "PLDqahtm2vA70VohJ__IobJSOGFJ2SdaRO"

# Matches "0:00 Title" or "12:34 Title" or "1:02:03 Title" at start of a line
CHAPTER_LINE_RE = re.compile(r"^(?P<ts>(?:\d+:)?\d{1,2}:\d{2})\s*[-–—]\s*(?P<title>.+)$|^(?P<ts2>(?:\d+:)?\d{1,2}:\d{2})\s+(?P<title2>.+)$")

def parse_timestamp_to_seconds(ts: str) -> int:
    parts = ts.split(":")
    parts = [int(p) for p in parts]
    if len(parts) == 2:
        m, s = parts
        return m * 60 + s
    if len(parts) == 3:
        h, m, s = parts
        return h * 3600 + m * 60 + s
    raise ValueError(f"Unrecognized timestamp format: {ts}")

def yt_get(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_all_playlist_video_ids(playlist_id: str) -> List[str]:
    video_ids = []
    page_token = None
    while True:
        params = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": YOUTUBE_API_KEY,
        }
        if page_token:
            params["pageToken"] = page_token

        data = yt_get("https://www.googleapis.com/youtube/v3/playlistItems", params)
        for item in data.get("items", []):
            vid = item["contentDetails"]["videoId"]
            video_ids.append(vid)

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return video_ids

def fetch_video_snippets(video_ids: List[str]) -> List[Dict[str, Any]]:
    # videos.list supports up to 50 ids per request
    out = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        params = {
            "part": "snippet",
            "id": ",".join(chunk),
            "maxResults": 50,
            "key": YOUTUBE_API_KEY,
        }
        data = yt_get("https://www.googleapis.com/youtube/v3/videos", params)
        out.extend(data.get("items", []))
    return out

def extract_chapters_from_description(description: str) -> List[Tuple[str, str, int]]:
    chapters = []
    for raw_line in description.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = CHAPTER_LINE_RE.match(line)
        if not m:
            continue

        ts = m.group("ts") or m.group("ts2")
        title = (m.group("title") or m.group("title2") or "").strip()
        if not ts or not title:
            continue

        try:
            seconds = parse_timestamp_to_seconds(ts)
        except ValueError:
            continue

        chapters.append((ts, title, seconds))

    # YouTube “chapters” usually start at 0:00; we won’t enforce it, just return what exists
    return chapters

def build_output(playlist_id: str) -> List[Dict[str, Any]]:
    video_ids = fetch_all_playlist_video_ids(playlist_id)
    videos = fetch_video_snippets(video_ids)

    results = []
    for v in videos:
        sn = v.get("snippet", {})
        video_id = v.get("id")
        title = sn.get("title", "")
        description = sn.get("description", "")
        published_at = sn.get("publishedAt", "")

        video_url = f"https://www.youtube.com/watch?v={video_id}"

        chapters = extract_chapters_from_description(description)
        for (ts, chapter_title, seconds) in chapters:
            chapter_url = f"{video_url}&t={seconds}s"
            results.append({
                "playlist_id": playlist_id,
                "video_id": video_id,
                "video_title": title,
                "publishedAt": published_at,
                "video_url": video_url,
                "chapter_title": chapter_title,
                "chapter_timestamp": ts,
                "chapter_seconds": seconds,
                "chapter_url": chapter_url,
                "description": description,
            })

    # Sort by published date then by chapter time
    def sort_key(x):
        # publishedAt is RFC3339; string sort usually works, but we’ll be safe
        try:
            dt = datetime.datetime.fromisoformat(x["publishedAt"].replace("Z", "+00:00"))
        except Exception:
            dt = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        return (dt, x["chapter_seconds"])

    results.sort(key=sort_key, reverse=True)
    return results

def main():
    if not YOUTUBE_API_KEY:
        raise RuntimeError("Set YOUTUBE_API_KEY env var first.")
    data = build_output(PLAYLIST_ID)
    with open("askswami_chapters.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(data)} chapter entries to askswami_chapters.json")

if __name__ == "__main__":
    main()
