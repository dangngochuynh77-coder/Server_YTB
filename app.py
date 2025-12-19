from flask import Flask, request, jsonify, Response, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import subprocess, time, uuid, re, requests, threading, hashlib
from io import BytesIO
from PIL import Image # Cần pip install Pillow

from services.youtube_fixed import yt_search

app = Flask(__name__)

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["500 per day", "100 per hour"], # Tăng nhẹ limit vì load ảnh tốn request
    storage_uri="memory://"
)

AUDIO_BITRATE="64K"
AUDIO_SAMPLERATE="44100"
AUDIO_CHANNELS="1"
IMG_SIZE = (240, 240) # Kích thước ảnh vuông trả về cho ESP32

# Cache
SEARCH_CACHE = {}
AUDIO_CACHE = {}
LYRIC_CACHE = {}
IMAGE_CACHE = {} # Cache lưu URL ảnh gốc
LAST_ACCESS = {}

CLEANUP_INTERVAL=600
CACHE_EXPIRE=1800

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

# Hàm xử lý ảnh: Tải -> Crop vuông -> Resize -> JPEG
def process_image(url):
    try:
        # 1. Tải ảnh gốc
        resp = requests.get(url, timeout=5)
        img = Image.open(BytesIO(resp.content))
        
        # 2. Convert sang RGB (đề phòng ảnh PNG/WEBP có nền trong suốt)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # 3. Crop vuông (Center crop)
        width, height = img.size
        new_size = min(width, height)
        
        left = (width - new_size) / 2
        top = (height - new_size) / 2
        right = (width + new_size) / 2
        bottom = (height + new_size) / 2
        
        img = img.crop((left, top, right, bottom))
        
        # 4. Resize nhỏ lại cho nhẹ
        img = img.resize(IMG_SIZE, Image.LANCZOS)
        
        # 5. Xuất ra Bytes
        img_io = BytesIO()
        img.save(img_io, 'JPEG', quality=80) # Nén JPEG quality 80
        img_io.seek(0)
        return img_io
    except Exception as e:
        print(f"[IMG_ERR] {str(e)}")
        return None

@app.route("/stream_pcm")
@limiter.limit("20 per minute")
def stream_pcm():
    song = request.args.get("song", "")
    if not song: 
        return jsonify({"error": "missing song"}), 400
    
    cache_key = hashlib.md5(song.lower().encode()).hexdigest()
    
    # --- Xử lý dữ liệu trả về ---
    def make_response_data(uid, entry, cached_lyrics=None):
        return {
            "id": uid,
            "title": entry.get("title", ""),
            "artist": entry.get("artist") or entry.get("channel", ""),
            "duration": entry.get("duration", 0),
            "audio_url": f"/proxy_audio?id={uid}",
            "lyric_url": f"/proxy_lyric?id={uid}" if cached_lyrics else "",
            "image_url": f"/proxy_image?id={uid}" # Thêm link ảnh
        }

    # CACHE HIT
    if cache_key in SEARCH_CACHE:
        cached_data = SEARCH_CACHE[cache_key]
        if time.time() - cached_data["timestamp"] < CACHE_EXPIRE:
            print(f"[CACHE HIT] {song}")
            entry = cached_data["entry"]
            uid = str(uuid.uuid4())
            
            # Cập nhật các loại cache
            AUDIO_CACHE[uid] = entry.get("url")
            IMAGE_CACHE[uid] = entry.get("thumbnail") # Lưu URL thumbnail gốc
            LYRIC_CACHE[uid] = cached_data["lyrics"]
            LAST_ACCESS[uid] = time.time()
            
            return jsonify(make_response_data(uid, entry, cached_data["lyrics"]))
    
    # SEARCH YOUTUBE
    print(f"[SEARCH] {song}")
    try:
        entry = yt_search(song)
        if not entry: 
            return jsonify({"error": "yt_fail", "message": "Cannot find song"}), 404
    except Exception as e:
        return jsonify({"error": "yt_error", "message": str(e)}), 500
    
    uid = str(uuid.uuid4())
    AUDIO_CACHE[uid] = entry.get("url")
    IMAGE_CACHE[uid] = entry.get("thumbnail") # Lưu URL thumbnail gốc
    LAST_ACCESS[uid] = time.time()
    
    # Parse lyrics
    vtt_url = entry.get("vtt_url")
    lyr = []
    if vtt_url:
        try: 
            lyr = parse_vtt(requests.get(vtt_url, timeout=10).text)
        except Exception as e:
            print(f"[WARN] Lyric fetch failed: {str(e)}")
    
    LYRIC_CACHE[uid] = lyr
    
    SEARCH_CACHE[cache_key] = {
        "entry": entry,
        "lyrics": lyr,
        "timestamp": time.time()
    }
    
    return jsonify(make_response_data(uid, entry, lyr))

