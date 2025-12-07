FROM python:3.10-slim
RUN apt-get update && apt-get install -y ffmpeg curl nodejs npm && apt-get clean
RUN pip install --upgrade pip && pip install yt-dlp
WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["bash", "start.sh"]