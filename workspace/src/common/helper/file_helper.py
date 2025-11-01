import json
from pathlib import Path
from typing import Any

from src.common.base.singleton import Singleton


class FileHelper(Singleton):
    """
    Singleton class for file operations.
    Provides methods to read and manipulate files.
    """
    
    def read_json_file(self, file_path: str | Path) -> dict[str, Any]:
        """
        Read JSON file and return object (dict).
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            dict: JSON content as dictionary
            
        Raises:
            FileNotFoundError: If file does not exist
            json.JSONDecodeError: If file is not valid JSON
        """
        file_path = Path(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def write_json_file(self, file_path: str | Path, data: Any) -> None:
        """
        Write data to JSON file.
        
        Args:
            file_path: Path to JSON file
            data: Data to write (must be JSON serializable)
            
        Raises:
            OSError: If file cannot be written
        """
        file_path = Path(file_path)
        
        # Create directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


