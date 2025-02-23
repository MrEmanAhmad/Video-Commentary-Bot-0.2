"""
Step 7: Cleanup module
Cleans up temporary files and directories
"""

import os
import logging
import shutil
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

def cleanup_temp_files(temp_dirs: List[Path]) -> None:
    """
    Clean up temporary directories and files.
    
    Args:
        temp_dirs: List of temporary directory paths to clean up
    """
    for temp_dir in temp_dirs:
        try:
            if temp_dir.exists():
                # Check if directory contains final video
                final_videos = list(temp_dir.glob("final_video_*.mp4"))
                if final_videos:
                    logger.info(f"Skipping cleanup of {temp_dir} as it contains final video")
                    continue
                    
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Could not delete directory {temp_dir}: {e}")

def cleanup_temp_files_with_pattern(pattern: str) -> None:
    """
    Clean up temporary files matching a pattern.
    
    Args:
        pattern: Glob pattern to match files/directories
    """
    try:
        for path in Path().glob(pattern):
            try:
                # Skip if directory contains final video
                if path.is_dir():
                    final_videos = list(path.glob("final_video_*.mp4"))
                    if final_videos:
                        logger.info(f"Skipping cleanup of {path} as it contains final video")
                        continue
                        
                if path.is_file():
                    # Skip final videos
                    if "final_video_" in path.name and path.suffix == ".mp4":
                        logger.info(f"Skipping cleanup of final video: {path}")
                        continue
                    path.unlink()
                    logger.info(f"Deleted file: {path}")
                elif path.is_dir():
                    shutil.rmtree(path)
                    logger.info(f"Deleted directory: {path}")
            except Exception as e:
                logger.warning(f"Could not delete {path}: {e}")
    except Exception as e:
        logger.error(f"Error cleaning up pattern {pattern}: {e}")

def execute_step(temp_dirs: List[Path] = None) -> None:
    """
    Execute cleanup step.
    
    Args:
        temp_dirs: Optional list of temporary directories to clean up
    """
    logger.debug("Step 7: Cleaning up...")
    
    try:
        # Clean up specific temp directories if provided
        if temp_dirs:
            cleanup_temp_files(temp_dirs)
        
        # Clean up any remaining temp files/directories
        cleanup_temp_files_with_pattern("temp_*")
        cleanup_temp_files_with_pattern("output_*")
        
        logger.info("Cleanup completed successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}") 