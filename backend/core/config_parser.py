"""
backend/core/config_parser.py

配置解析器：解析 application.yml、.properties、pom.xml，产出结构化 ConfigEntry。
"""

import os
import re
import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConfigEntry:
    """配置项数据模型。"""
    entry_id: str
    source_id: str
    file_path: str
    config_type: str       # yaml, properties, pom_dependency
    key_path: str          # e.g. spring.datasource.url
    value: str
    comment: str = ""
    profile: str = ""      # e.g. dev, prod (from filename)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConfigParser:
    """解析配置文件，产出 ConfigEntry 列表。"""

    def __init__(self, source_id: str):
        self.source_id = source_id

    def parse_file(self, abs_path: str, rel_path: str) -> List[ConfigEntry]:
        """根据文件扩展名分发到对应解析方法。"""
        ext = os.path.splitext(abs_path)[1].lower()
        basename = os.path.basename(abs_path).lower()

        try:
            if ext in (".yml", ".yaml"):
                return self.parse_yaml(abs_path, rel_path)
            elif ext == ".properties":
                return self.parse_properties(abs_path, rel_path)
            elif basename == "pom.xml":
                return self.parse_pom_xml(abs_path, rel_path)
            else:
                return []
        except Exception as e:
            logger.error(f"Error parsing config {rel_path}: {e}")
            return []

    # ------------------------------------------------------------------
    # YAML 解析
    # ------------------------------------------------------------------

    def parse_yaml(self, abs_path: str, rel_path: str) -> List[ConfigEntry]:
        """解析 .yml/.yaml 文件，递归扁平化键路径。"""
        try:
            import yaml
        except ImportError:
            logger.error("pyyaml not installed. Run: uv pip install pyyaml")
            return []

        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Extract profile from filename (e.g., application-dev.yml -> dev)
        profile = self._extract_profile(rel_path)

        entries = []
        try:
            docs = list(yaml.safe_load_all(content))
        except yaml.YAMLError as e:
            logger.warning(f"YAML parse error in {rel_path}: {e}")
            return []

        for doc in docs:
            if not isinstance(doc, dict):
                continue
            flat = self._flatten_dict(doc)
            for key_path, value in flat.items():
                entries.append(ConfigEntry(
                    entry_id=self._gen_id(),
                    source_id=self.source_id,
                    file_path=rel_path,
                    config_type="yaml",
                    key_path=key_path,
                    value=str(value) if value is not None else "",
                    profile=profile,
                ))

        return entries

    # ------------------------------------------------------------------
    # Properties 解析
    # ------------------------------------------------------------------

    def parse_properties(self, abs_path: str, rel_path: str) -> List[ConfigEntry]:
        """逐行解析 .properties 文件。"""
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        profile = self._extract_profile(rel_path)
        entries = []
        comment_buffer = ""

        for line in lines:
            stripped = line.strip()

            # Comment line
            if stripped.startswith("#") or stripped.startswith("!"):
                comment_buffer = stripped.lstrip("#!").strip()
                continue

            # Skip blank lines
            if not stripped:
                comment_buffer = ""
                continue

            # Key=Value (supports = and : as separator)
            match = re.match(r'^([^=:]+)[=:](.*)$', stripped)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                entries.append(ConfigEntry(
                    entry_id=self._gen_id(),
                    source_id=self.source_id,
                    file_path=rel_path,
                    config_type="properties",
                    key_path=key,
                    value=value,
                    comment=comment_buffer,
                    profile=profile,
                ))
                comment_buffer = ""

        return entries

    # ------------------------------------------------------------------
    # pom.xml 解析
    # ------------------------------------------------------------------

    def parse_pom_xml(self, abs_path: str, rel_path: str) -> List[ConfigEntry]:
        """解析 pom.xml，提取 dependencies 中的 groupId/artifactId/version。"""
        try:
            from lxml import etree
        except ImportError:
            logger.error("lxml not installed. Run: uv pip install lxml")
            return []

        try:
            tree = etree.parse(abs_path)
            root = tree.getroot()
        except Exception as e:
            logger.warning(f"Failed to parse pom.xml {rel_path}: {e}")
            return []

        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        entries = []

        for dep in root.findall(".//m:dependencies/m:dependency", ns):
            group_id = dep.findtext("m:groupId", default="", namespaces=ns)
            artifact_id = dep.findtext("m:artifactId", default="", namespaces=ns)
            version = dep.findtext("m:version", default="", namespaces=ns)
            scope = dep.findtext("m:scope", default="", namespaces=ns)

            if artifact_id:
                key_path = f"dependency.{group_id}.{artifact_id}"
                value = version or "managed"
                entries.append(ConfigEntry(
                    entry_id=self._gen_id(),
                    source_id=self.source_id,
                    file_path=rel_path,
                    config_type="pom_dependency",
                    key_path=key_path,
                    value=value,
                    metadata={"group_id": group_id, "artifact_id": artifact_id,
                              "version": version, "scope": scope},
                ))

        return entries

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _flatten_dict(self, d: dict, parent_key: str = "") -> Dict[str, Any]:
        """递归扁平化字典，键用 . 连接。"""
        items = {}
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else str(k)
            if isinstance(v, dict):
                items.update(self._flatten_dict(v, new_key))
            elif isinstance(v, list):
                # Store list as JSON-like string
                items[new_key] = str(v)
            else:
                items[new_key] = v
        return items

    def _extract_profile(self, rel_path: str) -> str:
        """从文件名提取 profile（如 application-dev.yml -> dev）。"""
        basename = os.path.splitext(os.path.basename(rel_path))[0]
        match = re.match(r'application-(.+)', basename)
        if match:
            return match.group(1)
        return ""

    def _gen_id(self) -> str:
        return str(uuid.uuid4())
