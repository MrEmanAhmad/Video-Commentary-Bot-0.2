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
from openai import OpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration
try:
    # Define required variables
    required_vars = [
        'OPENAI_API_KEY',
        'DEEPSEEK_API_KEY',
        'GOOGLE_APPLICATION_CREDENTIALS_JSON',
        'CLOUDINARY_CLOUD_NAME',
        'CLOUDINARY_API_KEY',
        'CLOUDINARY_API_SECRET'
    ]
    
    # First try to get variables from environment (Railway)
    env_vars = {var: os.getenv(var) for var in required_vars}
    missing_vars = [var for var, value in env_vars.items() if not value]
    
    # Log environment status
    logger.info("Checking environment variables...")
    for var in required_vars:
        if os.getenv(var):
            logger.info(f"✓ Found {var} in environment")
        else:
            logger.warning(f"✗ Missing {var} in environment")
    
    # Try to load from railway.json if any variables are missing
    if missing_vars:
        logger.info("Some variables missing, checking railway.json...")
        railway_file = Path("railway.json")
        if railway_file.exists():
            logger.info("Found railway.json, loading configuration...")
            with open(railway_file, 'r') as f:
                config = json.load(f)
            for var in missing_vars:
                if var in config:
                    os.environ[var] = str(config[var])
                    logger.info(f"Loaded {var} from railway.json")
        else:
            logger.warning("railway.json not found")
    
    # Final check for required variables
    still_missing = [var for var in required_vars if not os.getenv(var)]
    if still_missing:
        error_msg = f"Missing required environment variables: {', '.join(still_missing)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Set up Google credentials
    if "GOOGLE_APPLICATION_CREDENTIALS_JSON" in os.environ:
        try:
            # Create credentials directory with proper permissions
            creds_dir = Path("credentials")
            creds_dir.mkdir(exist_ok=True, mode=0o777)
            
            google_creds_file = creds_dir / "google_credentials.json"
            
            # Get credentials JSON and ensure it's properly formatted
            creds_json_str = os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"]
            logger.info("Attempting to parse Google credentials...")
            
            # Try multiple parsing approaches
            try:
                # First, try direct JSON parsing
                creds_json = json.loads(creds_json_str)
            except json.JSONDecodeError as je:
                logger.warning(f"Direct JSON parsing failed: {je}")
                try:
                    # Try cleaning the string and parsing again
                    cleaned_str = creds_json_str.replace('\n', '\\n').replace('\r', '\\r')
                    creds_json = json.loads(cleaned_str)
                except json.JSONDecodeError:
                    logger.warning("Cleaned JSON parsing failed, trying literal eval")
                    try:
                        # Try literal eval as last resort
                        import ast
                        creds_json = ast.literal_eval(creds_json_str)
                    except (SyntaxError, ValueError) as e:
                        logger.error(f"All parsing attempts failed. Original error: {e}")
                        # Log the first and last few characters of the string for debugging
                        str_preview = f"{creds_json_str[:100]}...{creds_json_str[-100:]}" if len(creds_json_str) > 200 else creds_json_str
                        logger.error(f"Credentials string preview: {str_preview}")
                        raise ValueError("Could not parse Google credentials. Please check the format.")
            
            # Validate required fields
            required_fields = [
                "type", "project_id", "private_key_id", "private_key",
                "client_email", "client_id", "auth_uri", "token_uri",
                "auth_provider_x509_cert_url", "client_x509_cert_url"
            ]
            missing_fields = [field for field in required_fields if field not in creds_json]
            if missing_fields:
                raise ValueError(f"Missing required fields in credentials: {', '.join(missing_fields)}")
            
            # Ensure private key is properly formatted
            if 'private_key' in creds_json:
                # Normalize line endings and ensure proper PEM format
                private_key = creds_json['private_key']
                if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
                    private_key = f"-----BEGIN PRIVATE KEY-----\n{private_key}"
                if not private_key.endswith('-----END PRIVATE KEY-----'):
                    private_key = f"{private_key}\n-----END PRIVATE KEY-----"
                creds_json['private_key'] = private_key.replace('\\n', '\n')
            
            # Write credentials file with proper permissions
            with open(google_creds_file, 'w') as f:
                json.dump(creds_json, f, indent=2)
            
            # Set file permissions
            google_creds_file.chmod(0o600)
            
            # Set environment variable to absolute path
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(google_creds_file.absolute())
            logger.info("✓ Google credentials configured successfully")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format in credentials: {e}")
            raise ValueError("Google credentials JSON is not properly formatted")
        except ValueError as e:
            logger.error(f"Invalid credentials content: {e}")
            raise
        except Exception as e:
            logger.error(f"Error setting up Google credentials: {e}")
            raise

    # Initialize Cloudinary configuration
    cloudinary_vars = ['CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET']
    if all(os.getenv(var) for var in cloudinary_vars):
        import cloudinary
        cloudinary.config(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET'),
            secure=True,
            chunk_size=6000000,  # 6MB chunks for faster uploads
            use_cache=True,
            cache_duration=3600  # 1 hour cache
        )
        # Explicitly set environment variables to ensure they're available to subprocesses
        os.environ['CLOUDINARY_CLOUD_NAME'] = os.getenv('CLOUDINARY_CLOUD_NAME')
        os.environ['CLOUDINARY_API_KEY'] = os.getenv('CLOUDINARY_API_KEY')
        os.environ['CLOUDINARY_API_SECRET'] = os.getenv('CLOUDINARY_API_SECRET')
        logger.info("✓ Cloudinary client initialized")
    else:
        logger.error("Missing Cloudinary credentials")
        raise ValueError("Missing required Cloudinary credentials")

    # Continue with the rest of the imports and initialization
    logger.info("✓ Configuration loaded successfully")
    
    # Import pipeline modules
    from pipeline import (
        Step_1_download_video,
        Step_2_extract_frames,
        Step_3_analyze_frames,
        Step_4_generate_commentary,
        Step_5_generate_audio,
        Step_6_video_generation
    )

    # Initialize OpenAI client with API key from environment
    try:
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        logger.info("✓ OpenAI client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        raise

    # Initialize DeepSeek client with API key from environment
    try:
        deepseek_client = OpenAI(
            api_key=os.getenv('DEEPSEEK_API_KEY'),
            base_url="https://api.deepseek.com"
        )
        logger.info("✓ DeepSeek client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize DeepSeek client: {e}")
        raise

    # Initialize Google Text-to-Speech client
    try:
        from google.cloud import texttospeech
        tts_client = texttospeech.TextToSpeechClient()
        logger.info("✓ Google Text-to-Speech client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Text-to-Speech client: {e}")
        raise

except Exception as e:
    logger.error(f"Initialization error: {e}", exc_info=True)
    raise

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

# Voice configurations
VOICE_CONFIGS = {
    'en': {
        'MALE': texttospeech.VoiceSelectionParams(
            language_code="en-GB",
            name="en-GB-Journey-D",
            ssml_gender=texttospeech.SsmlVoiceGender.MALE
        ),
        'FEMALE': texttospeech.VoiceSelectionParams(
            language_code="en-GB",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
    },
    'ur': {
        'MALE': texttospeech.VoiceSelectionParams(
            language_code="ur-PK",
            ssml_gender=texttospeech.SsmlVoiceGender.MALE
        ),
        'FEMALE': texttospeech.VoiceSelectionParams(
            language_code="ur-PK",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
    }
}

# Audio configuration
AUDIO_CONFIG = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3,
    speaking_rate=1.0,
    pitch=0.0,
    effects_profile_id=["headphone-class-device"]
)

async def synthesize_speech(text, voice_params, output_dir, is_ssml=False):
    """Synthesize speech from text using Google Text-to-Speech."""
    if is_ssml:
        synthesis_input = texttospeech.SynthesisInput(ssml=text)
    else:
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
    response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice_params,
        audio_config=AUDIO_CONFIG
    )
    
    output_path = output_dir / "output_audio.mp3"
    with open(output_path, "wb") as out:
        out.write(response.audio_content)
    return output_path

class VideoRequest(BaseModel):
    video_url: str
    style: Optional[str] = "news"
    language: Optional[str] = "en"
    model: Optional[str] = "gpt-4o-mini"
    voice_gender: Optional[str] = "MALE"

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

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
            
            # Generate commentary using the specified model
            logger.info("Generating commentary...")
            if settings['model'] == "gpt-4o-mini":
                completion = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "developer", "content": "Generate engaging video commentary."},
                        {"role": "user", "content": json.dumps(frames_info)}
                    ]
                )
                audio_script = completion.choices[0].message.content
            else:
                response = deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "Generate engaging video commentary."},
                        {"role": "user", "content": json.dumps(frames_info)}
                    ],
                    stream=False
                )
                audio_script = response.choices[0].message.content
            
            # Generate audio using Google Text-to-Speech
            logger.info("Generating audio...")
            voice_params = VOICE_CONFIGS[settings['language']][settings['voice_gender']]
            audio_path = await synthesize_speech(
                text=audio_script,
                voice_params=voice_params,
                output_dir=output_dir
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