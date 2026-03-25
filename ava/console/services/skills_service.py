"""Skills and tools management service."""

from __future__ import annotations

import importlib
import inspect
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger


class SkillsService:
    """Service for managing skills and tools."""

    def __init__(self, workspace: Path, builtin_skills_dir: Path, nanobot_dir: Path):
        self.workspace = workspace
        self.builtin_skills_dir = builtin_skills_dir
        self.nanobot_dir = nanobot_dir
        self.workspace_skills_dir = workspace / "skills"
        self.tools_dir = Path(__file__).parent.parent.parent / "agent" / "tools"

    # ─── Tools ──────────────────────────────────────────────────────────────────

    def list_tools(self) -> list[dict[str, Any]]:
        """List all built-in tools with their metadata."""
        tools = []
        
        # Tool files to scan (excluding base.py, registry.py, __init__.py)
        tool_files = [
            f for f in self.tools_dir.glob("*.py")
            if f.name not in ("__init__.py", "base.py", "registry.py")
        ]
        
        for tool_file in sorted(tool_files):
            tool_info = self._extract_tool_info(tool_file)
            if tool_info:
                tools.extend(tool_info)
        
        return tools

    def _extract_tool_info(self, tool_file: Path) -> list[dict[str, Any]]:
        """Extract tool information from a tool file."""
        tools = []
        content = tool_file.read_text(encoding="utf-8")
        
        # Find all Tool classes
        class_pattern = re.compile(
            r'class\s+(\w+)\(Tool\):\s*"""([^"]+)"""',
            re.MULTILINE
        )
        
        for match in class_pattern.finditer(content):
            class_name = match.group(1)
            description = match.group(2).strip()
            
            # Try to find the name property
            name = self._extract_property_value(content, class_name, "name")
            if not name:
                # Derive name from class name (e.g., ReadFileTool -> read_file)
                name = re.sub(r'Tool$', '', class_name)
                name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
            
            tools.append({
                "name": name,
                "class": class_name,
                "description": description,
                "file": tool_file.name,
            })
        
        return tools

    def _extract_property_value(self, content: str, class_name: str, prop_name: str) -> str | None:
        """Extract a property value from class definition."""
        # Look for class-level attribute: name = "xxx"
        pattern = rf'class\s+{class_name}.*?(?=class\s+\w+|$)'
        class_match = re.search(pattern, content, re.DOTALL)
        if class_match:
            class_content = class_match.group(0)
            prop_pattern = rf'{prop_name}\s*=\s*["\']([^"\']+)["\']'
            prop_match = re.search(prop_pattern, class_content)
            if prop_match:
                return prop_match.group(1)
        return None

    # ─── Skills ─────────────────────────────────────────────────────────────────

    def list_skills(self) -> list[dict[str, Any]]:
        """List all skills (builtin + workspace)."""
        skills = []
        
        # Workspace skills (highest priority)
        if self.workspace_skills_dir.exists():
            for skill_dir in sorted(self.workspace_skills_dir.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        meta = self._parse_skill_metadata(skill_file)
                        skills.append({
                            "name": skill_dir.name,
                            "source": "workspace",
                            "path": str(skill_file),
                            "enabled": True,  # Workspace skills are always enabled
                            **meta,
                        })
        
        # Built-in skills
        if self.builtin_skills_dir.exists():
            for skill_dir in sorted(self.builtin_skills_dir.iterdir()):
                if skill_dir.is_dir() and skill_dir.name != "__pycache__":
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        # Skip if already in workspace
                        if any(s["name"] == skill_dir.name for s in skills):
                            continue
                        meta = self._parse_skill_metadata(skill_file)
                        skills.append({
                            "name": skill_dir.name,
                            "source": "builtin",
                            "path": str(skill_file),
                            "enabled": True,
                            **meta,
                        })
        
        return skills

    def _parse_skill_metadata(self, skill_file: Path) -> dict[str, Any]:
        """Parse skill metadata from SKILL.md frontmatter."""
        content = skill_file.read_text(encoding="utf-8")
        meta = {"description": "", "always": False}
        
        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        if key == "description":
                            meta["description"] = value
                        elif key == "always":
                            meta["always"] = value.lower() == "true"
                        elif key == "name":
                            pass  # We use directory name
        
        return meta

    def get_skill(self, name: str) -> dict[str, Any] | None:
        """Get a single skill by name."""
        for skill in self.list_skills():
            if skill["name"] == name:
                return skill
        return None

    def install_skill_from_git(self, git_url: str, name: str | None = None) -> dict[str, Any]:
        """Install a skill from a Git repository."""
        self.workspace_skills_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract skill name from URL if not provided
        if not name:
            name = git_url.rstrip("/").split("/")[-1]
            if name.endswith(".git"):
                name = name[:-4]
        
        target_dir = self.workspace_skills_dir / name
        
        if target_dir.exists():
            raise ValueError(f"Skill '{name}' already exists")
        
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", git_url, str(target_dir)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Git clone failed: {result.stderr}")
            
            # Remove .git directory
            git_dir = target_dir / ".git"
            if git_dir.exists():
                shutil.rmtree(git_dir)
            
            # Verify SKILL.md exists
            skill_file = target_dir / "SKILL.md"
            if not skill_file.exists():
                shutil.rmtree(target_dir)
                raise ValueError(f"No SKILL.md found in repository")
            
            return {"ok": True, "name": name, "path": str(target_dir)}
        except subprocess.TimeoutExpired:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            raise RuntimeError("Git clone timed out")
        except Exception as e:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            raise

    def install_skill_from_path(self, source_path: str, name: str | None = None) -> dict[str, Any]:
        """Install a skill by copying from a local path."""
        source = Path(source_path).expanduser().resolve()
        
        if not source.exists():
            raise FileNotFoundError(f"Source path does not exist: {source}")
        
        if not source.is_dir():
            raise ValueError(f"Source must be a directory: {source}")
        
        skill_file = source / "SKILL.md"
        if not skill_file.exists():
            raise ValueError(f"No SKILL.md found in {source}")
        
        if not name:
            name = source.name
        
        self.workspace_skills_dir.mkdir(parents=True, exist_ok=True)
        target_dir = self.workspace_skills_dir / name
        
        if target_dir.exists():
            raise ValueError(f"Skill '{name}' already exists")
        
        shutil.copytree(source, target_dir)
        return {"ok": True, "name": name, "path": str(target_dir)}

    def delete_skill(self, name: str) -> dict[str, Any]:
        """Delete a workspace skill."""
        skill_dir = self.workspace_skills_dir / name
        
        if not skill_dir.exists():
            raise FileNotFoundError(f"Skill '{name}' not found")
        
        # Only allow deleting workspace skills
        if not str(skill_dir).startswith(str(self.workspace_skills_dir)):
            raise PermissionError("Cannot delete built-in skills")
        
        shutil.rmtree(skill_dir)
        return {"ok": True, "name": name}
