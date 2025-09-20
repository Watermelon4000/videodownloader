import os
import sys
import subprocess
import uuid
import threading
from datetime import datetime
from typing import Dict, Any, List

from flask import Flask, request, jsonify, render_template, send_from_directory, abort

# Use the repo's yt_dlp package directly
from yt_dlp import YoutubeDL


app = Flask(__name__, template_folder="templates", static_folder="static")

DOWNLOAD_DIR = os.environ.get("YTDLP_WEBUI_DOWNLOAD_DIR", os.path.join(os.getcwd(), "webui_downloads"))
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class _HookLogger:
    def __init__(self, task: Dict[str, Any]):
        self._task = task

    def debug(self, msg):
        self._append("DEBUG", msg)

    def info(self, msg):
        self._append("INFO", msg)

    def warning(self, msg):
        self._append("WARN", msg)

    def error(self, msg):
        self._append("ERROR", msg)

    def _append(self, level: str, msg: str):
        if not isinstance(msg, str):
            msg = str(msg)
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "msg": msg,
        }
        self._task["log"].append(entry)


_tasks: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def _progress_hook(task_id: str):
    def hook(d: Dict[str, Any]):
        with _lock:
            task = _tasks.get(task_id)
            if not task:
                return
            if d.get("status") == "downloading":
                p = {
                    "status": d.get("status"),
                    "downloaded_bytes": d.get("downloaded_bytes"),
                    "total_bytes": d.get("total_bytes") or d.get("total_bytes_estimate"),
                    "speed": d.get("speed"),
                    "eta": d.get("eta"),
                    "fragment_index": d.get("fragment_index"),
                    "filename": d.get("filename"),
                }
                task["progress"].append(p)
                task["last_progress"] = p
            elif d.get("status") == "finished":
                fn = d.get("filename")
                # Do not blindly expose download stage artifacts (e.g. f140.m4a, f401.mp4).
                # These may be deleted by post-processors (merge/extract). We only
                # record last progress here; final files are added via postprocessor hook.
                task["last_progress"] = {"status": "finished", "filename": fn}
    return hook


def _postprocessor_hook(task_id: str):
    def hook(d: Dict[str, Any]):
        # Called with {status, postprocessor, info_dict}
        if d.get('status') != 'finished':
            return
        info = (d.get('info_dict') or {})
        # yt-dlp guarantees info['filepath'] to point to current working file
        # for postprocessors; after a PP finishes, this generally equals the
        # produced file.
        fp = info.get('filepath') or info.get('filename')
        if not fp:
            return
        try:
            abspath = os.path.abspath(fp)
            # Only list files that currently exist inside DOWNLOAD_DIR
            if os.path.exists(abspath) and abspath.startswith(os.path.abspath(DOWNLOAD_DIR) + os.sep):
                with _lock:
                    task = _tasks.get(task_id)
                    if not task:
                        return
                    bn = os.path.basename(abspath)
                    if bn not in task['files']:
                        task['files'].append(bn)
        except Exception:
            # Never let hook errors crash the app; errors are visible in logs
            pass
    return hook

def _run_download(task_id: str, urls: List[str], audio_only: bool, fmt: str, extra: Dict[str, Any]):
    ydl_opts: Dict[str, Any] = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title).200B-%(id)s.%(ext)s"),
        "progress_hooks": [_progress_hook(task_id)],
        "postprocessor_hooks": [_postprocessor_hook(task_id)],
        "logger": _HookLogger(_tasks[task_id]),
        # Keep stdout quiet; logs go via logger
        "quiet": True,
        "no_warnings": True,
        # Write thumbnails if asked via fmt like "bestaudio/ba" is fine
    }

    if audio_only:
        # Extract audio; bestaudio and convert to mp3/m4a depending on container
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",
            }],
        })
    elif fmt:
        ydl_opts["format"] = fmt
    else:
        # Optional convenience: force MP4-only selection if requested
        if extra.get("mp4_only"):
            # Try dash video+audio in MP4/M4A, otherwise single MP4. Will fail if MP4 not available.
            ydl_opts["format"] = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]"

    # Allow a couple of safe, simple extras
    if extra.get("subtitles"):
        ydl_opts.update({"writesubtitles": True, "subtitleslangs": ["all"]})
    if extra.get("embed_thumbnail"):
        ydl_opts.setdefault("postprocessors", []).append({"key": "EmbedThumbnail"})

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download(urls)
        with _lock:
            _tasks[task_id]["status"] = "completed"
    except Exception as err:  # noqa: BLE001 - keep broad to surface to UI
        with _lock:
            t = _tasks.get(task_id)
            if t:
                t["status"] = "error"
                t["error"] = str(err)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(force=True, silent=True) or {}
    url_text = (data.get("url") or "").strip()
    if not url_text:
        return jsonify({"error": "Missing url"}), 400
    urls = [u.strip() for u in url_text.splitlines() if u.strip()]
    audio_only = bool(data.get("audio_only"))
    fmt = (data.get("format") or "").strip()
    extra = {
        "subtitles": bool(data.get("subtitles")),
        "embed_thumbnail": bool(data.get("embed_thumbnail")),
    }

    task_id = uuid.uuid4().hex
    with _lock:
        _tasks[task_id] = {
            "id": task_id,
            "status": "running",
            "urls": urls,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "progress": [],
            "last_progress": None,
            "files": [],
            "log": [],
            "error": None,
        }

    th = threading.Thread(target=_run_download, args=(task_id, urls, audio_only, fmt, extra), daemon=True)
    th.start()
    return jsonify({"task_id": task_id})


