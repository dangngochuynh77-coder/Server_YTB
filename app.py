from flask import Flask, request, jsonify, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import subprocess, time, uuid, re, requests, threading, hashlib

from services.youtube_fixed import yt_search

app = Flask(__name__)

# Rate limiting - bảo vệ API khỏi abuse
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

AUDIO_BITRATE="64K"
AUDIO_SAMPLERATE="44100"
AUDIO_CHANNELS="1"

# Cache cho search query (tránh search lại cùng bài hát)
SEARCH_CACHE = {}
AUDIO_CACHE={}
LYRIC_CACHE={}
LAST_ACCESS={}

CLEANUP_INTERVAL=600
CACHE_EXPIRE=1800  # Tăng lên 30 phút (1800s)

def parse_vtt(text):
    lines=text.split("\n")
    result=[]
    import re
    pattern=re.compile(r"(\d+):(\d+)\.(\d+)\s+-->")
    cur=None
    for line in lines:
        m=pattern.search(line)
        if m:
            cur=int(m.group(1))*60+int(m.group(2))+int(m.group(3))/1000.0
            continue
        if cur and line.strip():
            result.append({"time":cur,"text":line.strip()})
            cur=None
    return result

@app.route("/stream_pcm")
@limiter.limit("10 per minute")  # Giới hạn 10 request/phút/IP
def stream_pcm():
    song = request.args.get("song", "")
    if not song: 
        return jsonify({"error": "missing song"}), 400
    
    # Tạo cache key từ song query
    cache_key = hashlib.md5(song.lower().encode()).hexdigest()
    
    # Kiểm tra search cache trước
    if cache_key in SEARCH_CACHE:
        cached_data = SEARCH_CACHE[cache_key]
        # Kiểm tra cache còn hiệu lực không
        if time.time() - cached_data["timestamp"] < CACHE_EXPIRE:
            print(f"[CACHE HIT] {song}")
            entry = cached_data["entry"]
            uid = str(uuid.uuid4())
            AUDIO_CACHE[uid] = entry["url"]
            LAST_ACCESS[uid] = time.time()
            LYRIC_CACHE[uid] = cached_data["lyrics"]
            
            return jsonify({
                "id": uid,
                "title": entry.get("title", ""),
                "artist": entry.get("artist") or entry.get("channel", ""),
                "duration": entry.get("duration", 0),
                "audio_url": f"/proxy_audio?id={uid}",
                "lyric_url": f"/proxy_lyric?id={uid}" if cached_data["lyrics"] else ""
            })
    
    # Cache miss - search YouTube
    print(f"[SEARCH] {song}")
    try:
        entry = yt_search(song)
        if not entry: 
            return jsonify({"error": "yt_fail", "message": "Cannot find song on YouTube"}), 404
    except Exception as e:
        print(f"[ERROR] YouTube search failed: {str(e)}")
        return jsonify({"error": "yt_error", "message": str(e)}), 500
    
    uid = str(uuid.uuid4())
    AUDIO_CACHE[uid] = entry["url"]
    LAST_ACCESS[uid] = time.time()
    
    # Parse lyrics
    vtt_url = entry.get("vtt_url")
    lyr = []
    if vtt_url:
        try: 
            lyr = parse_vtt(requests.get(vtt_url, timeout=10).text)
        except Exception as e:
            print(f"[WARN] Lyric fetch failed: {str(e)}")
            lyr = []
    
    LYRIC_CACHE[uid] = lyr
    
    # Lưu vào search cache
    SEARCH_CACHE[cache_key] = {
        "entry": entry,
        "lyrics": lyr,
        "timestamp": time.time()
    }
    
    return jsonify({
        "id": uid,
        "title": entry.get("title", ""),
        "artist": entry.get("artist") or entry.get("channel", ""),
        "duration": entry.get("duration", 0),
        "audio_url": f"/proxy_audio?id={uid}",
        "lyric_url": f"/proxy_lyric?id={uid}" if lyr else ""
    })

