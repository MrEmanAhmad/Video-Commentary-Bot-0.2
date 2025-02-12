from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from pathlib import Path
import os
from typing import Optional, Dict, Any
from new_bot import VideoBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Video Commentary Bot API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Initialize VideoBot
bot = VideoBot()

class VideoRequest(BaseModel):
    video_url: str
    style: Optional[str] = "news"
    language: Optional[str] = "en"
    model: Optional[str] = "gpt-4"
    voice_gender: Optional[str] = "MALE"

@app.options("/process_video")
async def process_video_preflight():
    """Handle preflight requests for the process_video endpoint"""
    return {}

@app.post("/process_video")
async def process_video(request: VideoRequest, background_tasks: BackgroundTasks):
    """
    Process a video with AI commentary
    
    Parameters:
    - video_url: URL of the video to process
    - style: Commentary style (news, funny, nature, infographic)
    - language: Output language (en, ur, etc.)
    - model: AI model to use (gpt-4, deepseek-chat)
    - voice_gender: Voice gender for TTS (MALE, FEMALE)
    
    Returns:
    - job_id: Unique identifier for the processing job
    - status: Current status of the job
    """
    try:
        # Update settings based on request
        settings = bot.default_settings.copy()
        settings.update({
            "style": request.style,
            "language": request.language,
            "model": request.model,
            "voice_gender": request.voice_gender
        })
        
        # Start processing in background
        job_id = await bot.start_processing(request.video_url, settings)
        
        return {
            "job_id": job_id,
            "status": "processing",
            "message": "Video processing started successfully"
        }
        
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/job_status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a video processing job
    
    Parameters:
    - job_id: The unique identifier returned by process_video
    
    Returns:
    - status: Current status of the job
    - result: URL of the processed video if complete
    """
    try:
        status = await bot.get_job_status(job_id)
        return status
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 