@app.route("/api/status/<task_id>")
def api_status(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            return jsonify({"error": "unknown task"}), 404
        # Do not return full logs forever; truncate to last 200
        log_tail = task["log"][-200:]
        resp = {k: v for k, v in task.items() if k != "log"}
        # Filter out files that no longer exist (e.g., temporary streams deleted after merge)
        existing_files = []
        for fn in task.get('files', []):
            fp = os.path.join(DOWNLOAD_DIR, fn)
            if os.path.exists(fp):
                existing_files.append(fn)
        resp['files'] = existing_files
        resp["log"] = log_tail
        return jsonify(resp)


@app.route("/files/<path:filename>")
def files(filename: str):
    # Only serve files inside DOWNLOAD_DIR
    safe_path = os.path.abspath(os.path.join(DOWNLOAD_DIR, filename))
    if not safe_path.startswith(os.path.abspath(DOWNLOAD_DIR) + os.sep):
        abort(403)
    if not os.path.exists(safe_path):
        abort(404)
    return send_from_directory(DOWNLOAD_DIR, os.path.relpath(safe_path, DOWNLOAD_DIR), as_attachment=True)


def main():
    host = os.environ.get("YTDLP_WEBUI_HOST", "127.0.0.1")
    port = int(os.environ.get("YTDLP_WEBUI_PORT", "8080"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()

@app.post("/api/open_downloads")
def api_open_downloads():
    try:
        _open_in_file_manager(DOWNLOAD_DIR, reveal=False)
        return jsonify({"ok": True})
    except Exception as err:
        return jsonify({"ok": False, "error": str(err)}), 500


@app.post("/api/reveal/<path:filename>")
def api_reveal(filename: str):
    # Only allow revealing files within DOWNLOAD_DIR
    safe_path = os.path.abspath(os.path.join(DOWNLOAD_DIR, filename))
    if not safe_path.startswith(os.path.abspath(DOWNLOAD_DIR) + os.sep):
        abort(403)
    try:
        _open_in_file_manager(safe_path, reveal=True)
        return jsonify({"ok": True})
    except Exception as err:
        return jsonify({"ok": False, "error": str(err)}), 500


def _open_in_file_manager(path: str, reveal: bool = False) -> None:
    # Open a directory or reveal a file in the platform's file manager.
    if sys.platform == 'darwin':  # macOS
        if reveal:
            subprocess.run(['open', '-R', path], check=False)
        else:
            subprocess.run(['open', path], check=False)
    elif os.name == 'nt':  # Windows
        if reveal:
            subprocess.run(['explorer', '/select,', path], check=False)
        else:
            subprocess.run(['explorer', path], check=False)
    else:  # Linux/others
        # xdg-open works for both files and dirs; no standard 'reveal'
        target = path if not reveal else os.path.dirname(path) or '.'
        subprocess.run(['xdg-open', target], check=False)


@app.get('/api/list_downloads')
def api_list_downloads():
    # List files directly under DOWNLOAD_DIR; sorted by mtime desc
    max_items = int(request.args.get('limit', '200'))
    items = []
    try:
        for name in os.listdir(DOWNLOAD_DIR):
            p = os.path.join(DOWNLOAD_DIR, name)
            # Skip hidden files (e.g., .DS_Store) and non-regular files
            if name.startswith('.') or not os.path.isfile(p):
                continue
            st = os.stat(p)
            items.append({
                'name': name,
                'size': st.st_size,
                'mtime': datetime.utcfromtimestamp(st.st_mtime).isoformat() + 'Z',
            })
        items.sort(key=lambda x: x['mtime'], reverse=True)
        return jsonify({'files': items[:max_items]})
    except FileNotFoundError:
        return jsonify({'files': []})