@app.route("/proxy_audio")
@limiter.limit("30 per minute")  # Giới hạn bandwidth abuse
def proxy_audio():
    uid = request.args.get("id")
    if uid not in AUDIO_CACHE: 
        return jsonify({"error": "id not found"}), 404
    
    src = AUDIO_CACHE[uid]
    LAST_ACCESS[uid] = time.time()
    
    # Lấy Range header từ ESP32 (nếu có)
    range_header = request.headers.get('Range')
    
    # ✅ GIẢI PHÁP: Convert sang MP3 bằng FFmpeg VÀ buffer toàn bộ để có Content-Length
    try:
        print(f"[PROXY_AUDIO] Converting to MP3: {uid}")
        
        # FFmpeg command: YouTube URL → MP3 (mono, 44.1kHz, 64kbps)
        cmd = [
            "ffmpeg", 
            "-i", src,              # Input: YouTube URL
            "-vn",                  # Không video
            "-acodec", "libmp3lame", # MP3 codec
            "-b:a", AUDIO_BITRATE,  # 64kbps
            "-ac", AUDIO_CHANNELS,  # Mono (1 channel)
            "-ar", AUDIO_SAMPLERATE, # 44.1kHz
            "-f", "mp3",            # Format MP3
            "pipe:1"                # Output to stdout
        ]
        
        # Chạy FFmpeg và buffer toàn bộ output
        print(f"[FFMPEG] Starting conversion...")
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        # Đọc toàn bộ MP3 data vào RAM
        mp3_data, stderr = process.communicate(timeout=60)  # Timeout 60s
        
        if process.returncode != 0:
            print(f"[ERROR] FFmpeg failed: {stderr.decode()}")
            return jsonify({"error": "ffmpeg_error"}), 500
        
        total_size = len(mp3_data)
        print(f"[FFMPEG] Conversion complete: {total_size} bytes")
        
        # Xử lý Range request (nếu ESP32 yêu cầu resume)
        if range_header:
            # Parse Range header: "bytes=start-end"
            import re
            match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else total_size - 1
                
                print(f"[RANGE] Serving bytes {start}-{end}/{total_size}")
                
                # Trả về partial content
                return Response(
                    mp3_data[start:end+1],
                    status=206,
                    headers={
                        'Content-Type': 'audio/mpeg',
                        'Content-Length': str(end - start + 1),
                        'Content-Range': f'bytes {start}-{end}/{total_size}',
                        'Accept-Ranges': 'bytes'
                    }
                )
        
        # Trả về toàn bộ file (200 OK)
        return Response(
            mp3_data,
            status=200,
            headers={
                'Content-Type': 'audio/mpeg',
                'Content-Length': str(total_size),
                'Accept-Ranges': 'bytes'
            }
        )
        
    except subprocess.TimeoutExpired:
        process.kill()
        print(f"[ERROR] FFmpeg timeout after 60s")
        return jsonify({"error": "timeout"}), 504
    except Exception as e:
        print(f"[ERROR] Proxy failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "proxy_error", "message": str(e)}), 500

@app.route("/proxy_lyric")
@limiter.limit("30 per minute")
def proxy_lyric():
    uid = request.args.get("id")
    if uid not in LYRIC_CACHE: 
        return jsonify({"error": "no lyric"}), 404
    
    LAST_ACCESS[uid] = time.time()
    
    def g():
        for l in LYRIC_CACHE[uid]:
            yield f"{l}\n"
    
    return Response(g(), mimetype="text/plain")

@app.route("/")
def home(): 
    return jsonify({
        "status": "ok",
        "version": "2.0",
        "endpoints": {
            "/stream_pcm": "Search and get song info",
            "/proxy_audio": "Stream audio",
            "/proxy_lyric": "Get lyrics"
        }
    })

def auto():
    """Background thread để clean cache định kỳ"""
    while True:
        now = time.time()
        
        # Clean audio/lyric cache
        rm = [k for k, t in LAST_ACCESS.items() if now - t > CACHE_EXPIRE]
        for k in rm:
            AUDIO_CACHE.pop(k, None)
            LYRIC_CACHE.pop(k, None)
            LAST_ACCESS.pop(k, None)
            print(f"[CLEAN] Removed cache: {k}")
        
        # Clean search cache
        search_rm = [k for k, v in SEARCH_CACHE.items() 
                     if now - v["timestamp"] > CACHE_EXPIRE]
        for k in search_rm:
            SEARCH_CACHE.pop(k, None)
            print(f"[CLEAN] Removed search cache")
        
        time.sleep(CLEANUP_INTERVAL)

threading.Thread(target=auto, daemon=True).start()

if __name__ == "__main__": 
    print("=" * 50)
    print("YouTube MP3 API v2.0 - Enhanced Edition")
    print("=" * 50)
    print("Features:")
    print("  ✓ Rate limiting protection")
    print("  ✓ Smart caching (30min)")
    print("  ✓ Multi-client YouTube extraction")
    print("  ✓ Error handling & logging")
    print("=" * 50)
    app.run(host="0.0.0.0", port=8000)
