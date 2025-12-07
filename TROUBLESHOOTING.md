# 🚨 Xử lý lỗi YouTube Blocking

## Lỗi: "Failed to parse JSON" / JSONDecodeError

### Nguyên nhân:
- YouTube phát hiện bot và chặn request
- Rate limiting (quá nhiều request trong thời gian ngắn)
- IP bị blacklist tạm thời

### Giải pháp:

#### 1. **Chờ 5-10 phút** (Đơn giản nhất)
YouTube thường unblock sau vài phút.

#### 2. **Restart Docker với IP mới**
```bash
docker stop youtube-api-container
docker rm youtube-api-container
# Restart Docker Desktop để đổi IP
docker run -d -p 8000:8000 --name youtube-api-container youtube-api
```

#### 3. **Dùng Proxy/VPN**
Chạy Docker với proxy:
```bash
docker run -d -p 8000:8000 \
  -e HTTP_PROXY=http://proxy-server:port \
  -e HTTPS_PROXY=http://proxy-server:port \
  --name youtube-api-container youtube-api
```

#### 4. **Tắt cookie support nếu không có Chrome**
Trong `services/youtube_fixed.py`, comment dòng:
```python
# "cookiesfrombrowser": ("chrome",),
```

#### 5. **Giảm tần suất request**
- Tăng `CACHE_EXPIRE` trong `app.py` lên 3600 (1 giờ)
- Giới hạn users test cùng lúc

### Monitor:
```bash
docker logs -f youtube-api-container | grep "JSONDecodeError"
```

Nếu thấy nhiều lỗi này → đang bị block → chờ hoặc đổi IP
