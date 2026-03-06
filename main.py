import os
import uuid
import glob
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "/tmp/ytdl"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class AnalyzeRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format: str = "mp4"

FORMAT_MAP = {
    "mp3": {
        "format": "bestaudio/best",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    },
    "720p": {
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "merge_output_format": "mp4",
    },
    "1080p": {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "merge_output_format": "mp4",
    },
    "mp4": {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
    },
}

def cleanup_old_files():
    """Remove files older than 10 minutes"""
    import time
    now = time.time()
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
        if now - os.path.getmtime(f) > 600:
            try:
                os.remove(f)
            except:
                pass

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(req.url, download=False)
    return {
        "title": info.get("title", "Unknown"),
        "thumbnail": info.get("thumbnail", ""),
        "duration": info.get("duration", 0),
        "channel": info.get("channel", info.get("uploader", "Unknown")),
        "url": req.url,
    }

@app.post("/api/download")
def download(req: DownloadRequest):
    cleanup_old_files()

    fmt_config = FORMAT_MAP.get(req.format, FORMAT_MAP["mp4"])
    file_id = str(uuid.uuid4())[:8]
    ext = "mp3" if req.format == "mp3" else "mp4"
    out_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    ydl_opts = {
        "format": fmt_config["format"],
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
    }

    if "merge_output_format" in fmt_config:
        ydl_opts["merge_output_format"] = fmt_config["merge_output_format"]

    if "postprocessors" in fmt_config:
        ydl_opts["postprocessors"] = fmt_config["postprocessors"]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(req.url, download=True)
        title = info.get("title", "download")

    # Find the output file (yt-dlp may change extension after postprocessing)
    candidates = glob.glob(os.path.join(DOWNLOAD_DIR, f"{file_id}.*"))
    if not candidates:
        raise HTTPException(status_code=500, detail="Download failed: no output file found")

    output_file = candidates[0]
    actual_ext = os.path.splitext(output_file)[1]
    filename = f"{title}{actual_ext}"

    return {
        "downloadUrl": f"/api/file/{os.path.basename(output_file)}",
        "filename": filename,
    }

@app.get("/api/file/{file_name}")
def serve_file(file_name: str):
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found or expired")

    media_type = "audio/mpeg" if file_name.endswith(".mp3") else "video/mp4"
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=file_name,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
