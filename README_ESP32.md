# 🎵 YouTube ESP32 Music API v2.1

Server Python để stream nhạc từ YouTube cho ESP32, giải quyết vấn đề chunked encoding và Content-Length.

## 🚀 Quick Start

### 1. Cài đặt
```bash
cd j:\youtube_api_full
pip install flask flask-limiter yt-dlp requests
```

### 2. Chạy server
```bash
python app.py
```

**Output:**
```
============================================================
🎵 YouTube ESP32 Music API v2.1 - Enhanced Edition
============================================================
Features:
  ✅ Rate limiting protection
  ✅ Smart caching (30min)
  ✅ Multi-client YouTube extraction
  ✅ Error handling & logging
  ✨ NEW: Content-Length detection (HEAD request)
  ✨ NEW: Browser User-Agent anti-blocking
  ✨ NEW: Chunked encoding fix (proxy_youtube)
  ✨ NEW: HTTP Range support (resume download)
============================================================
📡 Listening on http://0.0.0.0:8000
🎯 ESP32 endpoint: /stream_pcm?song=<name>&artist=<name>
============================================================
```

### 3. Test
```bash
python test_api.py
```

## 📝 Thay đổi chính v2.1

### ✅ Đã sửa:
1. **Content-Length Detection** - Lấy file size bằng HEAD request ngay khi search
2. **Browser User-Agent** - Headers đầy đủ để bypass YouTube blocking
3. **Metadata Cache** - Cache content_length và user_agent
4. **Proxy Priority** - Ưu tiên Content-Length từ cache → không cần HEAD lại

### 🎯 Kết quả:
- ✅ ESP32 biết file bao lớn → Hiển thị progress bar chính xác
- ✅ ESP32 retry logic hoạt động → Download resume khi bị ngắt
- ✅ YouTube không block → User-Agent giống browser thật
- ✅ Download thành công 4MB+ → Phát full bài hát

## 📡 API Endpoints

### `/stream_pcm` - Search bài hát
```bash
GET /stream_pcm?song=<tên bài>&artist=<nghệ sĩ>

Response:
{
  "id": "abc-123",
  "title": "Tên bài hát",
  "artist": "Nghệ sĩ",
  "duration": 180,
  "audio_url": "/proxy_youtube?id=abc-123",  ← Proxy endpoint
  "lyric_url": "/proxy_lyric?id=abc-123"
}
```

### `/proxy_youtube` - Download audio qua proxy
```bash
GET /proxy_youtube?id=<uuid>
Header: Range: bytes=<start>-  (optional, for resume)

Response:
Status: 200 OK (hoặc 206 Partial Content)
Content-Type: audio/mpeg
Content-Length: 4123456  ← Luôn có!
Accept-Ranges: bytes

<audio stream data>
```

### `/proxy_lyric` - Lấy lyrics
```bash
GET /proxy_lyric?id=<uuid>

Response:
{"time": 0.5, "text": "Lời bài hát..."}
{"time": 5.2, "text": "Dòng tiếp theo..."}
...
```

## 🔍 Logs Example

### Server Search:
```
[SEARCH] test song
[yt_search] Success with format: bestaudio*
[yt_search] Getting Content-Length for audio URL...
[get_content_length] SUCCESS: 4123456 bytes (3.93 MB)
[yt_search] Found subtitle: vi
[yt_search] ✅ Complete: title='Test Song', size=3.93MB, duration=180s
```

### Server Proxy:
```
[PROXY] ESP32 resume download: bytes=1024000-
[PROXY] ✅ Using cached Content-Length: 4123456 bytes (3.93MB)
[PROXY] Completed: 3099456 bytes sent to ESP32
```

### ESP32 Download:
```
I (1234) Esp32Music: Starting download from: /proxy_youtube?id=xxx
I (1500) Esp32Music: Content-Length: 4123456 bytes
I (45000) Esp32Music: Download completed: 4123456/4123456 bytes
I (180000) Esp32Music: Playback finished (full song)
```

## 📚 Files Changed

### `youtube_fixed.py` - Content-Length detection
- ✅ Added `get_content_length()` function
- ✅ Enhanced browser headers (Sec-Ch-Ua, Referer, Origin)
- ✅ Retry logic with fallback strategies
- ✅ Return `content_length` and `user_agent` in result

### `app.py` - Proxy & metadata cache
- ✅ Added `AUDIO_META_CACHE` for storing metadata
- ✅ Enhanced `/proxy_youtube` with priority Content-Length
- ✅ Use cached User-Agent in proxy requests
- ✅ Full browser headers forwarding

### `test_api.py` - Test suite
- ✅ Test search API
- ✅ Test Content-Length header
- ✅ Test Range support (206 Partial Content)
- ✅ Test partial download

## ⚙️ Configuration

Port: `8000` (default)
Cache expire: `30 minutes`
Rate limit: `10 search/min`, `30 download/min`
Chunk size: `8KB` (proxy streaming)

## 🐛 Troubleshooting

### Vẫn không có Content-Length?
**Check:**
1. Server log có hiển thị `[get_content_length] SUCCESS` không?
2. YouTube có block IP server không? (thử VPN)
3. yt-dlp có update mới không? `pip install -U yt-dlp`

### YouTube block 403?
**Check:**
1. Server log có warning về User-Agent không?
2. Headers đầy đủ chưa? (Sec-Ch-Ua, Referer)
3. Thử clear cache và search lại

### ESP32 vẫn dừng sớm?
**Check:**
1. ESP32 có nhận đúng `/proxy_youtube` URL không?
2. ESP32 log có hiển thị Content-Length không?
3. Server proxy có running không?
4. Firewall có block connection không?

## 📖 Documentation

- **Full Changelog:** `CHANGELOG_ESP32.md`
- **ESP32 Code:** `f:\Puppy_V2.0.5\main\boards\common\esp32_music.cc`
- **yt-dlp:** https://github.com/yt-dlp/yt-dlp

## 🎉 Credits

- **yt-dlp** - YouTube extraction
- **Flask** - Web framework
- **requests** - HTTP client
- **ESP32 Music Player** - Hardware player

---

**Version:** 2.1  
**Date:** 2025-12-07  
**Status:** ✅ Production Ready
