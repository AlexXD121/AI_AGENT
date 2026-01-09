"""File utilities for temporary file and directory management.

This module provides utilities for managing temporary files and directories
with automatic cleanup to prevent resource leaks.
"""

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from loguru import logger


class TempFileManager:
    """Manager for temporary files and directories with automatic cleanup.
    
    This class ensures temporary files are always cleaned up, even if
    exceptions occur during processing (Requirement 1.4).
    """
    
    def __init__(self, base_dir: str = "data/temp"):
        """Initialize the temporary file manager.
        
        Args:
            base_dir: Base directory for temporary files (default: data/temp)
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_temp_dir(self) -> Generator[Path, None, None]:
        """Create a temporary directory with automatic cleanup.
        
        This context manager ensures the directory is always deleted,
        even if an exception occurs during processing.
        
        Yields:
            Path to the temporary directory
            
        Example:
            >>> with temp_manager.get_temp_dir() as temp_dir:
            ...     # Use temp_dir for processing
            ...     pass
            >>> # temp_dir is automatically deleted here
        """
        # Create unique temporary directory
        temp_dir = Path(tempfile.mkdtemp(dir=self.base_dir))
        logger.debug(f"Created temporary directory: {temp_dir}")
        
        try:
            yield temp_dir
        finally:
            # Guaranteed cleanup even if exception occurs
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.error(f"Failed to clean up temporary directory {temp_dir}: {e}")
    
    @contextmanager
    def get_temp_file(self, suffix: str = "", prefix: str = "tmp") -> Generator[Path, None, None]:
        """Create a temporary file with automatic cleanup.
        
        Args:
            suffix: File suffix (e.g., '.pdf', '.png')
            prefix: File prefix
            
        Yields:
            Path to the temporary file
        """
        # Create temporary file
        fd, temp_path = tempfile.mkstemp(
            suffix=suffix,
            prefix=prefix,
            dir=self.base_dir
        )
        
        # Close file descriptor immediately
        import os
        os.close(fd)
        
        temp_file = Path(temp_path)
        logger.debug(f"Created temporary file: {temp_file}")
        
        try:
            yield temp_file
        finally:
            # Guaranteed cleanup
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.error(f"Failed to clean up temporary file {temp_file}: {e}")
