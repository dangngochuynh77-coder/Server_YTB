import yt_dlp

def yt_search(query):
    base = {
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch1",
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
                "skip": ["hls", "dash"]
            }
        }
    }
    
    formats = ["bestaudio*", "bestaudio", "ba", "worstaudio"]   
    info = None
    
    for f in formats:
        try:
            opt = base | {"format": f}
            with yt_dlp.YoutubeDL(opt) as y:
                r = y.extract_info(query, download=False)
            info = r["entries"][0] if "entries" in r else r
            
            if info and info.get("url"):
                print(f"[yt_search] Success with format: {f}")
                break
            else:
                info = None
        except Exception as e:
            print(f"[yt_search] Format {f} failed: {str(e)}")
            continue
    
    if not info: return None
    
    # --- LOGIC THUMBNAIL ---
    # yt-dlp thường trả về key 'thumbnail' (ảnh độ phân giải cao nhất).
    # Chúng ta đảm bảo key này tồn tại để app.py dùng.
    if "thumbnail" not in info and "thumbnails" in info:
        # Nếu không có key thumbnail trực tiếp, lấy cái cuối cùng trong list (thường là to nhất)
        try:
            info["thumbnail"] = info["thumbnails"][-1]["url"]
        except:
            info["thumbnail"] = None

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
