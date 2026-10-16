# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
"""
GenBank Format Engine - GenBank 格式解析引擎

GenBank 是 NCBI 的标准基因序列注释格式
包含序列数据和丰富的注释信息（基因、蛋白质、特征等）

格式示例：
LOCUS       AB000100                 500 bp    DNA     linear   PLN 01-JAN-2000
DEFINITION  Example sequence
ACCESSION   AB000100
VERSION     AB000100.1
...
FEATURES             Location/Qualifiers
     source          1..500
                     /organism="Homo sapiens"
     gene            100..400
                     /gene="EXAMPLE"
...
ORIGIN
        1 atcgatcgat cgatcgatcg ...
//

依赖：
- BioPython: 必需，用于准确解析 GenBank 格式
"""

from typing import Dict, List, Optional
from .base import FormatEngine
from .i18n import get_language, CommonSemantics


class GenBankEngine(FormatEngine):
    """GenBank 格式解析引擎（基于 BioPython）"""

    FORMAT_NAME = "genbank"
    FORMAT_DESCRIPTION = "NCBI 基因序列注释格式"
    SUPPORTED_EXTENSIONS = {".gb", ".gbk", ".genbank", ".gbff"}

    def __init__(self):
        super().__init__()

        # 导入 BioPython（必需）
        try:
            from Bio import SeqIO
            from Bio.SeqUtils import gc_fraction

            self._SeqIO = SeqIO
            self._gc_fraction = gc_fraction
            self.logger.info("✅ BioPython loaded for GenBank parsing")
        except ImportError as e:
            self.logger.error("❌ BioPython is required for GenBank parsing")
            raise ImportError(
                "BioPython is required for GenBank format support. Install it with: pip install biopython>=1.80"
            ) from e

    def parse(self, file_path: str, options: Optional[Dict] = None) -> Dict:
        """
        解析 GenBank 文件

        Args:
            file_path: 文件路径
            options: 解析选项
                - max_sequence_preview: 序列预览的最大长度（默认 100）
                - include_full_sequence: 是否在 JSON 中包含完整序列（默认 True）
                - include_features: 是否包含特征注释（默认 True）
                - language: 语义描述语言 ('en' 或 'zh'，默认 'en')

        Returns:
            解析结果
        """
        if not self.validate_file(file_path):
            raise ValueError(f"Unsupported file format: {file_path}")

        # 解析选项
        options = options or {}
        max_preview = options.get("max_sequence_preview", 100)
        include_full = options.get("include_full_sequence", True)
        include_features = options.get("include_features", True)
        lang_code = options.get("language", "en")

        # 解析语言并初始化国际化组件
        lang = get_language(lang_code)
        self.common_i18n = CommonSemantics(lang)

        # 使用 BioPython 解析
        records = self._parse_with_biopython(file_path, include_features)

        # 生成 Markdown 和 JSON
        markdown = self._generate_markdown(records, max_preview, include_features)
        json_content = self._generate_json(records, include_full, include_features)
        metadata = self._generate_metadata(records)
        summary = self._generate_summary(records)

        return {
            "format": self.FORMAT_NAME,
            "markdown": markdown,
            "json_content": json_content,
            "metadata": metadata,
            "summary": summary,
        }

    def _parse_with_biopython(self, file_path: str, include_features: bool) -> List[Dict]:
        """使用 BioPython 解析 GenBank 文件并进行深度语义提取"""
        records = []

        try:
            for record in self._SeqIO.parse(file_path, "genbank"):
                parsed_record = {
                    "id": record.id,
                    "name": record.name,
                    "description": record.description,
                    "sequence": str(record.seq),
                    "length": len(record.seq),
                    "annotations": dict(record.annotations),
                }

                # 计算 GC 含量（使用 BioPython）
                try:
                    gc_content = self._gc_fraction(record.seq)
                    parsed_record["gc_content"] = gc_content
                except Exception:
                    parsed_record["gc_content"] = None

                # 解析特征信息（使用 BioPython 的 Feature 对象）
                if include_features:
                    features = []
                    for feature in record.features:
                        feat_dict = {
                            "type": feature.type,
                            "location": str(feature.location),
                            "strand": feature.location.strand if hasattr(feature.location, "strand") else None,
                            "qualifiers": {k: v for k, v in feature.qualifiers.items()},
                        }
                        features.append(feat_dict)
                    parsed_record["features"] = features

                    # 提取语义丰富的特征摘要（为 RAG 优化）
                    parsed_record["feature_summary"] = self._extract_feature_summary(features)

                    # 生成语义描述（核心 RAG 信息）
                    parsed_record["semantic_description"] = self._generate_semantic_description(parsed_record)

                records.append(parsed_record)

        except Exception as e:
            self.logger.error(f"Failed to parse GenBank file with BioPython: {e}")
            raise ValueError(f"GenBank parsing failed: {e}") from e

        return records

    def _generate_markdown(self, records: List[Dict], max_preview: int, include_features: bool) -> str:
        """生成 Markdown 格式"""
        title = self.common_i18n.get("genbank_title")
        lines = [f"# {title}\n"]

        # 总体统计
        total_records = len(records)
        total_length = sum(r["length"] for r in records)

        lines.append(f"## 📊 {self.common_i18n.get('statistics')}\n")
        lines.append(f"- **{self.common_i18n.get('sequence_count')}**: {total_records}")
        lines.append(f"- **{self.common_i18n.get('total_length')}**: {total_length:,} bp\n")

        # 记录详情
        lines.append(f"## 🧬 {self.common_i18n.get('sequence_details')}\n")

        for i, record in enumerate(records, 1):
            lines.append(f"### {i}. {record['name'] or record['id']}\n")

            # 基本信息
            lines.append("**Basic Information**:")
            lines.append(f"- ID: `{record['id']}`")
            lines.append(f"- Name: `{record['name']}`")
            lines.append(f"- Description: {record['description']}")
            lines.append(f"- Length: {record['length']:,} bp\n")

            # 注释信息
            if record.get("annotations"):
                lines.append("**Annotations**:")
                for key, value in record["annotations"].items():
                    if isinstance(value, (str, int, float)):
                        lines.append(f"- {key}: {value}")
                lines.append("")

            # 特征信息
            if include_features and record.get("features"):
                lines.append(f"**Feature Count**: {len(record['features'])}")

                # 统计特征类型
                feature_types = {}
                for feat in record["features"]:
                    feat_type = feat["type"]
                    feature_types[feat_type] = feature_types.get(feat_type, 0) + 1

                lines.append("**Feature Types**:")
                for feat_type, count in sorted(feature_types.items(), key=lambda x: x[1], reverse=True):
                    lines.append(f"- {feat_type}: {count}")
                lines.append("")

            # 序列预览
            preview = record["sequence"][:max_preview]
            if len(record["sequence"]) > max_preview:
                preview += "..."

            lines.append(f"**{self.common_i18n.get('sequence_preview')}**:\n```\n{preview}\n```\n")

            # GC 含量（由 BioPython 计算）
            if record.get("gc_content") is not None:
                gc_percent = record["gc_content"] * 100
                lines.append(f"**{self.common_i18n.get('gc_content')}**: {gc_percent:.2f}%\n")

            # 语义描述（核心 RAG 信息）
            if record.get("semantic_description"):
                lines.append(
                    f"**🔬 {self.common_i18n.get('biological_significance')}**:\n{record['semantic_description']}\n"
                )

        return "\n".join(lines)

    def _generate_json(self, records: List[Dict], include_full: bool, include_features: bool) -> Dict:
        """生成 JSON 格式 - 包含丰富的语义信息"""
        json_records = []

        for record in records:
            json_record = {
                "id": record["id"],
                "name": record["name"],
                "description": record["description"],
                "length": record["length"],
                "annotations": record.get("annotations", {}),
            }

            if include_full:
                json_record["sequence"] = record["sequence"]

            # GC 含量（由 BioPython 计算）
            if record.get("gc_content") is not None:
                json_record["gc_content"] = record["gc_content"]

            # 语义描述（RAG 核心）
            if record.get("semantic_description"):
                json_record["semantic_description"] = record["semantic_description"]

            # 特征信息
            if include_features and record.get("features"):
                json_record["features"] = record["features"]

                # 特征类型统计
                feature_types = {}
                for feat in record["features"]:
                    feat_type = feat["type"]
                    feature_types[feat_type] = feature_types.get(feat_type, 0) + 1
                json_record["feature_types"] = feature_types

                # 特征摘要（RAG 优化）
                if record.get("feature_summary"):
                    summary = record["feature_summary"]
                    json_record["feature_summary"] = {
                        "gene_count": summary.get("gene_count", 0),
                        "cds_count": summary.get("cds_count", 0),
                        "regulatory_count": len(summary.get("regulatory", [])),
                        "rna_count": len(summary.get("rna", [])),
                        "genes": summary.get("genes", [])[:10],  # 前10个基因
                        "proteins": summary.get("proteins", [])[:10],  # 前10个蛋白质
                    }

            json_records.append(json_record)

        return {
            "records": json_records,
            "total_count": len(records),
            "total_length": sum(r["length"] for r in records),
            "analysis_version": "1.0",
            "genbank_features": [
                "feature_extraction",
                "gene_annotation",
                "protein_annotation",
                "regulatory_elements",
                "rna_features",
                "semantic_description",
            ],
        }

    def _generate_metadata(self, records: List[Dict]) -> Dict:
        """生成元数据"""
        organisms = set()
        for record in records:
            if "annotations" in record and "organism" in record["annotations"]:
                organisms.add(record["annotations"]["organism"])

        return {
            "format": "GenBank",
            "record_count": len(records),
            "total_bases": sum(r["length"] for r in records),
            "organisms": list(organisms),
            "file_type": "annotated_sequence",
        }

    def _generate_summary(self, records: List[Dict]) -> str:
        """生成摘要"""
        count = len(records)
        total_length = sum(r["length"] for r in records)

        if count == 0:
            return self.common_i18n.get("empty_file")

        # 统计特征数量
        total_features = 0
        for record in records:
            if "features" in record:
                total_features += len(record["features"])

        if total_features > 0:
            return self.common_i18n.get(
                "genbank_summary_with_features", count=count, length=total_length, features=total_features
            )
        else:
            return self.common_i18n.get("genbank_summary", count=count, length=total_length)

    def _extract_feature_summary(self, features: List[Dict]) -> Dict:
        """
        从特征列表中提取语义丰富的摘要信息（为 RAG 优化）
        这是 GenBank 最有价值的部分
        """
        summary = {
            "gene_count": 0,
            "cds_count": 0,
            "genes": [],  # 基因列表
            "proteins": [],  # 蛋白质列表
            "regulatory": [],  # 调控元件
            "rna": [],  # RNA 特征
            "feature_types": {},  # 特征类型统计
        }

        for feat in features:
            feat_type = feat["type"]
            qualifiers = feat["qualifiers"]

            # 统计特征类型
            summary["feature_types"][feat_type] = summary["feature_types"].get(feat_type, 0) + 1

            # 提取基因信息
            if feat_type == "gene":
                summary["gene_count"] += 1
                gene_info = {
                    "location": feat["location"],
                    "strand": feat.get("strand"),
                }

                # 提取基因名称和功能
                if "gene" in qualifiers:
                    gene_info["name"] = qualifiers["gene"][0] if qualifiers["gene"] else None
                if "locus_tag" in qualifiers:
                    gene_info["locus_tag"] = qualifiers["locus_tag"][0] if qualifiers["locus_tag"] else None
                if "note" in qualifiers:
                    gene_info["note"] = qualifiers["note"][0] if qualifiers["note"] else None

                summary["genes"].append(gene_info)

            # 提取编码序列（CDS）信息
            elif feat_type == "CDS":
                summary["cds_count"] += 1
                protein_info = {
                    "location": feat["location"],
                    "strand": feat.get("strand"),
                }

                # 提取蛋白质信息（最重要的注释）
                if "product" in qualifiers:
                    protein_info["product"] = qualifiers["product"][0] if qualifiers["product"] else None
                if "gene" in qualifiers:
                    protein_info["gene"] = qualifiers["gene"][0] if qualifiers["gene"] else None
                if "protein_id" in qualifiers:
                    protein_info["protein_id"] = qualifiers["protein_id"][0] if qualifiers["protein_id"] else None
                if "translation" in qualifiers:
                    # 蛋白质序列（可用于进一步分析）
                    translation = qualifiers["translation"][0] if qualifiers["translation"] else None
                    if translation:
                        protein_info["translation_length"] = len(translation)
                if "function" in qualifiers:
                    protein_info["function"] = qualifiers["function"][0] if qualifiers["function"] else None
                if "note" in qualifiers:
                    protein_info["note"] = qualifiers["note"][0] if qualifiers["note"] else None

                summary["proteins"].append(protein_info)

            # 提取调控元件
            elif feat_type in (
                "promoter",
                "enhancer",
                "terminator",
                "regulatory",
                "CAAT_signal",
                "TATA_signal",
                "misc_regulatory",
            ):
                reg_info = {
                    "type": feat_type,
                    "location": feat["location"],
                }
                if "regulatory_class" in qualifiers:
                    reg_info["regulatory_class"] = qualifiers["regulatory_class"][0]
                if "note" in qualifiers:
                    reg_info["note"] = qualifiers["note"][0]

                summary["regulatory"].append(reg_info)

            # 提取 RNA 特征
            elif feat_type in ("rRNA", "tRNA", "mRNA", "ncRNA", "misc_RNA"):
                rna_info = {
                    "type": feat_type,
                    "location": feat["location"],
                }
                if "product" in qualifiers:
                    rna_info["product"] = qualifiers["product"][0]
                if "gene" in qualifiers:
                    rna_info["gene"] = qualifiers["gene"][0]

                summary["rna"].append(rna_info)

        return summary

    def _generate_semantic_description(self, record: Dict) -> str:
        """
        生成 GenBank 记录的语义描述（核心 RAG 功能）
        将结构化的注释转换为自然语言描述
        """
        parts = []

        # 基本信息
        organism = record.get("annotations", {}).get("organism")
        if organism:
            if self.common_i18n.lang == "zh":
                parts.append(f"该序列来自 {organism}")
            else:
                parts.append(f"This sequence is from {organism}")

        # 序列基本特征
        length = record["length"]
        gc_content = record.get("gc_content")

        if gc_content is not None:
            gc_percent = gc_content * 100
            if self.common_i18n.lang == "zh":
                parts.append(f"全长 {length:,} bp，GC 含量 {gc_percent:.1f}%")
            else:
                parts.append(f"Total length {length:,} bp, GC content {gc_percent:.1f}%")
        else:
            if self.common_i18n.lang == "zh":
                parts.append(f"全长 {length:,} bp")
            else:
                parts.append(f"Total length {length:,} bp")

        # 特征摘要（最重要的语义信息）
        feature_summary = record.get("feature_summary", {})

        if feature_summary:
            # 基因和蛋白质信息
            gene_count = feature_summary.get("gene_count", 0)
            cds_count = feature_summary.get("cds_count", 0)

            if gene_count > 0 or cds_count > 0:
                if self.common_i18n.lang == "zh":
                    parts.append(f"包含 {gene_count} 个基因和 {cds_count} 个编码序列")
                else:
                    parts.append(f"Contains {gene_count} gene(s) and {cds_count} coding sequence(s)")

            # 提取主要蛋白质产物（前3个）
            proteins = feature_summary.get("proteins", [])
            if proteins:
                protein_products = []
                for prot in proteins[:3]:
                    product = prot.get("product")
                    if product:
                        protein_products.append(product)

                if protein_products:
                    if self.common_i18n.lang == "zh":
                        parts.append(f"编码的主要蛋白质包括：{', '.join(protein_products)}")
                    else:
                        parts.append(f"Main encoded proteins include: {', '.join(protein_products)}")

            # RNA 特征
            rna = feature_summary.get("rna", [])
            if rna:
                rna_types = {}
                for r in rna:
                    rna_type = r.get("type", "RNA")
                    rna_types[rna_type] = rna_types.get(rna_type, 0) + 1

                rna_desc = ", ".join([f"{count} {rtype}" for rtype, count in rna_types.items()])
                if self.common_i18n.lang == "zh":
                    parts.append(f"包含 RNA 特征：{rna_desc}")
                else:
                    parts.append(f"Contains RNA features: {rna_desc}")

            # 调控元件
            regulatory = feature_summary.get("regulatory", [])
            if regulatory:
                if self.common_i18n.lang == "zh":
                    parts.append(f"包含 {len(regulatory)} 个调控元件")
                else:
                    parts.append(f"Contains {len(regulatory)} regulatory element(s)")

        # 其他注释信息
        annotations = record.get("annotations", {})

        # 分类学信息
        taxonomy = annotations.get("taxonomy", [])
        if taxonomy and len(taxonomy) > 0:
            if self.common_i18n.lang == "zh":
                parts.append(f"分类学：{' > '.join(taxonomy[:3])}")
            else:
                parts.append(f"Taxonomy: {' > '.join(taxonomy[:3])}")

        # 参考文献
        references = annotations.get("references", [])
        if references:
            if self.common_i18n.lang == "zh":
                parts.append(f"包含 {len(references)} 篇参考文献")
            else:
                parts.append(f"Contains {len(references)} reference(s)")

        # 连接所有部分
        separator = "；" if self.common_i18n.lang == "zh" else "; "
        terminator = "。" if self.common_i18n.lang == "zh" else "."

        return separator.join(parts) + terminator
