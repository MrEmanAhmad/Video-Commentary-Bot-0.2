import os
import sys
import logging
from pathlib import Path
import json

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('streamlit_app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Set stdout and stderr encoding to UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

try:
    import streamlit as st
    
    # Set page config first
    st.set_page_config(
        page_title="AI Video Commentary Bot",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': None
        }
    )
    
    # Show loading message
    loading_placeholder = st.empty()
    loading_placeholder.info("🔄 Initializing application...")
    
    # Load configuration
    try:
        # Define required variables
        required_vars = [
            'OPENAI_API_KEY',
            'DEEPSEEK_API_KEY',
            'GOOGLE_APPLICATION_CREDENTIALS_JSON'
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
            st.error(f"⚠️ Configuration Error: {error_msg}")
            st.error("Please ensure all required environment variables are set in Railway or railway.json")
            st.stop()
        
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
                st.error("⚠️ Error: Google credentials JSON is not properly formatted. Please check the credential format.")
                st.stop()
            except ValueError as e:
                logger.error(f"Invalid credentials content: {e}")
                st.error(f"⚠️ Error: {str(e)}")
                st.stop()
            except Exception as e:
                logger.error(f"Error setting up Google credentials: {e}")
                st.error("⚠️ Error setting up Google credentials. Please check the logs for details.")
                st.stop()

        # Continue with the rest of the imports and initialization
        logger.info("✓ Configuration loaded successfully")
        loading_placeholder.success("✓ Configuration loaded successfully")
        
        # Import required modules
        import tempfile
        import asyncio
        import json
        from datetime import datetime
        import shutil
        from telegram.ext import ContextTypes
        from telegram import Bot
        import gc
        import tracemalloc
        import psutil
        
        from new_bot import VideoBot
        from pipeline import Step_1_download_video, Step_7_cleanup
        
        # Initialize VideoBot with proper caching
        @st.cache_resource(show_spinner=False)
        def init_bot():
            """Initialize the VideoBot instance with caching"""
            try:
                return VideoBot()
            except Exception as e:
                logger.error(f"Bot initialization error: {e}")
                raise
        
        # Initialize bot instance
        bot = init_bot()
        
        # Initialize session state
        if 'initialized' not in st.session_state:
            st.session_state.initialized = False
            st.session_state.settings = bot.default_settings.copy()
            st.session_state.is_processing = False
            st.session_state.progress = 0
            st.session_state.status = ""
            st.session_state.initialized = True
        
        # Clear loading message
        loading_placeholder.empty()
        
        # Safe cleanup function
        def cleanup_memory(force=False):
            """Force garbage collection and clear memory"""
            try:
                if force or not st.session_state.get('is_processing', False):
                    gc.collect()
                    
                # Clear temp directories that are older than 1 hour
                current_time = datetime.now().timestamp()
                for pattern in ['temp_*', 'output_*']:
                    for path in Path().glob(pattern):
                        try:
                            if path.is_dir():
                                # Check if directory is older than 1 hour
                                if current_time - path.stat().st_mtime > 3600:
                                    shutil.rmtree(path, ignore_errors=True)
                        except Exception as e:
                            logger.warning(f"Failed to remove directory {path}: {e}")
                
                logger.info("Cleanup completed successfully")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        
        # Custom CSS with mobile responsiveness and centered content
        st.markdown("""
            <style>
            /* Global responsive container */
            .main {
                max-width: 1200px;
                margin: 0 auto;
                padding: 1rem;
            }

            /* Responsive text sizing */
            @media (max-width: 768px) {
                h1 { font-size: 1.5rem !important; }
                h2 { font-size: 1.3rem !important; }
                p, div { font-size: 0.9rem !important; }
            }

            /* Center all content */
            .stApp {
                max-width: 100%;
                margin: 0 auto;
            }

            /* Make tabs more mobile-friendly */
            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
                flex-wrap: wrap;
            }

            .stTabs [data-baseweb="tab"] {
                height: auto !important;
                padding: 10px !important;
                white-space: normal !important;
                min-width: 120px;
            }

            /* Responsive video grid */
            .sample-video-grid {
                display: grid;
                gap: 1rem;
                width: 100%;
                padding: 1rem;
            }

            /* Responsive grid breakpoints */
            @media (min-width: 1200px) {
                .sample-video-grid { grid-template-columns: repeat(3, 1fr); }
            }
            @media (min-width: 768px) and (max-width: 1199px) {
                .sample-video-grid { grid-template-columns: repeat(2, 1fr); }
            }
            @media (max-width: 767px) {
                .sample-video-grid { grid-template-columns: 1fr; }
            }

            /* Make all videos responsive and reel-sized */
            .stVideo {
                width: 100% !important;
                height: auto !important;
                max-width: 400px !important;
                margin: 0 auto !important;
            }

            video {
                width: 100% !important;
                height: auto !important;
                max-height: 80vh;
                aspect-ratio: 9/16 !important;
                object-fit: cover !important;
                border-radius: 10px;
                background: #000;
            }

            /* URL input and button styling */
            .url-input-container {
                width: 100%;
                max-width: 600px;
                margin: 0 auto;
                padding: 1rem;
            }

            /* Style text inputs */
            .stTextInput input {
                width: 100%;
                max-width: 600px;
                margin: 0 auto;
                padding: 0.5rem;
                border-radius: 5px;
            }

            /* Style buttons */
            .stButton button {
                width: auto !important;
                min-width: 150px;
                max-width: 300px;
                margin: 1rem auto !important;
                padding: 0.5rem 1rem !important;
                display: block !important;
                border-radius: 5px;
            }

            /* Responsive sidebar */
            @media (max-width: 768px) {
                .css-1d391kg {
                    width: 100% !important;
                }
            }

            /* Loading and status messages */
            .stAlert {
                max-width: 600px;
                margin: 1rem auto !important;
            }

            /* Center download button and style it */
            .download-button-container {
                display: flex;
                justify-content: center;
                align-items: center;
                width: 100%;
                margin: 1rem auto;
                padding: 0.5rem;
            }

            .stDownloadButton {
                display: flex !important;
                justify-content: center !important;
                margin: 1rem auto !important;
            }

            .stDownloadButton > button {
                background-color: #FF4B4B !important;
                color: white !important;
                padding: 0.5rem 2rem !important;
                border-radius: 25px !important;
                font-weight: 600 !important;
                transition: all 0.3s ease !important;
                border: none !important;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
            }

            .stDownloadButton > button:hover {
                background-color: #FF3333 !important;
                transform: translateY(-2px) !important;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2) !important;
            }

            /* Video card styling */
            .sample-video-card {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 10px;
                padding: 1rem;
                width: 100%;
                max-width: 400px;
                margin: 0 auto;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                transition: transform 0.2s;
            }

            /* Generated video container */
            .generated-video-container {
                width: 100%;
                max-width: 400px;
                margin: 2rem auto;
                padding: 1rem;
            }

            /* Center all content and animations */
            .stApp {
                max-width: 100%;
                margin: 0 auto;
                text-align: center;
            }

            /* Center status messages and emojis */
            .stMarkdown {
                text-align: center;
            }
            
            /* Make status messages stand out */
            .status-message {
                background-color: rgba(255, 255, 255, 0.1);
                padding: 1rem;
                border-radius: 10px;
                margin: 1rem auto;
                max-width: 600px;
                text-align: center;
            }

            /* Video duration warning */
            .duration-warning {
                color: #ff4b4b;
                background-color: rgba(255, 75, 75, 0.1);
                padding: 0.5rem;
                border-radius: 5px;
                margin: 0.5rem auto;
                max-width: 600px;
                font-weight: bold;
                text-align: center;
            }

            /* Center emojis and make them larger */
            .emoji-large {
                font-size: 2rem;
                text-align: center;
                display: block;
                margin: 1rem auto;
            }
            </style>
        """, unsafe_allow_html=True)
        
        # Title and description
        st.title("🎬 AI Video Commentary Bot")
        st.markdown("<div class='emoji-large'>✨</div>", unsafe_allow_html=True)
        st.markdown("""
            Transform your videos with AI-powered commentary in multiple styles and languages.
            Upload a video or provide a URL to get started!
        """)
        
        # Add duration warning
        st.markdown("<div class='duration-warning'>⚠️ Videos must be 2 minutes or shorter</div>", unsafe_allow_html=True)
        
        # Update status messages to use centered styling
        if st.session_state.get('status'):
            st.markdown(f"<div class='status-message'>{st.session_state.status}</div>", unsafe_allow_html=True)
        
        # Sidebar for settings
        with st.sidebar:
            st.header("⚙️ Settings")
            
            # AI Model selection first
            st.subheader("AI Model")
            llm = st.selectbox(
                "Choose AI model",
                options=["openai", "deepseek"],
                format_func=lambda x: "🧠 OpenAI GPT-4" if x == "openai" else "🤖 Deepseek",
                key="llm"
            )
            
            # Language selection with model compatibility check
            st.subheader("Language")
            available_languages = ["en", "ur"] if llm == "openai" else ["en"]
            language = st.selectbox(
                "Choose language",
                options=available_languages,
                format_func=lambda x: {
                    "en": "🇬🇧 English - Default language",
                    "ur": "🇵🇰 Urdu - اردو"
                }[x],
                key="language"
            )
            
            # Add warning if trying to use Urdu with Deepseek
            if llm == "deepseek" and language == "ur":
                st.warning("⚠️ Urdu language requires OpenAI GPT-4")
            
            # Style selection
            st.subheader("Commentary Style")
            style = st.selectbox(
                "Choose your style",
                options=["news", "funny", "nature", "infographic"],
                format_func=lambda x: {
                    "news": "📰 News - Professional reporting",
                    "funny": "😄 Funny - Humorous commentary",
                    "nature": "🌿 Nature - Documentary style",
                    "infographic": "📊 Infographic - Educational"
                }[x],
                key="style"
            )
            
            # Add style description
            style_descriptions = {
                "news": "Clear, objective reporting with professional tone",
                "funny": "Light-hearted, entertaining commentary with humor",
                "nature": "Descriptive narration with scientific insights",
                "infographic": "Educational content with clear explanations"
            }
            st.caption(style_descriptions[style])
            
            # Update settings in session state and bot's user settings
            user_id = 0  # Default user ID for Streamlit interface
            init_bot().update_user_setting(user_id, 'style', style)
            init_bot().update_user_setting(user_id, 'llm', llm)
            init_bot().update_user_setting(user_id, 'language', language)
            st.session_state.settings = init_bot().get_user_settings(user_id)
        
        # Add these classes and process_video function before the tab sections
        class StreamlitMessage:
            """Mock Telegram message for status updates"""
            def __init__(self):
                self.message_id = 0
                self.text = ""
                self.video = None
                self.file_id = None
                self.file_name = None
                self.mime_type = None
                self.file_size = None
                self.download_placeholder = st.empty()
                self.video_placeholder = st.empty()
                self.status_placeholder = st.empty()
                self.output_filename = None
                
            async def reply_text(self, text, **kwargs):
                logger.info(f"Status update: {text}")
                self.text = text
                st.session_state.status = text
                self.status_placeholder.markdown(f"🔄 {text}")
                return self
                
            async def edit_text(self, text, **kwargs):
                return await self.reply_text(text)
                
            async def reply_video(self, video, caption=None, **kwargs):
                logger.info("Handling video reply")
                try:
                    if hasattr(video, 'read'):
                        video_data = video.read()
                        self.output_filename = getattr(video, 'name', None)
                    elif isinstance(video, str) and os.path.exists(video):
                        self.output_filename = video
                        with open(video, 'rb') as f:
                            video_data = f.read()
                    else:
                        logger.error("Invalid video format")
                        st.error("Invalid video format")
                        return self
                    
                    # Store video data in session state
                    st.session_state.processed_video = video_data
                    
                    # Display video with download button
                    self.video_placeholder.markdown("<div class='generated-video-container'>", unsafe_allow_html=True)
                    if caption:
                        self.video_placeholder.markdown(f"### {caption}")
                    self.video_placeholder.video(video_data)
                    
                    # Add download button with unique key
                    self.video_placeholder.download_button(
                        label="⬇️ Download Enhanced Video",
                        data=video_data,
                        file_name="enhanced_video.mp4",
                        mime="video/mp4",
                        help="Click to download the enhanced video with AI commentary",
                        key="download_button_reply"
                    )
                    
                    self.video_placeholder.markdown("</div>", unsafe_allow_html=True)
                    return self
                    
                except Exception as e:
                    logger.error(f"Error in reply_video: {str(e)}")
                    st.error(f"Error displaying video: {str(e)}")
                    return self

        class StreamlitUpdate:
            """Mock Telegram Update for bot compatibility"""
            def __init__(self):
                logger.info("Initializing StreamlitUpdate")
                self.effective_user = type('User', (), {'id': 0})
                self.message = StreamlitMessage()
                self.effective_message = self.message

        class StreamlitContext:
            """Mock Telegram context"""
            def __init__(self):
                logger.info("Initializing StreamlitContext")
                self.bot = type('MockBot', (), {
                    'get_file': lambda *args, **kwargs: None,
                    'send_message': lambda *args, **kwargs: None,
                    'edit_message_text': lambda *args, **kwargs: None,
                    'send_video': lambda *args, **kwargs: None,
                    'send_document': lambda *args, **kwargs: None
                })()
                self.args = []
                self.matches = None
                self.user_data = {}
                self.chat_data = {}
                self.bot_data = {}

        async def process_video():
            # Check if already processing and reset if stuck
            if st.session_state.is_processing:
                # If stuck for more than 5 minutes, reset
                if hasattr(st.session_state, 'processing_start_time'):
                    if (datetime.now() - st.session_state.processing_start_time).total_seconds() > 300:
                        st.session_state.is_processing = False
                        logger.warning("Reset stuck processing state")
                    else:
                        st.warning("⚠️ Already processing a video. Please wait.")
                        return
                else:
                    st.session_state.is_processing = False
            
            try:
                # Set processing start time
                st.session_state.processing_start_time = datetime.now()
                st.session_state.is_processing = True
                
                update = StreamlitUpdate()
                context = StreamlitContext()
                
                # Create placeholders for status and video
                status_placeholder = st.empty()
                video_container = st.empty()
                
                # Show processing status
                status_placeholder.info("🎬 Starting video processing...")
                
                if video_url:
                    logger.info(f"Processing video URL: {video_url}")
                    await bot.process_video_from_url(update, context, video_url)
                elif uploaded_file:
                    logger.info(f"Processing uploaded file: {uploaded_file.name}")
                    status_placeholder.info("📥 Processing uploaded video...")
                    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        await bot.process_video_file(update, context, tmp.name, update.message)
                
                # Check if video was processed successfully
                if st.session_state.get('processed_video'):
                    status_placeholder.success("✅ Processing complete!")
                else:
                    logger.error("No video data found after processing")
                    status_placeholder.error("❌ Failed to generate video")
                
            except Exception as e:
                logger.error(f"Error processing video: {str(e)}")
                status_placeholder.error(f"❌ Error processing video: {str(e)}")
            finally:
                # Clear processing state
                st.session_state.is_processing = False
                if hasattr(st.session_state, 'processing_start_time'):
                    delattr(st.session_state, 'processing_start_time')
                cleanup_memory(force=True)

        # Main content area with responsive containers
        tab1, tab2 = st.tabs(["🔗 Video URL", "🎥 Sample Videos"])
        
        # Video URL Tab
        with tab1:
            st.markdown("<div class='url-input-container'>", unsafe_allow_html=True)
            video_url = st.text_input(
                "Enter video URL",
                placeholder="https://example.com/video.mp4",
                help="Support for YouTube, Vimeo, TikTok, and more",
                label_visibility="collapsed"
            )
            
            if video_url:
                if st.button("Process URL", key="process_url"):
                    if not video_url.startswith(('http://', 'https://')):
                        st.error("❌ Please provide a valid URL starting with http:// or https://")
                    else:
                        try:
                            if not st.session_state.is_processing:
                                st.session_state.progress = 0
                                st.session_state.status = "Starting video processing..."
                                asyncio.run(process_video())
                            else:
                                st.warning("⚠️ Already processing a video. Please wait.")
                        except Exception as e:
                            logger.error(f"Error in process_url: {str(e)}")
                            st.error("❌ Failed to process video URL. Please try again.")
                            st.session_state.is_processing = False
            st.markdown("</div>", unsafe_allow_html=True)
            
        # Sample Videos Tab
        with tab2:
            st.markdown("<div class='sample-video-grid'>", unsafe_allow_html=True)
            
            # Get list of sample videos
            sample_videos_dir = Path("sample_generated_videos")
            if sample_videos_dir.exists():
                sample_videos = list(sample_videos_dir.glob("*.mp4"))
                
                # Display each sample video in a card
                for video_path in sample_videos:
                    st.markdown("<div class='sample-video-card'>", unsafe_allow_html=True)
                    st.video(str(video_path))
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("No sample videos available")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Add memory monitoring
        if st.sidebar.checkbox("Show Memory Usage"):
            process = psutil.Process()
            memory_info = process.memory_info()
            st.sidebar.write(f"Memory Usage: {memory_info.rss / 1024 / 1024:.2f} MB")
            if st.sidebar.button("Force Cleanup"):
                cleanup_memory()
                st.sidebar.success("Memory cleaned up!")
        
        # Add this section after the tabs to ensure video persists
        if st.session_state.get('processed_video'):
            st.markdown("<div class='generated-video-container'>", unsafe_allow_html=True)
            st.video(st.session_state.processed_video)
            st.markdown("<div class='download-button-container'>", unsafe_allow_html=True)
            st.download_button(
                label="⬇️ Download Enhanced Video",
                data=st.session_state.processed_video,
                file_name="enhanced_video.mp4",
                mime="video/mp4",
                help="Click to download the enhanced video with AI commentary",
                key="download_button_persist"
            )
            st.markdown("</div></div>", unsafe_allow_html=True)
        
        # Help section
        with st.expander("ℹ️ Help & Information"):
            st.markdown("""
                ### How to Use
                1. Choose your preferred settings in the sidebar
                2. Upload a video file or provide a video URL
                3. Click the process button and wait for the magic!
                
                ### Features
                - Multiple commentary styles
                - Support for different languages
                - Choice of AI models
                - Professional voice synthesis
                
                ### Limitations
                - Maximum video size: 50MB
                - Maximum duration: 5 minutes
                - Supported formats: MP4, MOV, AVI
                
                ### Need Help?
                If you encounter any issues, try:
                - Using a shorter video
                - Converting your video to MP4 format
                - Checking your internet connection
                - Refreshing the page
            """)
        
    except Exception as e:
        logger.error(f"Initialization error: {e}", exc_info=True)
        st.error(f"⚠️ Failed to initialize application: {str(e)}")
        st.stop()
        
except Exception as e:
    logger.error(f"Critical error: {e}", exc_info=True)
    # If streamlit itself fails to import or initialize
    print(f"Critical error: {e}")
    sys.exit(1) 