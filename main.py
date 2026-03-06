from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Catch ALL unhandled exceptions and ensure CORS headers are included
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "*",
        },
    )

class AnalyzeRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format: str = "mp4"

@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download")
def download(req: DownloadRequest):
    try:
        if req.format == "thumbnail":
            ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(req.url, download=False)
            return {"url": info.get("thumbnail", "")}

        format_map = {
            "mp3": "bestaudio[ext=m4a]/bestaudio",
            "mp4": "best[ext=mp4]/best",
        }
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": format_map.get(req.format, format_map["mp4"]),
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=False)
            if info.get("url"):
                download_url = info["url"]
            elif info.get("requested_formats"):
                download_url = info["requested_formats"][0]["url"]
            else:
                raise Exception("Could not extract download URL")

        return {"url": download_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
