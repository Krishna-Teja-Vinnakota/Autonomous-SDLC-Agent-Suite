"""
Unzip Tool for handling ZIP file uploads
Provides safe extraction with validation and error handling
"""

import os
import zipfile
import shutil
from pathlib import Path
from typing import Tuple, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UnzipTool:
    """
    Tool for handling ZIP file operations
    Provides safe extraction with size limits and validation
    """

    # Security limits
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
    MAX_EXTRACTED_SIZE = 1024 * 1024 * 1024  # 1 GB
    MAX_FILES = 10000  # Maximum number of files

    @staticmethod
    def validate_zip_file(zip_path: Path) -> Tuple[bool, str]:
        """
        Validate ZIP file before extraction
        
        Args:
            zip_path: Path to ZIP file
            
        Returns:
            Tuple[bool, str]: (is_valid, message)
        """
        try:
            # Check if file exists
            if not zip_path.exists():
                return False, f"ZIP file does not exist: {zip_path}"

            # Check file size
            file_size = zip_path.stat().st_size
            if file_size > UnzipTool.MAX_FILE_SIZE:
                return False, f"ZIP file too large: {file_size} bytes (max: {UnzipTool.MAX_FILE_SIZE})"

            # Check if it's a valid ZIP file
            if not zipfile.is_zipfile(zip_path):
                return False, f"Invalid ZIP file: {zip_path}"

            # Open and validate contents
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Check for zip bombs
                total_size = sum(info.file_size for info in zf.filelist)
                if total_size > UnzipTool.MAX_EXTRACTED_SIZE:
                    return False, f"Extracted size too large: {total_size} bytes"

                # Check number of files
                if len(zf.filelist) > UnzipTool.MAX_FILES:
                    return False, f"Too many files: {len(zf.filelist)} (max: {UnzipTool.MAX_FILES})"

                # Check for path traversal attempts
                for info in zf.filelist:
                    if info.filename.startswith('/') or '..' in info.filename:
                        return False, f"Unsafe file path detected: {info.filename}"

            return True, "ZIP file is valid"

        except zipfile.BadZipFile:
            return False, "Corrupted or invalid ZIP file"
        except Exception as e:
            return False, f"Error validating ZIP file: {str(e)}"

    @staticmethod
    def extract_zip(
        zip_path: Path,
        target_path: Path,
        remove_root: bool = True
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Extract ZIP file to target path
        
        Args:
            zip_path: Path to ZIP file
            target_path: Destination path for extraction
            remove_root: If True, remove single root folder structure
            
        Returns:
            Tuple[bool, str, Optional[Dict]]: (success, message, metadata)
        """
        try:
            # Validate ZIP file
            is_valid, validation_msg = UnzipTool.validate_zip_file(zip_path)
            if not is_valid:
                return False, validation_msg, None

            # Ensure target path exists
            target_path.mkdir(parents=True, exist_ok=True)

            # Check if target path is empty
            if any(target_path.iterdir()):
                return False, f"Target path is not empty: {target_path}", None

            logger.info(f"Extracting ZIP file: {zip_path} to {target_path}")

            # Extract ZIP file
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(target_path)

            # Remove single root folder if requested
            if remove_root:
                contents = list(target_path.iterdir())
                if len(contents) == 1 and contents[0].is_dir():
                    root_folder = contents[0]
                    temp_path = target_path.parent / f"{target_path.name}_temp"
                    
                    # Move contents up one level
                    shutil.move(str(root_folder), str(temp_path))
                    shutil.rmtree(target_path)
                    shutil.move(str(temp_path), str(target_path))

            # Gather metadata
            file_count = sum(1 for _ in target_path.rglob('*') if _.is_file())
            dir_count = sum(1 for _ in target_path.rglob('*') if _.is_dir())
            
            metadata = {
                'zip_file': str(zip_path.name),
                'extracted_files': file_count,
                'extracted_dirs': dir_count,
                'target_path': str(target_path)
            }

            logger.info(f"Successfully extracted {file_count} files")
            return True, f"Successfully extracted {file_count} files", metadata

        except Exception as e:
            error_msg = f"Error extracting ZIP file: {str(e)}"
            logger.error(error_msg)
            
            # Cleanup on failure
            if target_path.exists():
                shutil.rmtree(target_path, ignore_errors=True)
            
            return False, error_msg, None

    @staticmethod
    def save_uploaded_zip(uploaded_file, temp_dir: Path) -> Tuple[bool, str, Optional[Path]]:
        """
        Save uploaded Streamlit file to temporary location
        
        Args:
            uploaded_file: Streamlit UploadedFile object
            temp_dir: Temporary directory for saving
            
        Returns:
            Tuple[bool, str, Optional[Path]]: (success, message, zip_path)
        """
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
            zip_path = temp_dir / uploaded_file.name

            # Write uploaded file
            with open(zip_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())

            logger.info(f"Saved uploaded ZIP to {zip_path}")
            return True, "File saved successfully", zip_path

        except Exception as e:
            error_msg = f"Error saving uploaded file: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None

