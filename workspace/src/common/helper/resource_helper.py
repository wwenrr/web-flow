import inspect
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.common.base.singleton import Singleton
from src.common.helper.file_helper import FileHelper


class ResourceHelper(Singleton):
    """
    Singleton class for reading resources from files.
    Automatically finds resources in ./resources/ directory relative to the caller's file.
    """

    def __init__(self):
        if not hasattr(self, "_cache"):
            self._cache: dict[str, Any] = {}

    def get(self, resource_path: str) -> str:
        """
        Get resource content as text from resources directory in caller's location.
        
        Args:
            resource_path: Path to resource file relative to resources/ (e.g., "site-map.html" or "./site-map.html")
        
        Returns:
            str: Resource content as text
            
        Raises:
            FileNotFoundError: If resource file not found
        """
        file_path = self._find_resource_path(resource_path)
        return file_path.read_text(encoding="utf-8")

    def get_json(self, resource_path: str) -> dict[str, Any]:
        """
        Get resource content as JSON from resources directory in caller's location.
        
        Args:
            resource_path: Path to resource file relative to resources/ (e.g., "config.json" or "./config.json")
        
        Returns:
            dict: Resource content as JSON dictionary
            
        Raises:
            FileNotFoundError: If resource file not found
            json.JSONDecodeError: If file is not valid JSON
        """
        file_path = self._find_resource_path(resource_path)
        file_helper = FileHelper()
        return file_helper.read_json_file(file_path)

    def get_binary(self, resource_path: str) -> bytes:
        """
        Get resource content as binary from resources directory in caller's location.
        
        Args:
            resource_path: Path to resource file relative to resources/ (e.g., "image.png" or "./image.png")
        
        Returns:
            bytes: Resource content as binary data
            
        Raises:
            FileNotFoundError: If resource file not found
        """
        file_path = self._find_resource_path(resource_path)
        return file_path.read_bytes()

    def get_enc_binary(self, enc_path: str, key: str | None = None) -> bytes:
        """
        Read and decrypt an OpenSSL .enc file from resources directory.

        It automatically searches under ./resources/<path>. If not found, it will
        also try ./resources/enc/<path>.
        """
        file_path = self._find_resource_path_with_enc_fallback(enc_path)
        decryption_key = self._get_encryption_key(key)

        with tempfile.NamedTemporaryFile(delete=False) as tmp_out:
            tmp_out_path = Path(tmp_out.name)

        try:
            # Try PBKDF2 first
            self._run_openssl_dec(
                input_path=file_path,
                output_path=tmp_out_path,
                key=decryption_key,
                use_pbkdf2=True,
                legacy_md=None,
            )
            return tmp_out_path.read_bytes()
        except subprocess.CalledProcessError:
            # Fallback legacy
            try:
                self._run_openssl_dec(
                    input_path=file_path,
                    output_path=tmp_out_path,
                    key=decryption_key,
                    use_pbkdf2=False,
                    legacy_md="md5",
                )
                return tmp_out_path.read_bytes()
            except subprocess.CalledProcessError as e2:
                raise RuntimeError("Failed to decrypt .enc resource with both PBKDF2 and legacy modes") from e2
        finally:
            try:
                if tmp_out_path.exists():
                    tmp_out_path.unlink()
            except Exception:
                pass

    def get_enc_text(self, enc_path: str, key: str | None = None, encoding: str = "utf-8") -> str:
        data = self.get_enc_binary(enc_path, key)
        return data.decode(encoding)

    def get_enc_json(self, enc_path: str, key: str | None = None, encoding: str = "utf-8") -> Any:
        text = self.get_enc_text(enc_path, key=key, encoding=encoding)
        text = text.lstrip("\ufeff")
        import json as _json
        try:
            return _json.loads(text)
        except _json.JSONDecodeError:
            # NDJSON fallback
            items: list[Any] = []
            for line in text.splitlines():
                s = line.strip()
                if not s:
                    continue
                try:
                    items.append(_json.loads(s))
                except Exception:
                    continue
            if items:
                return items
            # Split concatenated JSON objects '}{'
            parts = re.split(r"(?<=\})\s*(?=\{)", text)
            chunks: list[Any] = []
            for part in parts:
                s = part.strip()
                if not s or not s.startswith("{") or not s.endswith("}"):
                    continue
                try:
                    chunks.append(_json.loads(s))
                except Exception:
                    continue
            if chunks:
                return chunks
            raise

    def _find_resource_path(self, resource_path: str) -> Path:
        """
        Find resource file path from the caller's file location.
        
        Args:
            resource_path: Path to resource file relative to resources/
        
        Returns:
            Path: Path to resource file
            
        Raises:
            FileNotFoundError: If resource file not found
        """
        finder = _ResourcePathFinder()
        caller_path = finder.find_caller_dir()
        
        # Normalize resource path (remove ./ if present)
        normalized_path = resource_path.lstrip("./")
        
        resource_file = caller_path / "resources" / normalized_path
        if resource_file.exists():
            return resource_file.resolve()
        
        raise FileNotFoundError(
            f"Resource not found: {resource_path}. "
            f"Expected: {resource_file}"
        )

    def _find_resource_path_with_enc_fallback(self, resource_path: str) -> Path:
        finder = _ResourcePathFinder()
        caller_path = finder.find_caller_dir()

        normalized_path = resource_path.lstrip("./")
        resource_file = caller_path / "resources" / normalized_path
        if resource_file.exists():
            return resource_file.resolve()
        if not normalized_path.startswith("enc/"):
            alt = caller_path / "resources" / "enc" / normalized_path
            if alt.exists():
                return alt.resolve()
        raise FileNotFoundError(
            f"Resource not found: {resource_path}. Expected: {resource_file} or resources/enc/{normalized_path}"
        )

    def _get_encryption_key(self, provided_key: str | None) -> str:
        if provided_key:
            return provided_key
        env_key = os.environ.get("LOCAL_ENCRYPTION_KEY")
        if not env_key:
            raise RuntimeError("Missing decryption key. Provide key or set $LOCAL_ENCRYPTION_KEY")
        return env_key

    def _run_openssl_dec(self, input_path: Path, output_path: Path, key: str, use_pbkdf2: bool, legacy_md: str | None) -> None:
        cmd: list[str] = [
            "openssl",
            "enc",
            "-d",
            "-aes-256-cbc",
            "-salt",
        ]
        if use_pbkdf2:
            cmd.append("-pbkdf2")
        if legacy_md:
            cmd.extend(["-md", legacy_md])
        cmd.extend([
            "-in",
            str(input_path),
            "-out",
            str(output_path),
            "-pass",
            f"pass:{key}",
        ])
        subprocess.run(cmd, check=True, capture_output=True, text=True)


class _ResourcePathFinder:
    """
    Helper class for finding caller's directory location.
    """

    def find_caller_dir(self) -> Path:
        """
        Find caller's directory from the call stack.
        
        Returns:
            Path: Path to caller's directory
            
        Raises:
            FileNotFoundError: If caller location cannot be determined
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
                
                return Path(frame_file).parent
        finally:
            del frame
        
        raise FileNotFoundError("Could not determine caller file location to find resources")

    def _is_valid_caller_frame(self, frame_module: str, frame_file: str | None) -> bool:
        if not frame_module or not frame_file:
            return False
        return 'resource_helper' not in frame_module.lower()

