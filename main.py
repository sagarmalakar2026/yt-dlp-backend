from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "*",
}

# Standard CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Force CORS headers on ALL responses, including crashes
@app.middleware("http")
async def force_cors_on_every_response(request: Request, call_next):
    if request.method == "OPTIONS":
        return JSONResponse(content={"ok": True}, headers=CORS_HEADERS)

    try:
        response = await call_next(request)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)},
            headers=CORS_HEADERS,
        )

    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    return response

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
    "mp4": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
    "4k": "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "thumbnail": None,
}
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
                return {"url": info["url"]}

            if info.get("requested_formats") and info["requested_formats"][0].get("url"):
                return {"url": info["requested_formats"][0]["url"]}

            raise Exception("Could not extract download URL")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
