"""Media service: manage image generation records and files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ava.console.models import MediaRecord


class MediaService:
    def __init__(self, media_dir: Path | None = None, db: Any | None = None):
        self._media_dir = media_dir or (Path.home() / ".nanobot" / "media" / "generated")
        self._records_file = self._media_dir / "records.jsonl"
        self._db = db

    @property
    def _use_db(self) -> bool:
        return self._db is not None

    def write_record(self, record: dict) -> None:
        """Write a media generation record (called from ImageGenTool)."""
        if self._use_db:
            self._db.execute(
                """INSERT OR REPLACE INTO media_records
                   (id, timestamp, prompt, reference_image, output_images, output_text, model, status, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.get("id", ""),
                    record.get("timestamp", ""),
                    record.get("prompt", ""),
                    record.get("reference_image"),
                    json.dumps(record.get("output_images", []), ensure_ascii=False),
                    record.get("output_text", ""),
                    record.get("model", ""),
                    record.get("status", "success"),
                    record.get("error"),
                ),
            )
            self._db.commit()
            return

        try:
            self._media_dir.mkdir(parents=True, exist_ok=True)
            with open(self._records_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def query(
        self,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> dict[str, Any]:
        if self._use_db:
            return self._query_db(page, size, search)
        return self._query_jsonl(page, size, search)

    def _query_db(self, page: int, size: int, search: str | None) -> dict[str, Any]:
        if search:
            total_row = self._db.fetchone(
                "SELECT COUNT(*) as cnt FROM media_records WHERE prompt LIKE ?",
                (f"%{search}%",),
            )
            total = total_row["cnt"] if total_row else 0
            offset = (page - 1) * size
            rows = self._db.fetchall(
                """SELECT * FROM media_records WHERE prompt LIKE ?
                   ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
                (f"%{search}%", size, offset),
            )
        else:
            total_row = self._db.fetchone("SELECT COUNT(*) as cnt FROM media_records")
            total = total_row["cnt"] if total_row else 0
            offset = (page - 1) * size
            rows = self._db.fetchall(
                "SELECT * FROM media_records ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (size, offset),
            )

        records = []
        for r in rows:
            output_images = []
            if r["output_images"]:
                try:
                    output_images = json.loads(r["output_images"])
                except json.JSONDecodeError:
                    pass
            records.append(MediaRecord(
                id=r["id"],
                timestamp=r["timestamp"],
                prompt=r["prompt"],
                reference_image=r["reference_image"],
                output_images=output_images,
                output_text=r["output_text"] or "",
                model=r["model"] or "",
                status=r["status"] or "success",
                error=r["error"],
            ).model_dump())

        return {"records": records, "total": total, "page": page, "size": size}

    def _query_jsonl(self, page: int, size: int, search: str | None) -> dict[str, Any]:
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
        if "/" in filename or "\\" in filename or ".." in filename:
            return None
        path = self._media_dir / filename
        if path.is_file():
            return path
        return None

    def delete_record(self, record_id: str) -> bool:
        """Delete a media record and its associated image files.
        
        Returns True if deleted, raises ValueError if not found.
        """
        # Get record to find image paths
        if self._use_db:
            row = self._db.fetchone(
                "SELECT output_images FROM media_records WHERE id = ?",
                (record_id,),
            )
            if not row:
                raise ValueError(f"Record {record_id} not found")
            
            # Parse and delete image files
            output_images = []
            if row["output_images"]:
                try:
                    output_images = json.loads(row["output_images"])
                except json.JSONDecodeError:
                    pass
            
            for img_path in output_images:
                filename = img_path.split("/")[-1] if "/" in img_path else img_path
                full_path = self._media_dir / filename
                if full_path.is_file():
                    try:
                        full_path.unlink()
                    except Exception:
                        pass  # Best effort deletion
            
            # Delete database record
            self._db.execute("DELETE FROM media_records WHERE id = ?", (record_id,))
            self._db.commit()
            return True
        
        # JSONL mode: rewrite file without the record
        if not self._records_file.exists():
            raise ValueError(f"Record {record_id} not found")
        
        lines = self._records_file.read_text("utf-8").splitlines()
        new_lines = []
        found = False
        deleted_images = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("id") == record_id:
                    found = True
                    deleted_images = record.get("output_images", [])
                    continue
                new_lines.append(line)
            except json.JSONDecodeError:
                new_lines.append(line)
        
        if not found:
            raise ValueError(f"Record {record_id} not found")
        
        # Delete image files
        for img_path in deleted_images:
            filename = img_path.split("/")[-1] if "/" in img_path else img_path
            full_path = self._media_dir / filename
            if full_path.is_file():
                try:
                    full_path.unlink()
                except Exception:
                    pass
        
        # Rewrite records file
        self._records_file.write_text("\n".join(new_lines) + "\n" if new_lines else "", "utf-8")
        return True
