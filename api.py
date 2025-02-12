from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from pathlib import Path
import os
from typing import Optional, Dict, Any
import json
from datetime import datetime
import shutil

# Import pipeline modules
from pipeline import (
    Step_1_download_video,
    Step_2_extract_frames,
    Step_3_analyze_frames,
    Step_4_generate_commentary,
    Step_5_generate_audio,
    Step_6_video_generation
)

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

# Default settings
DEFAULT_SETTINGS = {
    'style': 'news',
    'llm': 'openai',
    'language': 'en',
    'notifications': True,
    'auto_cleanup': True
}

class VideoRequest(BaseModel):
    video_url: str
    style: Optional[str] = "news"
    language: Optional[str] = "en"
    model: Optional[str] = "gpt-4"
    voice_gender: Optional[str] = "MALE"

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "video-commentary-bot"}

async def process_video_task(video_url: str, output_dir: Path, settings: dict):
    """Process video from URL."""
    try:
        # Create status file
        status_file = output_dir / "status.json"
        with open(status_file, 'w') as f:
            json.dump({
                "status": "downloading",
                "message": "Downloading video..."
            }, f)
        
        try:
            # Download video
            logger.info(f"Downloading video from: {video_url}")
            success, metadata, video_title = Step_1_download_video.execute_step(video_url, output_dir)
            
            if not success or not metadata:
                raise Exception("Could not download video from this URL")
            
            # Find the downloaded video file
            video_path = next(Path(output_dir / "video").glob("*.mp4"))
            
            if not os.path.exists(video_path):
                raise Exception("Could not find downloaded video file")
            
            # Update status
            with open(status_file, 'w') as f:
                json.dump({
                    "status": "processing",
                    "message": "Processing video..."
                }, f)
            
            # Extract frames
            logger.info("Extracting frames...")
            key_frames, scene_changes, motion_scores, duration, file_metadata = Step_2_extract_frames.execute_step(
                video_file=str(video_path),
                output_dir=output_dir
            )
            
            # Convert any numpy floats to Python floats
            duration = float(duration)
            motion_scores = [(str(path), float(score)) for path, score in motion_scores]
            
            # Combine metadata
            combined_metadata = {
                **(file_metadata or {}),
                **(metadata or {}),
                'duration': duration,
                'scene_changes': [str(p) for p in scene_changes],
                'motion_scores': motion_scores,
                'language': settings['language']
            }
            
            # Store frame info
            frames_info = {
                'metadata': combined_metadata
            }
            
            # Analyze frames
            logger.info("Analyzing frames...")
            frames_info = await Step_3_analyze_frames.execute_step(
                frames_dir=output_dir / "frames",
                output_dir=output_dir,
                metadata=frames_info['metadata'],
                scene_changes=scene_changes,
                motion_scores=motion_scores,
                video_duration=duration
            )
            
            # Generate commentary
            logger.info("Generating commentary...")
            audio_script = await Step_4_generate_commentary.execute_step(
                frames_info,
                output_dir,
                settings['style']
            )
            
            # Generate audio
            logger.info("Generating audio...")
            audio_path = await Step_5_generate_audio.execute_step(
                audio_script,
                output_dir,
                settings['style']
            )
            
            # Generate final video
            logger.info("Creating final video...")
            final_video = await Step_6_video_generation.execute_step(
                Path(str(video_path)),
                Path(str(audio_path)),
                output_dir,
                settings['style']
            )
            
            if not final_video:
                raise Exception("Failed to generate final video")
            
            # Update status to complete
            with open(status_file, 'w') as f:
                json.dump({
                    "status": "completed",
                    "result": str(final_video)
                }, f)
            
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            with open(status_file, 'w') as f:
                json.dump({
                    "status": "error",
                    "message": str(e)
                }, f)
            
    except Exception as e:
        logger.error(f"Error in process_video_task: {str(e)}")
        with open(status_file, 'w') as f:
            json.dump({
                "status": "error",
                "message": str(e)
            }, f)

@app.post("/process_video")
async def process_video(request: VideoRequest, background_tasks: BackgroundTasks):
    """Process a video with AI commentary"""
    try:
        # Update settings
        settings = DEFAULT_SETTINGS.copy()
        settings.update({
            "style": request.style,
            "language": request.language,
            "model": request.model,
            "voice_gender": request.voice_gender
        })
        
        # Generate job ID and create output directory
        job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_dir = Path(f"output_{job_id}")
        output_dir.mkdir(exist_ok=True)
        
        # Start processing in background
        background_tasks.add_task(
            process_video_task,
            request.video_url,
            output_dir,
            settings
        )
        
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
    """Get the status of a video processing job"""
    try:
        output_dir = Path(f"output_{job_id}")
        
        # Check if the output directory exists
        if not output_dir.exists():
            return {
                "status": "not_found",
                "message": "Job not found"
            }
        
        # Check for status file
        status_file = output_dir / "status.json"
        if status_file.exists():
            with open(status_file, 'r') as f:
                return json.load(f)
        
        # Check for final video
        final_video = next(output_dir.glob("*.mp4"), None)
        if final_video:
            return {
                "status": "completed",
                "result": str(final_video)
            }
        
        # If neither status file nor final video exists, assume processing
        return {
            "status": "processing",
            "message": "Video is being processed"
        }
        
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 