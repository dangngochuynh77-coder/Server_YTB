import yt_dlp

def yt_search(query):
    # Cấu hình tối ưu tốc độ tối đa
    base = {
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch1",
        "noplaylist": True,          # Bỏ qua playlist
        "force_ipv4": True,          # [QUAN TRỌNG] Ép dùng IPv4 để kết nối ngay lập tức
        "socket_timeout": 5,         # Timeout nhanh
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"], # Giả lập Android để link sống lâu
                "skip": ["hls", "dash"]
            }
        },
        # Lấy audio tốt nhất có thể trong 1 lần gọi
        "format": "bestaudio*/bestaudio/best" 
    }
    
    info = None
    
    try:
        # Khởi tạo và chạy 1 lần duy nhất
        with yt_dlp.YoutubeDL(base) as y:
            r = y.extract_info(query, download=False)
            
        if "entries" in r:
            info = r["entries"][0] # Kết quả search
        else:
            info = r # Kết quả direct link
            
        if not info or not info.get("url"):
            print(f"[yt_search] Failed: No URL found")
            return None
            
        print(f"[yt_search] Success: {info.get('title')} ({info.get('duration')}s)")

        # --- ĐÃ XÓA BỎ ĐOẠN TÌM SUBTITLE/LYRIC ---
        # Code sẽ trả về info ngay tại đây
        info["vtt_url"] = None 
        return info

    except Exception as e:
        print(f"[yt_search] Error: {str(e)}")
        return None
