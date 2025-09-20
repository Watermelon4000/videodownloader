yt-dlp Web UI (Local)

Quickly run a minimal local web interface for yt-dlp.

Prerequisites
- Python 3.9+
- ffmpeg available in PATH (needed for audio extraction, thumbnail embedding)

Setup
1) (Optional) Create a virtualenv
   python -m venv .venv && source .venv/bin/activate

2) Install Flask (and optionally install yt-dlp extras)
   pip install Flask
   # Optional but recommended if running outside the repo package path
   # pip install -e .

Run
   python webui/app.py

Then open: http://127.0.0.1:8080/

Environment variables
- YTDLP_WEBUI_DOWNLOAD_DIR: directory for downloads (default: ./webui_downloads)
- YTDLP_WEBUI_HOST: bind host (default: 127.0.0.1)
- YTDLP_WEBUI_PORT: bind port (default: 8080)

Notes
- “仅提取音频” 使用 FFmpegExtractAudio 将音频转为 MP3；需要 ffmpeg。
- 自定义格式可使用 yt-dlp 的 format 选择表达式，例如：bestvideo*+bestaudio/best。
- 下载的文件会显示在页面并可直接点击下载（本地服务）。

