"""Streaming FASTQ parser and read-quality report generator."""

from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from .base import FormatEngine


class FASTQEngine(FormatEngine):
    """Parse FASTQ reads without retaining the complete file in memory."""

    FORMAT_NAME = "fastq"
    FORMAT_DESCRIPTION = "FASTQ sequencing reads with Phred+33 quality scores"
    SUPPORTED_EXTENSIONS = {".fastq", ".fq"}
    PREVIEW_READS = 10
    PREVIEW_BASES = 100
    MAX_QUALITY_CYCLES = 400

    def __init__(self):
        super().__init__()
        try:
            from Bio import SeqIO

            self._SeqIO = SeqIO
        except ImportError as e:
            raise ImportError("BioPython is required for FASTQ support. Install it with: pip install biopython>=1.80") from e

    def parse(self, file_path: str, options: Optional[Dict] = None) -> Dict:
        if not self.validate_file(file_path):
            raise ValueError(f"Unsupported FASTQ file format: {file_path}")

        options = options or {}
        language = str(options.get("language", "en")).lower()
        is_chinese = language in {"ch", "zh", "zh-cn", "chinese"}
        stats = self._scan(file_path, options.get("file_name"))
        markdown = self._render_markdown(stats, is_chinese)
        summary = self._render_summary(stats, is_chinese)
        metadata = {
            "read_count": stats["read_count"],
            "total_bases": stats["total_bases"],
            "mean_read_length": stats["mean_read_length"],
            "gc_percent": stats["gc_percent"],
            "mean_phred": stats["mean_phred"],
            "q20_percent": stats["q20_percent"],
            "q30_percent": stats["q30_percent"],
        }
        return {
            "format": self.FORMAT_NAME,
            "markdown": markdown,
            "json_content": stats,
            "metadata": metadata,
            "summary": summary,
        }

    def _scan(self, file_path: str, display_filename: Optional[str] = None) -> Dict:
        read_count = total_bases = total_quality = q20_bases = q30_bases = gc_bases = 0
        canonical_bases = 0
        min_read_length: Optional[int] = None
        max_read_length = 0
        base_counts: Counter = Counter()
        quality_sums = [0] * self.MAX_QUALITY_CYCLES
        quality_counts = [0] * self.MAX_QUALITY_CYCLES
        previews: List[Dict] = []

        try:
            for record in self._SeqIO.parse(file_path, "fastq"):
                sequence = str(record.seq).upper()
                qualities = record.letter_annotations.get("phred_quality")
                if qualities is None or len(sequence) != len(qualities):
                    raise ValueError(f"FASTQ record {read_count + 1} has missing or mismatched quality values")

                length = len(sequence)
                if length == 0:
                    raise ValueError(f"FASTQ record {read_count + 1} has an empty sequence")

                read_count += 1
                total_bases += length
                min_read_length = length if min_read_length is None else min(min_read_length, length)
                max_read_length = max(max_read_length, length)

                counts = Counter(sequence)
                base_counts.update(counts)
                gc_bases += counts.get("G", 0) + counts.get("C", 0)
                canonical_bases += sum(counts.get(base, 0) for base in "ACGTU")

                total_quality += sum(qualities)
                q20_bases += sum(q >= 20 for q in qualities)
                q30_bases += sum(q >= 30 for q in qualities)
                for position, quality in enumerate(qualities[: self.MAX_QUALITY_CYCLES]):
                    quality_sums[position] += quality
                    quality_counts[position] += 1

                if len(previews) < self.PREVIEW_READS:
                    preview_qualities = qualities[: self.PREVIEW_BASES]
                    previews.append(
                        {
                            "id": record.id,
                            "description": record.description,
                            "length": length,
                            "mean_phred": round(sum(qualities) / length, 2),
                            "sequence_preview": sequence[: self.PREVIEW_BASES],
                            "preview_truncated": length > self.PREVIEW_BASES,
                            "quality_preview_phred": preview_qualities,
                        }
                    )
        except Exception as e:
            if isinstance(e, ValueError) and str(e).startswith("FASTQ record "):
                raise
            raise ValueError(f"FASTQ parsing failed: {e}") from e

        if read_count == 0:
            raise ValueError("FASTQ file contains no reads")

        mean_read_length = total_bases / read_count
        mean_phred = total_quality / total_bases
        gc_percent = 100 * gc_bases / canonical_bases if canonical_bases else 0.0
        position_quality = [
            {"position": index + 1, "mean_phred": round(total / count, 2), "read_count": count}
            for index, (total, count) in enumerate(zip(quality_sums, quality_counts))
            if count
        ]

        return {
            "format": self.FORMAT_NAME,
            "file_name": Path(display_filename or file_path).name,
            "read_count": read_count,
            "total_bases": total_bases,
            "min_read_length": min_read_length or 0,
            "mean_read_length": round(mean_read_length, 2),
            "max_read_length": max_read_length,
            "gc_percent": round(gc_percent, 3),
            "base_counts": {base: base_counts.get(base, 0) for base in "ACGTUN"},
            "other_base_count": total_bases - sum(base_counts.get(base, 0) for base in "ACGTUN"),
            "mean_phred": round(mean_phred, 3),
            "q20_percent": round(100 * q20_bases / total_bases, 3),
            "q30_percent": round(100 * q30_bases / total_bases, 3),
            "quality_encoding": "Phred+33 (FASTQ Sanger)",
            "mean_quality_by_position": position_quality,
            "read_preview": previews,
        }

    @staticmethod
    def _render_summary(stats: Dict, is_chinese: bool) -> str:
        if is_chinese:
            return (
                f"包含 {stats['read_count']:,} 条 reads、{stats['total_bases']:,} 个碱基；"
                f"平均长度 {stats['mean_read_length']:,.2f} bp，GC {stats['gc_percent']:.3f}%，"
                f"平均质量 Q{stats['mean_phred']:.2f}，Q30 碱基占比 {stats['q30_percent']:.3f}%"
            )
        return (
            f"{stats['read_count']:,} reads and {stats['total_bases']:,} bases; "
            f"mean length {stats['mean_read_length']:,.2f} bp, GC {stats['gc_percent']:.3f}%, "
            f"mean quality Q{stats['mean_phred']:.2f}, Q30 bases {stats['q30_percent']:.3f}%"
        )

    def _render_markdown(self, stats: Dict, is_chinese: bool) -> str:
        if is_chinese:
            lines = [
                "# FASTQ 测序数据质量报告",
                "",
                f"- **文件**：`{stats['file_name']}`",
                f"- **Reads 数**：{stats['read_count']:,}",
                f"- **总碱基数**：{stats['total_bases']:,} bp",
                f"- **Read 长度（最短 / 平均 / 最长）**：{stats['min_read_length']:,} / {stats['mean_read_length']:,.2f} / {stats['max_read_length']:,} bp",
                f"- **GC 含量**：{stats['gc_percent']:.3f}%（按 A/C/G/T/U 碱基计算）",
                f"- **平均 Phred 质量**：Q{stats['mean_phred']:.3f}",
                f"- **Q20 碱基占比**：{stats['q20_percent']:.3f}%",
                f"- **Q30 碱基占比**：{stats['q30_percent']:.3f}%",
                f"- **质量值编码**：{stats['quality_encoding']}",
                "",
                "## 碱基组成",
                "",
                "| 碱基 | 数量 |",
                "|---|---:|",
            ]
            base_names = {"A": "A", "C": "C", "G": "G", "T": "T", "U": "U", "N": "N"}
        else:
            lines = [
                "# FASTQ Sequencing Quality Report",
                "",
                f"- **File**: `{stats['file_name']}`",
                f"- **Read count**: {stats['read_count']:,}",
                f"- **Total bases**: {stats['total_bases']:,} bp",
                f"- **Read length (min / mean / max)**: {stats['min_read_length']:,} / {stats['mean_read_length']:,.2f} / {stats['max_read_length']:,} bp",
                f"- **GC content**: {stats['gc_percent']:.3f}% (among A/C/G/T/U bases)",
                f"- **Mean Phred quality**: Q{stats['mean_phred']:.3f}",
                f"- **Q20 bases**: {stats['q20_percent']:.3f}%",
                f"- **Q30 bases**: {stats['q30_percent']:.3f}%",
                f"- **Quality encoding**: {stats['quality_encoding']}",
                "",
                "## Base composition",
                "",
                "| Base | Count |",
                "|---|---:|",
            ]
            base_names = {base: base for base in "ACGTUN"}

        for base in "ACGTUN":
            lines.append(f"| {base_names[base]} | {stats['base_counts'][base]:,} |")
        lines.append(f"| {'其他' if is_chinese else 'Other'} | {stats['other_base_count']:,} |")

        if stats["mean_quality_by_position"]:
            lines.extend(
                [
                    "",
                    f"## {'逐碱基位置平均质量' if is_chinese else 'Mean quality by read position'}",
                    "",
                    "| Position (bp) | Mean Phred | Reads |",
                    "|---:|---:|---:|",
                ]
            )
            selected_positions = {1, 10, 25, 50, 100, 150, 200, 300, 400}
            for item in stats["mean_quality_by_position"]:
                if item["position"] in selected_positions:
                    lines.append(
                        f"| {item['position']} | {item['mean_phred']:.2f} | {item['read_count']:,} |"
                    )

        lines.extend(
            [
                "",
                f"## {'Read 预览（前 10 条）' if is_chinese else 'Read preview (first 10 reads)'}",
                "",
            ]
        )
        for index, read in enumerate(stats["read_preview"], 1):
            description = read["description"].replace("\n", " ")
            sequence = read["sequence_preview"] + ("…" if read["preview_truncated"] else "")
            lines.extend(
                [
                    f"### {index}. `{read['id']}`",
                    "",
                    f"- **{'长度' if is_chinese else 'Length'}**: {read['length']:,} bp",
                    f"- **{'平均质量' if is_chinese else 'Mean quality'}**: Q{read['mean_phred']:.2f}",
                    f"- **{'序列' if is_chinese else 'Sequence'}**: `{sequence}`",
                    f"- **{'标题' if is_chinese else 'Header'}**: {description}",
                    "",
                ]
            )
        lines.append("> " + ("报告统计了完整 FASTQ 文件；序列内容仅展示前 10 条的有限预览。" if is_chinese else "Statistics cover the full FASTQ file; sequence content is limited to previews of the first 10 reads."))
        return "\n".join(lines) + "\n"
