import inspect
import os
import subprocess
import tempfile
import re
from pathlib import Path
from typing import Any

from src.common.base.singleton import Singleton
from src.common.helper.file_helper import FileHelper


class DataHelper(Singleton):
    """
    Singleton class for reading and writing data files.
    Automatically finds data in ./data/ directory relative to the caller's file.
    """

    def __init__(self):
        if not hasattr(self, "_cache"):
            self._cache: dict[str, Any] = {}

    def exist(self, data_path: str) -> bool:
        """
        Check if data file exists in data directory.
        
        Args:
            data_path: Path to data file relative to data/ (e.g., "output.txt" or "./output.txt")
        
        Returns:
            bool: True if file exists, False otherwise
        """
        try:
            file_path = self._find_data_path(data_path, create_if_missing=False)
            return file_path.exists()
        except FileNotFoundError:
            return False

    def get(self, data_path: str) -> str:
        """
        Get data content as text from data directory in caller's location.
        
        Args:
            data_path: Path to data file relative to data/ (e.g., "output.txt" or "./output.txt")
        
        Returns:
            str: Data content as text
            
        Raises:
            FileNotFoundError: If data file not found
        """
        file_path = self._find_data_path(data_path)
        return file_path.read_text(encoding="utf-8")

    def get_json(self, data_path: str) -> Any:
        """
        Get data content as JSON from data directory in caller's location.
        
        Args:
            data_path: Path to data file relative to data/ (e.g., "products.json" or "./products.json")
        
        Returns:
            Any: Data content as JSON (dict, list, etc.)
            
        Raises:
            FileNotFoundError: If data file not found
            json.JSONDecodeError: If file is not valid JSON
        """
        file_path = self._find_data_path(data_path)
        file_helper = FileHelper()
        return file_helper.read_json_file(file_path)

    def get_binary(self, data_path: str) -> bytes:
        """
        Get data content as binary from data directory in caller's location.
        
        Args:
            data_path: Path to data file relative to data/ (e.g., "image.png" or "./image.png")
        
        Returns:
            bytes: Data content as binary data
            
        Raises:
            FileNotFoundError: If data file not found
        """
        file_path = self._find_data_path(data_path)
        return file_path.read_bytes()

    def get_enc_binary(self, enc_path: str, key: str | None = None) -> bytes:
        """
        Read and decrypt an OpenSSL .enc file from data directory.

        It automatically searches under ./data/<path>. If not found, it will
        also try ./data/enc/<path>.

        Decryption uses OpenSSL AES-256-CBC with salt and PBKDF2 to match the
        repository's encryption tool. The key is taken from the provided
        argument or the environment variable LOCAL_ENCRYPTION_KEY.

        Args:
            enc_path: Path to .enc file relative to data/ (e.g., "foo.bin.enc" or "enc/foo.bin.enc")
            key: Decryption key. If None, uses $LOCAL_ENCRYPTION_KEY

        Returns:
            bytes: Decrypted binary content

        Raises:
            FileNotFoundError: If encrypted file not found
            RuntimeError: If decryption key is missing or decryption fails
        """
        file_path = self._find_data_path_with_enc_fallback(enc_path)
        decryption_key = self._get_encryption_key(key)

        with tempfile.NamedTemporaryFile(delete=False) as tmp_out:
            tmp_out_path = Path(tmp_out.name)

        try:
            # Try modern settings first: PBKDF2 + AES-256-CBC
            self._run_openssl_dec(
                input_path=file_path,
                output_path=tmp_out_path,
                key=decryption_key,
                use_pbkdf2=True,
                legacy_md=None,
            )
            return tmp_out_path.read_bytes()
        except subprocess.CalledProcessError as e1:
            # Fallback to legacy EVP_BytesToKey (no -pbkdf2), default md is md5
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
                stderr1 = getattr(e1, "stderr", None)
                stderr2 = getattr(e2, "stderr", None)
                details = []
                if stderr1:
                    details.append(f"pbkdf2 stderr: {stderr1.strip()}")
                if stderr2:
                    details.append(f"legacy stderr: {stderr2.strip()}")
                msg = "Failed to decrypt .enc file with both PBKDF2 and legacy modes"
                if details:
                    msg += f". Details: {' | '.join(details)}"
                raise RuntimeError(msg) from e2
        finally:
            try:
                if tmp_out_path.exists():
                    tmp_out_path.unlink()
            except Exception:
                pass

    def get_enc_text(self, enc_path: str, key: str | None = None, encoding: str = "utf-8") -> str:
        """
        Read and decrypt a .enc file and return text using provided encoding.

        Args:
            enc_path: Path to .enc file relative to data/
            key: Decryption key or None to use $LOCAL_ENCRYPTION_KEY
            encoding: Text encoding for decoded bytes

        Returns:
            str: Decrypted text content
        """
        data = self.get_enc_binary(enc_path, key)
        return data.decode(encoding)

    def get_enc_json(self, enc_path: str, key: str | None = None, encoding: str = "utf-8") -> Any:
        """
        Read and decrypt a .enc JSON file, returning Python object.

        Supports both standard JSON and NDJSON (newline-delimited JSON). If the
        content parses as a single JSON value, returns that value. If not, it
        attempts to parse each non-empty line as a JSON object and returns a list
        of parsed items.

        Args:
            enc_path: Path to .enc file relative to data/
            key: Decryption key or None to use $LOCAL_ENCRYPTION_KEY
            encoding: Text encoding for decoded bytes

        Returns:
            Any: Parsed JSON value or list for NDJSON
        """
        text = self.get_enc_text(enc_path, key=key, encoding=encoding)
        # Strip UTF-8 BOM if present
        text = text.lstrip("\ufeff")
        import json as _json
        try:
            return _json.loads(text)
        except _json.JSONDecodeError:
            # Try NDJSON fallback
            items: list[Any] = []
            for line in text.splitlines():
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                try:
                    items.append(_json.loads(line_stripped))
                except Exception:
                    continue
            if items:
                return items
            # Try split by boundary between JSON objects like '}{'
            parts = re.split(r"(?<=\})\s*(?=\{)", text)
            chunks: list[Any] = []
            for part in parts:
                s = part.strip()
                if not s:
                    continue
                if not s.startswith("{"):
                    continue
                if not s.endswith("}"):
                    continue
                try:
                    chunks.append(_json.loads(s))
                except Exception:
                    continue
            if chunks:
                return chunks
            # If all strategies fail, raise original error
            raise

    def write(self, data_path: str, content: str) -> None:
        """
        Write text content to data file in caller's location.
        
        Args:
            data_path: Path to data file relative to data/ (e.g., "output.txt" or "./output.txt")
            content: Text content to write
            
        Raises:
            OSError: If file cannot be written
        """
        file_path = self._find_data_path(data_path, create_if_missing=True)
        file_path.write_text(content, encoding="utf-8")

    def write_json(self, data_path: str, data: Any) -> None:
        """
        Write JSON content to data file in caller's location.
        
        Args:
            data_path: Path to data file relative to data/ (e.g., "products.json" or "./products.json")
            data: Data to write (must be JSON serializable)
            
        Raises:
            OSError: If file cannot be written
        """
        file_path = self._find_data_path(data_path, create_if_missing=True)
        file_helper = FileHelper()
        file_helper.write_json_file(file_path, data)

    def write_binary(self, data_path: str, content: bytes) -> None:
        """
        Write binary content to data file in caller's location.
        
        Args:
            data_path: Path to data file relative to data/ (e.g., "image.png" or "./image.png")
            content: Binary content to write
            
        Raises:
            OSError: If file cannot be written
        """
        file_path = self._find_data_path(data_path, create_if_missing=True)
        file_path.write_bytes(content)

    def get_from_subworkflow(self, data_path: str) -> str:
        """
        Get data content as text from sub_workflow's data directory.
        
        Args:
            data_path: Path to data file relative to sub_workflow/data/ (e.g., "output.txt")
        
        Returns:
            str: Data content as text
            
        Raises:
            FileNotFoundError: If subworkflow data file not found
        """
        file_path = self._find_subworkflow_data_path(data_path)
        return file_path.read_text(encoding="utf-8")

    def get_json_from_subworkflow(self, data_path: str) -> Any:
        """
        Get data content as JSON from sub_workflow's data directory.
        
        Args:
            data_path: Path to data file relative to sub_workflow/data/ (e.g., "products.json")
        
        Returns:
            Any: Data content as JSON (dict, list, etc.)
            
        Raises:
            FileNotFoundError: If subworkflow data file not found
            json.JSONDecodeError: If file is not valid JSON
        """
        file_path = self._find_subworkflow_data_path(data_path)
        file_helper = FileHelper()
        return file_helper.read_json_file(file_path)

    def get_binary_from_subworkflow(self, data_path: str) -> bytes:
        """
        Get data content as binary from sub_workflow's data directory.
        
        Args:
            data_path: Path to data file relative to sub_workflow/data/ (e.g., "image.png")
        
        Returns:
            bytes: Data content as binary data
            
        Raises:
            FileNotFoundError: If subworkflow data file not found
        """
        file_path = self._find_subworkflow_data_path(data_path)
        return file_path.read_bytes()

    def list_data(self) -> list[str]:
        """
        List all data files in data directory recursively.
        
        Returns:
            list[str]: List of data file paths (relative to data/)
        """
        finder = _DataPathFinder()
        caller_path = finder.find_caller_dir()
        data_dir = caller_path / "data"
        
        if not data_dir.exists():
            return []
        
        files = []
        for file_path in data_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(data_dir)
                files.append(str(relative_path))
        
        return sorted(files)

    def list_subworkflow_data(self) -> list[str]:
        """
        List all data files in sub_workflow's data directory recursively.
        
        Returns:
            list[str]: List of data file paths (relative to data/)
        """
        finder = _DataPathFinder()
        caller_path = finder.find_caller_dir()
        subworkflow_data_dir = caller_path / "sub_workflow" / "data"
        
        if not subworkflow_data_dir.exists():
            return []
        
        files = []
        for file_path in subworkflow_data_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(subworkflow_data_dir)
                files.append(str(relative_path))
        
        return sorted(files)

    def _find_data_path(self, data_path: str, create_if_missing: bool = False) -> Path:
        """
        Find data file path from the caller's file location.
        
        Args:
            data_path: Path to data file relative to data/
            create_if_missing: If True, create parent directories if they don't exist
        
        Returns:
            Path: Path to data file
            
        Raises:
            FileNotFoundError: If data file not found and create_if_missing is False
        """
        finder = _DataPathFinder()
        caller_path = finder.find_caller_dir()
        
        # Normalize data path (remove ./ if present)
        normalized_path = data_path.lstrip("./")
        
        data_file = caller_path / "data" / normalized_path
        if create_if_missing:
            data_file.parent.mkdir(parents=True, exist_ok=True)
            return data_file.resolve()
        
        if data_file.exists():
            return data_file.resolve()
        
        raise FileNotFoundError(
            f"Data file not found: {data_path}. "
            f"Expected: {data_file}"
        )

    def _find_subworkflow_data_path(self, data_path: str) -> Path:
        """
        Find data file path in sub_workflow's data directory.
        
        Args:
            data_path: Path to data file relative to sub_workflow/data/
        
        Returns:
            Path: Path to data file
            
        Raises:
            FileNotFoundError: If subworkflow data file not found
        """
        finder = _DataPathFinder()
        caller_path = finder.find_caller_dir()
        
        # Normalize data path (remove ./ if present)
        normalized_path = data_path.lstrip("./")
        
        subworkflow_data_file = caller_path / "sub_workflow" / "data" / normalized_path
        
        if subworkflow_data_file.exists():
            return subworkflow_data_file.resolve()
        
        raise FileNotFoundError(
            f"Subworkflow data file not found: sub_workflow/{data_path}. "
            f"Expected: {subworkflow_data_file}"
        )

    def _find_data_path_with_enc_fallback(self, data_path: str) -> Path:
        """
        Find an encrypted data file path trying both ./data/<path> and ./data/enc/<path>.

        Args:
            data_path: Path to file relative to data/

        Returns:
            Path: Resolved path to the encrypted file

        Raises:
            FileNotFoundError: If not found in either location
        """
        try:
            return self._find_data_path(data_path, create_if_missing=False)
        except FileNotFoundError:
            normalized_path = data_path.lstrip("./")
            if not normalized_path.startswith("enc/"):
                try_path = f"enc/{normalized_path}"
                return self._find_data_path(try_path, create_if_missing=False)
            raise

    def _get_encryption_key(self, provided_key: str | None) -> str:
        """
        Resolve encryption/decryption key from argument or environment.

        Prefers the provided key; otherwise uses $LOCAL_ENCRYPTION_KEY.
        """
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


class _DataPathFinder:
    """
    Helper class for finding caller's directory location.
    """

    def find_caller_dir(self) -> Path:
        """
        Find caller's directory from the call stack.
        If caller is in services/ directory, returns parent directory (workflow/subworkflow).
        
        Returns:
            Path: Path to workflow/subworkflow directory (not services/)
            
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
                
                caller_dir = Path(frame_file).parent
                # If caller is in services/ directory, return parent directory
                if caller_dir.name == "services":
                    return caller_dir.parent
                return caller_dir
        finally:
            del frame
        
        raise FileNotFoundError("Could not determine caller file location to find data")

    def _is_valid_caller_frame(self, frame_module: str, frame_file: str | None) -> bool:
        if not frame_module or not frame_file:
            return False
        return 'data_helper' not in frame_module.lower()

