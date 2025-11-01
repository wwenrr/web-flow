import inspect
from pathlib import Path
from typing import Any

from src.common.base.singleton import Singleton
from src.common.helper.file_helper import FileHelper


class SettingHelper(Singleton):
    """
    Singleton class for reading and managing settings from JSON files.
    Automatically finds settings.json in the same directory as the caller's file.
    """
    
    def __init__(self):
        if not hasattr(self, "_settings_cache"):
            self._settings_cache: dict[str, dict[str, Any]] = {}
    
    def get(self) -> dict[str, Any]:
        """
        Get all settings from settings.json in caller's directory.
        
        Returns:
            dict: All settings
            
        Raises:
            FileNotFoundError: If settings.json not found
        """
        return self._load_settings()
    
    def get_section(self, section: str) -> dict[str, Any] | None:
        """
        Get a specific section from settings.json in caller's directory.
        
        Args:
            section: Section name
            
        Returns:
            dict | None: Section settings or None if not found
            
        Raises:
            FileNotFoundError: If settings.json not found
        """
        settings = self._load_settings()
        return settings.get(section)
    
    def _find_settings_path(self) -> Path:
        """
        Find settings.json from the caller's file location.
        
        Returns:
            Path: Path to settings.json
            
        Raises:
            FileNotFoundError: If settings.json not found
        """
        finder = _SettingsPathFinder()
        return finder.find()
    
    def _load_settings(self) -> dict[str, Any]:
        """
        Load settings from settings.json file in caller's directory.
        
        Returns:
            dict: Settings dictionary
            
        Raises:
            FileNotFoundError: If settings.json not found
        """
        settings_path = self._find_settings_path()
        
        # Use string path as cache key
        cache_key = str(settings_path)
        
        # Check cache
        if cache_key in self._settings_cache:
            return self._settings_cache[cache_key]
        
        # Load settings
        file_helper = FileHelper()
        settings = file_helper.read_json_file(settings_path)
        
        # Cache settings
        self._settings_cache[cache_key] = settings
        return settings


class _SettingsPathFinder:
    """
    Helper class for finding settings.json path from caller's file location.
    """

    def find(self) -> Path:
        """
        Find settings.json from the caller's file location.
        
        Returns:
            Path: Path to settings.json
            
        Raises:
            FileNotFoundError: If settings.json not found
        """
        frame = inspect.currentframe()
        try:
            current_frame = frame
            while current_frame:
                current_frame = current_frame.f_back
                if not current_frame:
                    break
                
                frame_module = current_frame.f_globals.get('__name__', '')
                frame_file = current_frame.f_globals.get('__file__')
                
                if not self._is_valid_caller_frame(frame_module, frame_file):
                    continue
                
                return self._check_settings_path(frame_file)
        finally:
            del frame
        
        raise FileNotFoundError("Could not determine caller file location to find settings.json")

    def _is_valid_caller_frame(self, frame_module: str, frame_file: str | None) -> bool:
        if not frame_module or not frame_file:
            return False
        return 'setting_helper' not in frame_module.lower()

    def _check_settings_path(self, frame_file: str) -> Path:
        caller_dir = Path(frame_file).parent
        settings_path = caller_dir / "settings.json"
        if settings_path.exists():
            return settings_path.resolve()
        raise FileNotFoundError(
            f"settings.json not found in {caller_dir}. "
            f"Expected: {settings_path}"
        )
