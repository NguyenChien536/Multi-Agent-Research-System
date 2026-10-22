import hashlib
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional
import uuid

from app.core.config import settings


def sanitize_filename(filename: str) -> str:
    """Loại bỏ ký tự không an toàn và chống path traversal attack."""
    # Lấy base name loại bỏ path separator
    base = os.path.basename(filename).strip()
    # Loại bỏ các ký tự đặc biệt nguy hiểm, giữ lại chữ cái, số, dấu gạch nối, gạch dưới và chấm
    safe = re.sub(r"[^\w\.\-\_]", "_", base)
    if not safe or safe.startswith("."):
        safe = f"artifact_{uuid.uuid4().hex[:8]}.pdf"
    return safe


class ArtifactStore:
    """Quản lý lưu trữ tệp tin riêng tư cục bộ (Private Local Storage) theo task_id."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.ARTIFACTS_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_task_dir(self, task_id: uuid.UUID) -> Path:
        task_dir = (self.base_dir / str(task_id)).resolve()
        # Đảm bảo không thoát khỏi base_dir
        if task_dir == self.base_dir or self.base_dir not in task_dir.parents:
            raise ValueError("Invalid task ID path traversal attempt")
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def save_artifact(
        self,
        task_id: uuid.UUID,
        filename: str,
        content: bytes,
    ) -> Dict[str, Any]:
        """Lưu tệp tin vào thư mục riêng của task và tính mã băm SHA-256."""
        safe_name = sanitize_filename(filename)
        task_dir = self._get_task_dir(task_id)
        sha256_hash = hashlib.sha256(content).hexdigest()

        # Create atomically so concurrent uploads/retries cannot overwrite
        # bytes referenced by an older artifact row.
        source_name = Path(safe_name)
        while True:
            target_path = (task_dir / safe_name).resolve()
            if target_path == task_dir or task_dir not in target_path.parents:
                raise ValueError("Invalid filename path traversal attempt")
            try:
                with target_path.open("xb") as target_file:
                    target_file.write(content)
                break
            except FileExistsError:
                safe_name = f"{source_name.stem}_{uuid.uuid4().hex[:12]}{source_name.suffix}"
            except Exception:
                target_path.unlink(missing_ok=True)
                raise

        relative_path = f"{task_id}/{safe_name}"

        return {
            "file_name": safe_name,
            "file_path": relative_path,
            "absolute_path": str(target_path),
            "file_size_bytes": len(content),
            "sha256_hash": sha256_hash,
        }

    def get_artifact_path(self, task_id: uuid.UUID, filename_or_path: str) -> Optional[Path]:
        """Lấy đường dẫn an toàn của file và kiểm tra tồn tại."""
        safe_name = sanitize_filename(filename_or_path)
        task_dir = self._get_task_dir(task_id)
        target_path = (task_dir / safe_name).resolve()

        if target_path == task_dir or task_dir not in target_path.parents:
            raise ValueError("Path traversal attempt detected")

        if target_path.is_file():
            return target_path
        return None

    def delete_artifact(self, task_id: uuid.UUID, filename: str) -> bool:
        """Xóa một tệp tin của task."""
        file_path = self.get_artifact_path(task_id, filename)
        if file_path and file_path.is_file():
            file_path.unlink()
            return True
        return False

    def delete_task_artifacts(self, task_id: uuid.UUID) -> int:
        """Xóa toàn bộ artifacts của một task khi xóa task (Tombstone cleanup)."""
        import shutil
        task_dir = (self.base_dir / str(task_id)).resolve()
        if task_dir == self.base_dir or self.base_dir not in task_dir.parents:
            return 0
        if task_dir.is_dir():
            count = len(list(task_dir.glob("*")))
            shutil.rmtree(task_dir, ignore_errors=True)
            return count
        return 0


# Singleton instance
artifact_store = ArtifactStore()