@app.route("/proxy_audio")
@limiter.limit("30 per minute")
def proxy_audio():
    uid = request.args.get("id")
    if uid not in AUDIO_CACHE: return jsonify({"error": "id not found"}), 404
    
    src = AUDIO_CACHE[uid]
    LAST_ACCESS[uid] = time.time()
    
    try:
        cmd = [
            "ffmpeg", "-i", src, "-vn",
            "-acodec", "libmp3lame", "-b:a", AUDIO_BITRATE,
            "-ac", AUDIO_CHANNELS, "-ar", AUDIO_SAMPLERATE,
            "-f", "mp3", "pipe:1"
        ]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        def generate():
            try:
                while True:
                    chunk = process.stdout.read(8192)
                    if not chunk: break
                    yield chunk
            finally:
                process.stdout.close()
                process.wait()
        
        return Response(generate(), mimetype='audio/mpeg')
    except Exception as e:
        return jsonify({"error": "streaming_error"}), 500

@app.route("/proxy_lyric")
def proxy_lyric():
    uid = request.args.get("id")
    if uid not in LYRIC_CACHE: return jsonify({"error": "no lyric"}), 404
    LAST_ACCESS[uid] = time.time()
    def g():
        for l in LYRIC_CACHE[uid]: yield f"{l}\n"
    return Response(g(), mimetype="text/plain")

# --- API MỚI: XỬ LÝ ẢNH ---
@app.route("/proxy_image")
@limiter.limit("60 per minute") # Load ảnh nhanh hơn audio
def proxy_image():
    uid = request.args.get("id")
    if uid not in IMAGE_CACHE: 
        return jsonify({"error": "no image"}), 404
    
    # Không cần update LAST_ACCESS liên tục cho ảnh để tránh lock, 
    # nhưng update để giữ session sống
    LAST_ACCESS[uid] = time.time() 
    
    original_url = IMAGE_CACHE[uid]
    if not original_url:
        return jsonify({"error": "empty url"}), 404

    # Xử lý ảnh
    img_data = process_image(original_url)
    if img_data:
        return send_file(img_data, mimetype='image/jpeg')
    else:
        return jsonify({"error": "image processing failed"}), 500

@app.route("/")
def home(): 
    return jsonify({"status": "ok", "version": "2.1"})

def auto():
    while True:
        now = time.time()
        rm = [k for k, t in LAST_ACCESS.items() if now - t > CACHE_EXPIRE]
        for k in rm:
            AUDIO_CACHE.pop(k, None)
            LYRIC_CACHE.pop(k, None)
            IMAGE_CACHE.pop(k, None) # Xóa cache ảnh
            LAST_ACCESS.pop(k, None)
            print(f"[CLEAN] Removed session: {k}")
        
        search_rm = [k for k, v in SEARCH_CACHE.items() if now - v["timestamp"] > CACHE_EXPIRE]
        for k in search_rm: SEARCH_CACHE.pop(k, None)
        
        time.sleep(CLEANUP_INTERVAL)

threading.Thread(target=auto, daemon=True).start()

if __name__ == "__main__": 
    app.run(host="0.0.0.0", port=8000)
