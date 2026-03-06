from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format: str = "mp4"

FORMAT_MAP = {
    "mp3": "bestaudio[ext=m4a]/bestaudio",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "mp4": "bestvideo+bestaudio/best",
}

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
    fmt = FORMAT_MAP.get(req.format, "best")
    ydl_opts = {"format": fmt, "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(req.url, download=False)
    return {
        "url": info.get("url", ""),
        "filename": f"{info.get('title', 'download')}.{'mp3' if req.format == 'mp3' else 'mp4'}",
    }

@app.get("/api/download/stream")
async def stream_download(url: str, format: str = "mp4"):
    fmt = FORMAT_MAP.get(format, "best")
    ydl_opts = {"format": fmt, "quiet": True}

    if format == "mp3":
        ydl_opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get("title", "download")
        direct_url = info.get("url", "")

    ext = "mp3" if format == "mp3" else "mp4"
    filename = f"{title}.{ext}"

    async def stream():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", direct_url) as resp:
                async for chunk in resp.aiter_bytes(chunk_size=8192):
                    yield chunk

    return StreamingResponse(
        stream(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
