"""
backend/core/code_parser.py

代码解析器：解析 Java/hbs/jQuery/XML 文件，产出 CodeChunk 对象及跨层关联数据。
"""

import os
import re
import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CodeChunk:
    """代码片段数据模型。"""
    chunk_id: str
    source_id: str
    file_path: str
    chunk_type: str        # class, method, field, file, xml_mapper, xml_statement, etc.
    language: str           # java, javascript, handlebars, xml
    name: str
    qualified_name: str
    content: str
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    line_start: int = 0
    line_end: int = 0


class CodeParser:
    """解析 Java/hbs/jQuery/XML 文件。"""

    def __init__(self, source_id: str):
        self.source_id = source_id
        self.max_lines = settings.CODE_CHUNK_MAX_LINES

    def parse_file(self, abs_path: str, rel_path: str) -> List[CodeChunk]:
        """根据文件扩展名分发到对应解析方法。"""
        ext = os.path.splitext(abs_path)[1].lower()

        try:
            if ext == ".java":
                return self.parse_java_file(abs_path, rel_path)
            elif ext == ".xml":
                return self.parse_xml_file(abs_path, rel_path)
            elif ext == ".hbs":
                return self.parse_hbs_file(abs_path, rel_path)
            elif ext == ".js":
                return self.parse_jquery_js(abs_path, rel_path)
            elif ext in (".yml", ".yaml", ".properties"):
                return self.parse_config_file(abs_path, rel_path)
            else:
                return []
        except Exception as e:
            logger.error(f"Error parsing {rel_path}: {e}")
            return []

    # ------------------------------------------------------------------
    # Java 解析
    # ------------------------------------------------------------------

    def parse_java_file(self, abs_path: str, rel_path: str) -> List[CodeChunk]:
        """使用 javalang AST 解析 Java 文件。"""
        try:
            import javalang
        except ImportError:
            logger.error("javalang not installed. Run: uv pip install javalang")
            return []

        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()

        lines = source.splitlines()
        chunks: List[CodeChunk] = []
        cross_refs: List[Dict] = []

        try:
            tree = javalang.parse.parse(source)
        except javalang.parser.JavaSyntaxError as e:
            logger.warning(f"Java syntax error in {rel_path}: {e}")
            # 降级：作为整个文件的一个 chunk
            return [self._file_level_chunk(source, rel_path, "java")]
        except Exception as e:
            logger.warning(f"Failed to parse Java AST for {rel_path}: {e}")
            return [self._file_level_chunk(source, rel_path, "java")]

        # 提取 package
        package_name = tree.package.name if tree.package else ""

        # 提取类级注解中的 @RequestMapping 前缀
        class_request_mapping = ""

        for path, node in tree.filter(javalang.tree.ClassDeclaration):
            class_name = node.name
            qualified_class = f"{package_name}.{class_name}" if package_name else class_name

            # 类级注解
            annotations = self._extract_annotations(node)
            class_request_mapping = self._get_request_mapping(annotations)

            # 检查继承和注解
            class_annotations_str = ", ".join(f"@{a['name']}" for a in annotations)
            extends = node.extends.name if node.extends else ""
            implements = [impl.name for impl in (node.implements or [])]

            class_line_start = node.position.line if node.position else 1
            class_line_end = min(class_line_start + self.max_lines, len(lines))
            class_content = "\n".join(lines[class_line_start - 1:class_line_end])

            class_summary = f"Class {class_name}"
            if class_annotations_str:
                class_summary += f" [{class_annotations_str}]"
            if extends:
                class_summary += f" extends {extends}"
            if implements:
                class_summary += f" implements {', '.join(implements)}"

            class_cross_refs = []

            # @TableName 注解 → queries_table
            for ann in annotations:
                if ann["name"] == "TableName" and ann.get("value"):
                    ref = self._make_cross_ref(
                        "class", qualified_class, class_name,
                        "table", ann["value"], "maps_to_entity",
                        f"@TableName(\"{ann['value']}\")"
                    )
                    class_cross_refs.append(ref)
                    cross_refs.append(ref)

            chunks.append(CodeChunk(
                chunk_id=self._gen_id(),
                source_id=self.source_id,
                file_path=rel_path,
                chunk_type="class",
                language="java",
                name=class_name,
                qualified_name=qualified_class,
                content=class_content,
                summary=class_summary,
                metadata={"annotations": annotations, "extends": extends,
                          "implements": implements, "cross_refs": class_cross_refs},
                line_start=class_line_start,
                line_end=class_line_end,
            ))

            # 提取方法
            for method in (node.methods or []):
                method_chunks, method_refs = self._parse_java_method(
                    method, qualified_class, class_request_mapping,
                    lines, rel_path
                )
                chunks.extend(method_chunks)
                cross_refs.extend(method_refs)

            # 提取字段
            for fld in (node.fields or []):
                field_chunks, field_refs = self._parse_java_field(
                    fld, qualified_class, lines, rel_path
                )
                chunks.extend(field_chunks)
                cross_refs.extend(field_refs)

        # 接口解析
        for path, node in tree.filter(javalang.tree.InterfaceDeclaration):
            iface_name = node.name
            qualified_iface = f"{package_name}.{iface_name}" if package_name else iface_name
            iface_line = node.position.line if node.position else 1
            iface_content = "\n".join(lines[iface_line - 1:min(iface_line + self.max_lines, len(lines))])

            chunks.append(CodeChunk(
                chunk_id=self._gen_id(),
                source_id=self.source_id,
                file_path=rel_path,
                chunk_type="interface",
                language="java",
                name=iface_name,
                qualified_name=qualified_iface,
                content=iface_content,
                summary=f"Interface {iface_name}",
                metadata={"cross_refs": []},
                line_start=iface_line,
                line_end=min(iface_line + self.max_lines, len(lines)),
            ))

        return chunks

    def _parse_java_method(
        self, method, qualified_class: str, class_mapping: str,
        lines: List[str], rel_path: str
    ) -> tuple:
        """解析 Java 方法，提取注解、Spring 路径映射、跨层引用。"""
        method_name = method.name
        qualified_method = f"{qualified_class}.{method_name}"

        annotations = self._extract_annotations(method)
        method_line = method.position.line if method.position else 1
        method_end = min(method_line + self.max_lines, len(lines))
        method_content = "\n".join(lines[method_line - 1:method_end])

        # Spring 路径映射
        api_path = self._get_api_path(annotations, class_mapping)
        http_method = self._get_http_method(annotations)

        summary_parts = [f"Method {method_name}"]
        if api_path:
            summary_parts.append(f"[{http_method} {api_path}]")

        method_refs = []

        # @Value("${key}") → reads_config
        for ann in annotations:
            if ann["name"] == "Value" and ann.get("value"):
                config_key = self._extract_config_key(ann["value"])
                if config_key:
                    ref = self._make_cross_ref(
                        "method", qualified_method, method_name,
                        "config", config_key, "reads_config",
                        f"@Value(\"${{{config_key}}}\")"
                    )
                    method_refs.append(ref)

        # 检查方法体中的 return "template" → renders_template
        template_refs = re.findall(r'return\s+"([a-zA-Z0-9_/\-]+)"', method_content)
        for tmpl in template_refs:
            if not tmpl.startswith("redirect:") and not tmpl.startswith("http"):
                ref = self._make_cross_ref(
                    "method", qualified_method, method_name,
                    "template", tmpl, "renders_template",
                    f"return \"{tmpl}\""
                )
                method_refs.append(ref)

        # 检查方法调用链（简单启发式：识别注入的 service 调用）
        service_calls = re.findall(r'(\w+Service)\.\w+\(', method_content)
        for svc in set(service_calls):
            ref = self._make_cross_ref(
                "method", qualified_method, method_name,
                "class", svc, "calls_method",
                f"calls {svc}"
            )
            method_refs.append(ref)

        metadata = {
            "annotations": annotations,
            "api_path": api_path,
            "http_method": http_method,
            "cross_refs": method_refs,
        }

        chunk = CodeChunk(
            chunk_id=self._gen_id(),
            source_id=self.source_id,
            file_path=rel_path,
            chunk_type="method",
            language="java",
            name=method_name,
            qualified_name=qualified_method,
            content=method_content,
            summary=" ".join(summary_parts),
            metadata=metadata,
            line_start=method_line,
            line_end=method_end,
        )
        return [chunk], method_refs

    def _parse_java_field(
        self, fld, qualified_class: str, lines: List[str], rel_path: str
    ) -> tuple:
        """解析 Java 字段，提取 @Value 等注解。"""
        chunks = []
        field_refs = []

        for declarator in fld.declarators:
            field_name = declarator.name
            qualified_field = f"{qualified_class}.{field_name}"
            field_line = fld.position.line if fld.position else 1

            annotations = self._extract_annotations(fld)
            field_content = lines[field_line - 1] if field_line <= len(lines) else ""

            # @Value 注解
            for ann in annotations:
                if ann["name"] == "Value" and ann.get("value"):
                    config_key = self._extract_config_key(ann["value"])
                    if config_key:
                        ref = self._make_cross_ref(
                            "field", qualified_field, field_name,
                            "config", config_key, "reads_config",
                            f"@Value(\"${{{config_key}}}\")"
                        )
                        field_refs.append(ref)

            chunks.append(CodeChunk(
                chunk_id=self._gen_id(),
                source_id=self.source_id,
                file_path=rel_path,
                chunk_type="field",
                language="java",
                name=field_name,
                qualified_name=qualified_field,
                content=field_content,
                summary=f"Field {field_name} in {qualified_class}",
                metadata={"annotations": annotations, "cross_refs": field_refs},
                line_start=field_line,
                line_end=field_line,
            ))

        return chunks, field_refs

    # ------------------------------------------------------------------
    # XML 解析
    # ------------------------------------------------------------------

    def parse_xml_file(self, abs_path: str, rel_path: str) -> List[CodeChunk]:
        """解析 XML 文件（MyBatis mapper、pom.xml）。"""
        from lxml import etree

        try:
            tree = etree.parse(abs_path)
            root = tree.getroot()
        except Exception as e:
            logger.warning(f"Failed to parse XML {rel_path}: {e}")
            return []

        chunks = []
        tag = etree.QName(root.tag).localname if '}' in root.tag else root.tag

        if tag == "mapper":
            chunks.extend(self._parse_mybatis_mapper(root, abs_path, rel_path))
        elif tag == "project":
            chunks.extend(self._parse_pom_xml(root, abs_path, rel_path))

        return chunks

    def _parse_mybatis_mapper(self, root, abs_path: str, rel_path: str) -> List[CodeChunk]:
        """解析 MyBatis mapper XML。"""
        from lxml import etree

        chunks = []
        namespace = root.get("namespace", "")

        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()

        # Mapper 文件级 chunk
        chunks.append(CodeChunk(
            chunk_id=self._gen_id(),
            source_id=self.source_id,
            file_path=rel_path,
            chunk_type="xml_mapper",
            language="xml",
            name=namespace.split(".")[-1] if namespace else os.path.basename(rel_path),
            qualified_name=namespace,
            content=source[:2000],
            summary=f"MyBatis Mapper: {namespace}",
            metadata={"namespace": namespace, "cross_refs": []},
            line_start=1,
            line_end=len(source.splitlines()),
        ))

        # 解析 select/insert/update/delete 语句
        for stmt_tag in ("select", "insert", "update", "delete"):
            for elem in root.iter(stmt_tag):
                stmt_id = elem.get("id", "")
                sql_text = etree.tostring(elem, encoding="unicode", method="text").strip()
                xml_text = etree.tostring(elem, encoding="unicode").strip()

                # 提取 SQL 中引用的表名
                table_pattern = r'(?:FROM|JOIN|INTO|UPDATE)\s+(\w+)'
                tables = list(set(re.findall(table_pattern, sql_text, re.IGNORECASE)))

                cross_refs = []
                for table_name in tables:
                    ref = self._make_cross_ref(
                        "xml_statement", f"{namespace}.{stmt_id}", stmt_id,
                        "table", table_name, "queries_table",
                        f"{stmt_tag} references table {table_name}"
                    )
                    cross_refs.append(ref)

                # implements_mapper：namespace 关联到 Java Mapper 接口
                if namespace and stmt_id:
                    ref = self._make_cross_ref(
                        "xml_statement", f"{namespace}.{stmt_id}", stmt_id,
                        "method", f"{namespace}.{stmt_id}", "implements_mapper",
                        f"Implements {namespace}.{stmt_id}"
                    )
                    cross_refs.append(ref)

                chunks.append(CodeChunk(
                    chunk_id=self._gen_id(),
                    source_id=self.source_id,
                    file_path=rel_path,
                    chunk_type="xml_statement",
                    language="xml",
                    name=stmt_id,
                    qualified_name=f"{namespace}.{stmt_id}",
                    content=xml_text[:2000],
                    summary=f"MyBatis {stmt_tag}: {namespace}.{stmt_id} → tables: {', '.join(tables)}",
                    metadata={"statement_type": stmt_tag, "tables": tables,
                              "namespace": namespace, "cross_refs": cross_refs},
                    line_start=elem.sourceline or 0,
                    line_end=elem.sourceline or 0,
                ))

        return chunks

    def _parse_pom_xml(self, root, abs_path: str, rel_path: str) -> List[CodeChunk]:
        """解析 pom.xml，提取依赖信息（留给 Phase 2 深度处理）。"""
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()

        return [CodeChunk(
            chunk_id=self._gen_id(),
            source_id=self.source_id,
            file_path=rel_path,
            chunk_type="pom",
            language="xml",
            name="pom.xml",
            qualified_name=rel_path,
            content=source[:2000],
            summary=f"Maven POM: {rel_path}",
            metadata={"cross_refs": []},
            line_start=1,
            line_end=len(source.splitlines()),
        )]

    # ------------------------------------------------------------------
    # Handlebars 解析
    # ------------------------------------------------------------------

    def parse_hbs_file(self, abs_path: str, rel_path: str) -> List[CodeChunk]:
        """解析 .hbs 模板文件。"""
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()

        cross_refs = []

        # {{> partial}} → includes_partial
        partials = re.findall(r'\{\{>\s*([a-zA-Z0-9_/\-]+)\s*\}\}', source)
        for p in set(partials):
            cross_refs.append(self._make_cross_ref(
                "template", rel_path, os.path.basename(rel_path),
                "template", p, "includes_partial",
                f"{{{{> {p}}}}}"
            ))

        # <form action="/api/..."> → calls_api
        form_actions = re.findall(r'<form[^>]*action=["\']([^"\']+)["\']', source)
        for action in form_actions:
            cross_refs.append(self._make_cross_ref(
                "template", rel_path, os.path.basename(rel_path),
                "api", action, "calls_api",
                f"form action=\"{action}\""
            ))

        # {{variable}} 占位符
        variables = list(set(re.findall(r'\{\{([a-zA-Z0-9_.]+)\}\}', source)))

        # layout/extend
        layout_refs = re.findall(r'\{\{#extend\s+["\']([^"\']+)["\']\}\}', source)
        for layout in layout_refs:
            cross_refs.append(self._make_cross_ref(
                "template", rel_path, os.path.basename(rel_path),
                "template", layout, "extends_layout",
                f"extends {layout}"
            ))

        return [CodeChunk(
            chunk_id=self._gen_id(),
            source_id=self.source_id,
            file_path=rel_path,
            chunk_type="template",
            language="handlebars",
            name=os.path.basename(rel_path),
            qualified_name=rel_path,
            content=source[:5000],
            summary=f"HBS template: {rel_path} (partials: {len(partials)}, variables: {len(variables)})",
            metadata={
                "partials": list(set(partials)),
                "variables": variables[:50],
                "form_actions": form_actions,
                "cross_refs": cross_refs,
            },
            line_start=1,
            line_end=len(source.splitlines()),
        )]

    # ------------------------------------------------------------------
    # JavaScript / jQuery 解析
    # ------------------------------------------------------------------

    def parse_jquery_js(self, abs_path: str, rel_path: str) -> List[CodeChunk]:
        """解析 JS 文件，提取 AJAX 调用和函数定义。"""
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()

        lines = source.splitlines()
        chunks: List[CodeChunk] = []
        cross_refs: List[Dict] = []

        # $.ajax/$.get/$.post/fetch URL 提取
        ajax_urls = re.findall(
            r'(?:\$\.(?:ajax|get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']'
            r'|url\s*:\s*["\']([^"\']+)["\']'
            r'|fetch\s*\(\s*["\']([^"\']+)["\'])',
            source
        )
        api_calls = []
        for match in ajax_urls:
            url = match[0] or match[1] or match[2]
            if url:
                api_calls.append(url)
                cross_refs.append(self._make_cross_ref(
                    "javascript", rel_path, os.path.basename(rel_path),
                    "api", url, "calls_api",
                    f"AJAX call to {url}"
                ))

        # 文件级 chunk
        file_chunk = CodeChunk(
            chunk_id=self._gen_id(),
            source_id=self.source_id,
            file_path=rel_path,
            chunk_type="javascript_file",
            language="javascript",
            name=os.path.basename(rel_path),
            qualified_name=rel_path,
            content=source[:5000],
            summary=f"JS file: {rel_path} (API calls: {len(api_calls)})",
            metadata={
                "api_calls": api_calls,
                "cross_refs": cross_refs,
            },
            line_start=1,
            line_end=len(lines),
        )
        chunks.append(file_chunk)

        # 命名函数 function xxx()
        func_pattern = re.compile(r'^(?:(?:var|let|const)\s+)?function\s+(\w+)\s*\(', re.MULTILINE)
        for match in func_pattern.finditer(source):
            func_name = match.group(1)
            func_line = source[:match.start()].count('\n') + 1
            func_end = min(func_line + self.max_lines, len(lines))
            func_content = "\n".join(lines[func_line - 1:func_end])

            chunks.append(CodeChunk(
                chunk_id=self._gen_id(),
                source_id=self.source_id,
                file_path=rel_path,
                chunk_type="function",
                language="javascript",
                name=func_name,
                qualified_name=f"{rel_path}:{func_name}",
                content=func_content,
                summary=f"JS function: {func_name}",
                metadata={"cross_refs": []},
                line_start=func_line,
                line_end=func_end,
            ))

        return chunks

    # ------------------------------------------------------------------
    # 配置文件解析
    # ------------------------------------------------------------------

    def parse_config_file(self, abs_path: str, rel_path: str) -> List[CodeChunk]:
        """解析 YAML/Properties 配置文件。"""
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()

        return [CodeChunk(
            chunk_id=self._gen_id(),
            source_id=self.source_id,
            file_path=rel_path,
            chunk_type="config",
            language="config",
            name=os.path.basename(rel_path),
            qualified_name=rel_path,
            content=source[:3000],
            summary=f"Config file: {rel_path}",
            metadata={"cross_refs": []},
            line_start=1,
            line_end=len(source.splitlines()),
        )]

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _file_level_chunk(self, source: str, rel_path: str, language: str) -> CodeChunk:
        """降级方案：创建文件级 chunk。"""
        return CodeChunk(
            chunk_id=self._gen_id(),
            source_id=self.source_id,
            file_path=rel_path,
            chunk_type="file",
            language=language,
            name=os.path.basename(rel_path),
            qualified_name=rel_path,
            content=source[:3000],
            summary=f"File: {rel_path}",
            metadata={"cross_refs": []},
            line_start=1,
            line_end=len(source.splitlines()),
        )

    def _gen_id(self) -> str:
        return str(uuid.uuid4())

    def _extract_annotations(self, node) -> List[Dict[str, Any]]:
        """从 javalang AST 节点提取注解列表。"""
        annotations = []
        for ann in (node.annotations or []):
            ann_info = {"name": ann.name, "value": None}
            if ann.element is not None:
                if isinstance(ann.element, str):
                    ann_info["value"] = ann.element
                elif isinstance(ann.element, list):
                    # 多属性注解
                    values = {}
                    for elem in ann.element:
                        if hasattr(elem, 'name') and hasattr(elem, 'value'):
                            val = elem.value
                            if hasattr(val, 'value'):
                                val = val.value
                            values[elem.name] = str(val)
                    ann_info["value"] = values if values else str(ann.element)
                elif hasattr(ann.element, 'value'):
                    ann_info["value"] = ann.element.value
                else:
                    ann_info["value"] = str(ann.element)
            annotations.append(ann_info)
        return annotations

    def _get_request_mapping(self, annotations: List[Dict]) -> str:
        """从注解列表中提取类级 @RequestMapping 路径。"""
        for ann in annotations:
            if ann["name"] == "RequestMapping":
                val = ann.get("value")
                if isinstance(val, str):
                    return val.strip('"')
                elif isinstance(val, dict):
                    return val.get("value", "").strip('"')
        return ""

    def _get_api_path(self, annotations: List[Dict], class_mapping: str) -> str:
        """从方法注解中提取完整 API 路径。"""
        mapping_annotations = {
            "GetMapping", "PostMapping", "PutMapping", "DeleteMapping",
            "PatchMapping", "RequestMapping",
        }
        for ann in annotations:
            if ann["name"] in mapping_annotations:
                val = ann.get("value")
                path = ""
                if isinstance(val, str):
                    path = val.strip('"')
                elif isinstance(val, dict):
                    path = val.get("value", "").strip('"')

                if class_mapping:
                    return f"{class_mapping.rstrip('/')}/{path.lstrip('/')}" if path else class_mapping
                return path
        return ""

    def _get_http_method(self, annotations: List[Dict]) -> str:
        """从注解推断 HTTP 方法。"""
        method_map = {
            "GetMapping": "GET",
            "PostMapping": "POST",
            "PutMapping": "PUT",
            "DeleteMapping": "DELETE",
            "PatchMapping": "PATCH",
        }
        for ann in annotations:
            if ann["name"] in method_map:
                return method_map[ann["name"]]
            if ann["name"] == "RequestMapping":
                val = ann.get("value")
                if isinstance(val, dict) and "method" in val:
                    return val["method"]
        return "GET"

    def _extract_config_key(self, value: str) -> Optional[str]:
        """从 @Value 注解值中提取 ${key} 中的 key。"""
        if isinstance(value, str):
            match = re.search(r'\$\{([^}]+)\}', value)
            if match:
                # 处理默认值: ${key:default}
                return match.group(1).split(":")[0]
        return None

    def _make_cross_ref(
        self, from_type: str, from_id: str, from_name: str,
        to_type: str, to_key: str, ref_type: str, context: str
    ) -> Dict[str, str]:
        return {
            "ref_id": self._gen_id(),
            "from_type": from_type,
            "from_id": from_id,
            "from_name": from_name,
            "to_type": to_type,
            "to_key": to_key,
            "ref_type": ref_type,
            "context": context,
        }
