"""File utilities for temporary file and directory management with secure deletion.

This module provides utilities for managing temporary files and directories
with automatic cleanup and secure deletion to prevent forensic recovery.
"""

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from loguru import logger


def secure_delete(path: Path, passes: int = 3) -> bool:
    """Securely delete a file by overwriting before removal.
    
    Prevents forensic recovery by overwriting file contents with
    random data before deletion.
    
    Args:
        path: Path to file to delete
        passes: Number of overwrite passes (default: 3)
                1 pass = fast, 3 passes = secure, 7 passes = paranoid
    
    Returns:
        True if file was securely deleted, False otherwise
        
    Example:
        >>> secure_delete(Path("sensitive_document.pdf"))
        True
    """
    path = Path(path)
    
    if not path.exists():
        logger.warning(f"File not found for secure deletion: {path}")
        return False
    
    if not path.is_file():
        logger.error(f"Cannot secure delete non-file: {path}")
        return False
    
    try:
        # Get file size
        file_size = path.stat().st_size
        
        if file_size == 0:
            # Empty file, just delete
            path.unlink()
            logger.debug(f"Deleted empty file: {path}")
            return True
        
        # Overwrite file contents multiple times
        for pass_num in range(passes):
            with open(path, 'r+b') as f:
                # Seek to start
                f.seek(0)
                
                # Pattern for this pass
                if pass_num == 0:
                    # First pass: zeros
                    pattern = b'\x00'
                elif pass_num == 1:
                    # Second pass: ones
                    pattern = b'\xFF'
                else:
                    # Subsequent passes: random
                    import secrets
                    pattern = secrets.token_bytes(min(file_size, 4096))
                
                # Write pattern
                remaining = file_size
                while remaining > 0:
                    chunk_size = min(remaining, len(pattern))
                    f.write(pattern[:chunk_size])
                    remaining -= chunk_size
                
                # Flush to disk
                f.flush()
                os.fsync(f.fileno())
        
        # Finally, delete the file
        path.unlink()
        
        logger.info(f"Securely deleted file: {path} ({passes} passes)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to securely delete {path}: {e}")
        return False


def secure_delete_directory(path: Path, secure_files: bool = True) -> bool:
    """Securely delete a directory and all its contents.
    
    Args:
        path: Path to directory
        secure_files: Whether to securely delete files (slower but more secure)
    
    Returns:
        True if directory was deleted
    """
    path = Path(path)
    
    if not path.exists():
        return False
    
    if not path.is_dir():
        logger.error(f"Not a directory: {path}")
        return False
    
    try:
        if secure_files:
            # Securely delete all files first
            for item in path.rglob('*'):
                if item.is_file():
                    secure_delete(item)
        
        # Remove directory structure
        shutil.rmtree(path)
        
        logger.info(f"Securely deleted directory: {path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to securely delete directory {path}: {e}")
        return False


class TempFileManager:
    """Manager for temporary files and directories with automatic cleanup.
    
    This class ensures temporary files are always cleaned up securely,
    even if exceptions occur during processing (Requirement 1.4).
    """
    
    def __init__(self, base_dir: str = "data/temp", secure_deletion: bool = True):
        """Initialize the temporary file manager.
        
        Args:
            base_dir: Base directory for temporary files (default: data/temp)
            secure_deletion: Whether to use secure deletion (default: True)
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.secure_deletion = secure_deletion
    
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
                    if self.secure_deletion:
                        secure_delete_directory(temp_dir, secure_files=True)
                    else:
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
        os.close(fd)
        
        temp_file = Path(temp_path)
        logger.debug(f"Created temporary file: {temp_file}")
        
        try:
            yield temp_file
        finally:
            # Guaranteed cleanup
            try:
                if temp_file.exists():
                    if self.secure_deletion:
                        secure_delete(temp_file, passes=1)  # 1 pass for temp files (balance speed/security)
                    else:
                        temp_file.unlink()
                    logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.error(f"Failed to clean up temporary file {temp_file}: {e}")

