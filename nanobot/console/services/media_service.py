"""Media service: manage image generation records and files."""

from __future__ import annotations

import json
from pathlib import Path

from nanobot.console.models import MediaRecord


class MediaService:
    def __init__(self, media_dir: Path | None = None):
        self._media_dir = media_dir or (Path.home() / ".nanobot" / "media" / "generated")
        self._records_file = self._media_dir / "records.jsonl"

    def query(
        self,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> dict:
        if not self._records_file.exists():
            return {"records": [], "total": 0, "page": page, "size": size}

        all_records: list[MediaRecord] = []
        for line in self._records_file.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = MediaRecord.model_validate_json(line)
                if search and search.lower() not in record.prompt.lower():
                    continue
                all_records.append(record)
            except Exception:
                continue

        all_records.reverse()

        total = len(all_records)
        start = (page - 1) * size
        end = start + size
        page_records = all_records[start:end]

        return {
            "records": [r.model_dump() for r in page_records],
            "total": total,
            "page": page,
            "size": size,
        }

    def get_image_path(self, filename: str) -> Path | None:
        """Get the full path for an image file, returning None if not found."""
        if "/" in filename or "\\" in filename or ".." in filename:
            return None
        path = self._media_dir / filename
        if path.is_file():
            return path
        return None
