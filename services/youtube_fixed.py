import yt_dlp
import time
import random

def yt_search(query):
    # Cải thiện config để tránh bị YouTube phát hiện
    base = {
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch1",
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],  # Dùng nhiều client để bypass
                "skip": ["hls", "dash"]
            }
        },
        # Giả lập browser thật
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-us,en;q=0.5",
            "Sec-Fetch-Mode": "navigate"
        },
        # Rate limiting để tránh spam
        "sleep_interval": 1,
        "max_sleep_interval": 3,
        "socket_timeout": 30
    }
    
    formats = ["bestaudio", "ba", "bestaudio*", "mp4"]
    info = None
    
    for f in formats:
        try:
            opt = base | {"format": f}
            with yt_dlp.YoutubeDL(opt) as y:
                r = y.extract_info(query, download=False)
            info = r["entries"][0] if "entries" in r else r
            break
        except Exception as e:
            print(f"[yt_search] Format {f} failed: {str(e)}")
            # Random sleep để tránh spam
            time.sleep(random.uniform(0.5, 1.5))
            continue
    
    if not info: return None
    
    # Tìm subtitle/caption
    caps = {}
    caps.update(info.get("automatic_captions", {}))
    caps.update(info.get("subtitles", {}))
    
    for lang in ["vi", "vi-VN", "en", "a.en", "auto"]:
        if lang in caps:
            for c in caps[lang]:
                if c.get("ext") == "vtt":
                    info["vtt_url"] = c["url"]
                    return info
    
    info["vtt_url"] = None
    return info
