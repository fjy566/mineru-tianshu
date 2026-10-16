# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
"""
FASTA Format Engine - FASTA 格式解析引擎

FASTA 是生物信息学中最常用的序列格式
用于存储核酸序列（DNA/RNA）或蛋白质序列

格式示例：
>序列ID|描述信息
ATCGATCGATCGATCG
GCTAGCTAGCTAGCTA
>另一个序列ID|描述
GGGGCCCCAAAATTTT

依赖：
- BioPython: 必需，用于准确解析生物序列
"""

from typing import Dict, List, Optional
from .base import FormatEngine
from .i18n import get_language, SemanticGenerator, CommonSemantics


class FASTAEngine(FormatEngine):
    """FASTA 格式解析引擎（基于 BioPython）"""

    FORMAT_NAME = "fasta"
    FORMAT_DESCRIPTION = "生物序列格式 (DNA/RNA/蛋白质)"
    SUPPORTED_EXTENSIONS = {".fasta", ".fa", ".fna", ".ffn", ".faa", ".frn", ".fas"}

    def __init__(self):
        super().__init__()

        # 导入 BioPython（必需）
        try:
            from Bio import SeqIO
            from Bio.SeqUtils import gc_fraction, molecular_weight
            from Bio.SeqUtils.ProtParam import ProteinAnalysis
            from Bio.Seq import Seq
            from Bio.Data import CodonTable

            self._SeqIO = SeqIO
            self._gc_fraction = gc_fraction
            self._molecular_weight = molecular_weight
            self._ProteinAnalysis = ProteinAnalysis
            self._Seq = Seq
            self._CodonTable = CodonTable

            self.logger.info("✅ BioPython loaded for FASTA parsing with advanced analysis")
        except ImportError as e:
            self.logger.error("❌ BioPython is required for FASTA parsing")
            raise ImportError(
                "BioPython is required for FASTA format support. Install it with: pip install biopython>=1.80"
            ) from e

    def parse(self, file_path: str, options: Optional[Dict] = None) -> Dict:
        """
        解析 FASTA 文件

        Args:
            file_path: 文件路径
            options: 解析选项
                - max_sequence_preview: 序列预览的最大长度（默认 100）
                - include_full_sequence: 是否在 JSON 中包含完整序列（默认 True）
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
        lang_code = options.get("language", "en")

        # 解析语言并初始化国际化组件
        lang = get_language(lang_code)
        self.semantic_gen = SemanticGenerator(lang)
        self.common_i18n = CommonSemantics(lang)

        # 使用 BioPython 解析
        sequences = self._parse_with_biopython(file_path)

        # 生成 Markdown 和 JSON
        markdown = self._generate_markdown(sequences, max_preview)
        json_content = self._generate_json(sequences, include_full)
        metadata = self._generate_metadata(sequences)
        summary = self._generate_summary(sequences)

        return {
            "format": self.FORMAT_NAME,
            "markdown": markdown,
            "json_content": json_content,
            "metadata": metadata,
            "summary": summary,
        }

    def _parse_with_biopython(self, file_path: str) -> List[Dict]:
        """使用 BioPython 解析 FASTA 文件并进行深度生物信息学分析"""
        sequences = []

        try:
            for record in self._SeqIO.parse(file_path, "fasta"):
                seq_data = {
                    "id": record.id,
                    "name": record.name,
                    "description": record.description,
                    "sequence": str(record.seq),
                    "length": len(record.seq),
                }

                # 判断序列类型并进行相应分析
                seq_type = self._detect_sequence_type(record.seq)
                seq_data["sequence_type"] = seq_type

                if seq_type == "nucleotide":
                    # 核酸序列分析
                    seq_data.update(self._analyze_nucleotide(record.seq))
                elif seq_type == "protein":
                    # 蛋白质序列分析
                    seq_data.update(self._analyze_protein(record.seq))

                sequences.append(seq_data)

        except Exception as e:
            self.logger.error(f"Failed to parse FASTA file with BioPython: {e}")
            raise ValueError(f"FASTA parsing failed: {e}") from e

        return sequences

    def _detect_sequence_type(self, seq) -> str:
        """检测序列类型（核酸 vs 蛋白质）"""
        seq_str = str(seq).upper()
        nucleotide_chars = set("ATCGUN")

        # 计算核酸字符的比例
        nucleotide_count = sum(1 for c in seq_str if c in nucleotide_chars)
        ratio = nucleotide_count / len(seq_str) if len(seq_str) > 0 else 0

        return "nucleotide" if ratio > 0.85 else "protein"

    def _analyze_nucleotide(self, seq) -> Dict:
        """深度分析核酸序列 - 为 RAG 提供丰富的语义信息"""
        analysis = {}

        try:
            # 1. 基础统计
            analysis["gc_content"] = self._gc_fraction(seq)
            analysis["molecular_weight"] = self._molecular_weight(seq, seq_type="DNA")

            # 2. 碱基组成
            composition = self._analyze_composition(str(seq))
            analysis["composition"] = composition

            # 3. GC 偏斜度（GC-skew）- 用于复制起点预测
            g_count = composition.get("G", 0)
            c_count = composition.get("C", 0)
            if (g_count + c_count) > 0:
                gc_skew = (g_count - c_count) / (g_count + c_count)
                analysis["gc_skew"] = gc_skew

            # 4. AT 偏斜度（AT-skew）
            a_count = composition.get("A", 0)
            t_count = composition.get("T", 0)
            if (a_count + t_count) > 0:
                at_skew = (a_count - t_count) / (a_count + t_count)
                analysis["at_skew"] = at_skew

            # 5. 寻找开放阅读框（ORF）
            orfs = self._find_orfs(seq)
            analysis["orfs"] = orfs
            analysis["longest_orf_length"] = max([orf["length"] for orf in orfs], default=0)

            # 6. 翻译所有6个阅读框（3个正向 + 3个反向）
            translations = self._translate_six_frames(seq)
            analysis["translations"] = translations

            # 7. 序列复杂度（熵）
            analysis["sequence_entropy"] = self._calculate_entropy(str(seq))

            # 8. 重复序列检测
            repeats = self._find_repeats(str(seq))
            analysis["repeats"] = repeats

            # 9. CpG 岛检测（对于真核生物重要）
            cpg_islands = self._find_cpg_islands(str(seq))
            analysis["cpg_islands"] = cpg_islands

            # 10. 语义描述（用于 RAG）
            analysis["semantic_description"] = self.semantic_gen.generate_nucleotide_semantics(analysis)

        except Exception as e:
            self.logger.warning(f"Some nucleotide analysis failed: {e}")

        return analysis

    def _analyze_protein(self, seq) -> Dict:
        """深度分析蛋白质序列 - 为 RAG 提供丰富的语义信息"""
        analysis = {}

        try:
            seq_str = str(seq)
            prot_analysis = self._ProteinAnalysis(seq_str)

            # 1. 基础理化性质
            analysis["molecular_weight"] = prot_analysis.molecular_weight()
            analysis["aromaticity"] = prot_analysis.aromaticity()  # 芳香性
            analysis["instability_index"] = prot_analysis.instability_index()  # 不稳定指数
            analysis["isoelectric_point"] = prot_analysis.isoelectric_point()  # 等电点

            # 2. 氨基酸组成
            analysis["amino_acid_composition"] = prot_analysis.get_amino_acids_percent()

            # 3. 二级结构预测
            secondary_structure = prot_analysis.secondary_structure_fraction()
            analysis["secondary_structure"] = {
                "helix": secondary_structure[0],
                "turn": secondary_structure[1],
                "sheet": secondary_structure[2],
            }

            # 4. 疏水性分析
            analysis["gravy"] = prot_analysis.gravy()  # Grand Average of Hydropathy

            # 5. 柔性（flexibility）
            flexibility = prot_analysis.flexibility()
            analysis["flexibility_mean"] = sum(flexibility) / len(flexibility) if flexibility else 0

            # 6. 蛋白质稳定性分类
            if analysis["instability_index"] < 40:
                analysis["stability_class"] = "stable"
            else:
                analysis["stability_class"] = "unstable"

            # 7. 功能域特征
            analysis["charge_at_ph7"] = self._calculate_charge_at_ph(seq_str, 7.0)

            # 8. 氨基酸类别统计
            analysis["amino_acid_classes"] = self._classify_amino_acids(seq_str)

            # 9. 潜在的翻译后修饰位点
            analysis["ptm_sites"] = self._predict_ptm_sites(seq_str)

            # 10. 语义描述（用于 RAG）
            analysis["semantic_description"] = self.semantic_gen.generate_protein_semantics(analysis)

        except Exception as e:
            self.logger.warning(f"Some protein analysis failed: {e}")

        return analysis

    def _find_orfs(self, seq, min_length: int = 100) -> List[Dict]:
        """寻找开放阅读框（ORF）"""
        orfs = []
        seq_str = str(seq)

        # 寻找起始密码子（ATG）到终止密码子（TAA, TAG, TGA）
        start_codons = ["ATG"]
        stop_codons = ["TAA", "TAG", "TGA"]

        for frame in range(3):
            i = frame
            while i < len(seq_str) - 2:
                codon = seq_str[i : i + 3]
                if codon in start_codons:
                    # 找到起始密码子，寻找终止密码子
                    start = i
                    j = i + 3
                    while j < len(seq_str) - 2:
                        stop_codon = seq_str[j : j + 3]
                        if stop_codon in stop_codons:
                            length = j - start + 3
                            if length >= min_length:
                                orfs.append(
                                    {"start": start, "end": j + 3, "length": length, "frame": frame, "strand": "+"}
                                )
                            break
                        j += 3
                i += 3

        return orfs

    def _translate_six_frames(self, seq) -> Dict:
        """翻译所有6个阅读框（智能截断）"""
        translations = {}

        try:
            # 正向3个阅读框
            for frame in range(3):
                frame_seq = seq[frame:]
                translated = frame_seq.translate(to_stop=False)

                # 智能截断：保留到第一个终止密码子或前200个氨基酸
                translated_str = str(translated)
                stop_pos = translated_str.find("*")
                if stop_pos != -1:
                    # 保留终止密码子后少量氨基酸以提供上下文
                    translations[f"frame_{frame + 1}_forward"] = translated_str[: stop_pos + 10]
                else:
                    translations[f"frame_{frame + 1}_forward"] = translated_str[:200]

            # 反向互补3个阅读框
            rev_comp = seq.reverse_complement()
            for frame in range(3):
                frame_seq = rev_comp[frame:]
                translated = frame_seq.translate(to_stop=False)

                translated_str = str(translated)
                stop_pos = translated_str.find("*")
                if stop_pos != -1:
                    translations[f"frame_{frame + 1}_reverse"] = translated_str[: stop_pos + 10]
                else:
                    translations[f"frame_{frame + 1}_reverse"] = translated_str[:200]
        except Exception:
            pass

        return translations

    def _calculate_entropy(self, seq: str) -> float:
        """计算序列熵（复杂度指标）"""
        from math import log2

        if not seq:
            return 0.0

        # 计算每个字符的频率
        freq = {}
        for char in seq:
            freq[char] = freq.get(char, 0) + 1

        # 计算熵
        entropy = 0.0
        for count in freq.values():
            p = count / len(seq)
            entropy -= p * log2(p)

        return entropy

    def _find_repeats(self, seq: str, min_length: int = 10) -> List[Dict]:
        """检测重复序列（优化算法 - 使用滑动窗口和字典）"""
        repeats = []
        seq_len = len(seq)
        max_repeats = 15  # 最多返回15个重复

        # 使用字典记录已访问的模式,避免重复检测
        seen_patterns = set()

        # 从较长的模式开始检测（更有意义）
        for length in range(min(50, seq_len // 3), max(min_length - 1, 2), -1):
            if len(repeats) >= max_repeats:
                break

            # 使用滑动窗口
            for i in range(seq_len - length * 2 + 1):
                if len(repeats) >= max_repeats:
                    break

                pattern = seq[i : i + length]

                # 跳过已检测的模式
                if pattern in seen_patterns:
                    continue

                # 检查是否为串联重复
                if seq[i + length : i + length * 2] == pattern:
                    seen_patterns.add(pattern)

                    # 计算重复次数
                    repeat_count = 2
                    pos = i + length * 2
                    while pos + length <= seq_len and seq[pos : pos + length] == pattern:
                        repeat_count += 1
                        pos += length

                    repeats.append(
                        {
                            "position": i,
                            "length": length,
                            "repeat_count": repeat_count,
                            "pattern": pattern[:30] + "..." if len(pattern) > 30 else pattern,
                        }
                    )

        # 按重复单元长度排序（长的更重要）
        repeats.sort(key=lambda x: x["length"] * x["repeat_count"], reverse=True)

        return repeats[:max_repeats]

    def _find_cpg_islands(self, seq: str) -> List[Dict]:
        """检测 CpG 岛（CG 富集区域）"""
        islands = []
        window_size = 200
        threshold = 0.6  # GC 含量阈值

        for i in range(0, len(seq) - window_size, 50):
            window = seq[i : i + window_size]
            gc_count = window.count("G") + window.count("C")
            gc_ratio = gc_count / window_size

            if gc_ratio >= threshold:
                # 检测 CpG 数量
                cpg_count = window.count("CG")
                expected_cpg = (window.count("C") * window.count("G")) / window_size

                if cpg_count > 0 and expected_cpg > 0:
                    obs_exp_ratio = cpg_count / expected_cpg

                    if obs_exp_ratio >= 0.6:
                        islands.append(
                            {"start": i, "end": i + window_size, "gc_content": gc_ratio, "cpg_ratio": obs_exp_ratio}
                        )

        return islands

    def _classify_amino_acids(self, seq: str) -> Dict:
        """氨基酸分类统计"""
        hydrophobic = set("AVILMFWP")
        polar = set("STNQ")
        charged_positive = set("KRH")
        charged_negative = set("DE")
        aromatic = set("FWY")

        classes = {"hydrophobic": 0, "polar": 0, "charged_positive": 0, "charged_negative": 0, "aromatic": 0}

        for aa in seq.upper():
            if aa in hydrophobic:
                classes["hydrophobic"] += 1
            elif aa in polar:
                classes["polar"] += 1
            elif aa in charged_positive:
                classes["charged_positive"] += 1
            elif aa in charged_negative:
                classes["charged_negative"] += 1
            if aa in aromatic:
                classes["aromatic"] += 1

        # 转换为百分比
        total = len(seq)
        return {k: v / total if total > 0 else 0 for k, v in classes.items()}

    def _calculate_charge_at_ph(self, seq: str, ph: float) -> float:
        """计算指定 pH 下的净电荷"""
        # 简化计算
        k_count = seq.count("K")
        r_count = seq.count("R")
        h_count = seq.count("H")
        d_count = seq.count("D")
        e_count = seq.count("E")

        # 简化的电荷计算（实际更复杂）
        positive_charge = k_count + r_count + (h_count * 0.5 if ph < 7 else 0)
        negative_charge = d_count + e_count

        return positive_charge - negative_charge

    def _predict_ptm_sites(self, seq: str) -> Dict:
        """预测翻译后修饰位点（改进版 - 考虑上下文）"""
        ptm_sites = {
            "phosphorylation": [],  # 磷酸化位点 (S, T, Y)
            "glycosylation": [],  # N-糖基化位点 (N-X-S/T 模式)
            "acetylation": [],  # 乙酰化位点 (K)
        }

        seq_len = len(seq)

        for i, aa in enumerate(seq):
            # 磷酸化位点：S, T, Y（考虑周围序列）
            if aa in "STY":
                # 提取上下文（前后各2个氨基酸）
                context_start = max(0, i - 2)
                context_end = min(seq_len, i + 3)
                context = seq[context_start:context_end]

                # 简单打分：Pro 在 +1 位置增加可能性
                score = 1.0
                if i + 1 < seq_len and seq[i + 1] == "P":
                    score = 2.0  # S/T-P 是经典磷酸化模式

                ptm_sites["phosphorylation"].append(
                    {"position": i + 1, "residue": aa, "context": context, "score": score}
                )

            # N-糖基化位点：N-X-S/T 模式（X 不是 P）
            if aa == "N" and i + 2 < seq_len:
                x = seq[i + 1]
                st = seq[i + 2]
                if x != "P" and st in "ST":
                    ptm_sites["glycosylation"].append({"position": i + 1, "motif": seq[i : i + 3], "type": "N-linked"})

            # 乙酰化位点：K（考虑周围序列）
            if aa == "K":
                context_start = max(0, i - 2)
                context_end = min(seq_len, i + 3)
                context = seq[context_start:context_end]

                ptm_sites["acetylation"].append({"position": i + 1, "context": context})

        # 只保留前15个位点（更多信息）
        for key in ptm_sites:
            ptm_sites[key] = ptm_sites[key][:15]

        return ptm_sites

    def _generate_markdown(self, sequences: List[Dict], max_preview: int) -> str:
        """生成 Markdown 格式"""
        title = self.common_i18n.get("fasta_title")
        lines = [f"# {title}\n"]

        # 总体统计
        total_seqs = len(sequences)
        total_length = sum(seq["length"] for seq in sequences)
        avg_length = total_length / total_seqs if total_seqs > 0 else 0

        lines.append(f"## 📊 {self.common_i18n.get('statistics')}\n")
        lines.append(f"- **{self.common_i18n.get('sequence_count')}**: {total_seqs}")
        lines.append(f"- **{self.common_i18n.get('total_length')}**: {total_length:,} bp")
        lines.append(f"- **{self.common_i18n.get('average_length')}**: {avg_length:.0f} bp")
        lines.append(
            f"- **{self.common_i18n.get('shortest_sequence')}**: {min((s['length'] for s in sequences), default=0):,} bp"
        )
        lines.append(
            f"- **{self.common_i18n.get('longest_sequence')}**: {max((s['length'] for s in sequences), default=0):,} bp\n"
        )

        # 序列详情
        lines.append(f"## 🧬 {self.common_i18n.get('sequence_details')}\n")

        for i, seq in enumerate(sequences, 1):
            lines.append(f"### {i}. {seq['id']}\n")
            lines.append(f"**Description**: {seq['description']}\n")
            lines.append(f"**Length**: {seq['length']:,} bp\n")

            # 序列预览
            preview = seq["sequence"][:max_preview]
            if len(seq["sequence"]) > max_preview:
                preview += "..."

            lines.append(f"**{self.common_i18n.get('sequence_preview')}**:\n```\n{preview}\n```\n")

            # 语义描述（核心 RAG 信息）
            if seq.get("semantic_description"):
                lines.append(
                    f"**🔬 {self.common_i18n.get('biological_significance')}**:\n{seq['semantic_description']}\n"
                )

            # 根据序列类型显示不同的分析结果
            if seq.get("sequence_type") == "nucleotide":
                # 核酸序列分析
                if seq.get("gc_content") is not None:
                    gc_percent = seq["gc_content"] * 100
                    lines.append(f"**{self.common_i18n.get('gc_content')}**: {gc_percent:.2f}%")

                if seq.get("longest_orf_length", 0) > 0:
                    lines.append(f"**{self.common_i18n.get('longest_orf')}**: {seq['longest_orf_length']} bp")

                if seq.get("cpg_islands"):
                    lines.append(f"**{self.common_i18n.get('cpg_islands')}**: {len(seq['cpg_islands'])}")

                if seq.get("sequence_entropy"):
                    lines.append(f"**{self.common_i18n.get('sequence_complexity')}**: {seq['sequence_entropy']:.2f}")

                lines.append("")

            elif seq.get("sequence_type") == "protein":
                # 蛋白质序列分析
                if seq.get("molecular_weight"):
                    mw = seq["molecular_weight"] / 1000
                    lines.append(f"**{self.common_i18n.get('molecular_weight')}**: {mw:.1f} kDa")

                if seq.get("isoelectric_point"):
                    lines.append(f"**{self.common_i18n.get('isoelectric_point')}**: {seq['isoelectric_point']:.2f}")

                if seq.get("stability_class"):
                    lines.append(f"**{self.common_i18n.get('stability')}**: {seq['stability_class']}")

                if seq.get("gravy") is not None:
                    lines.append(f"**{self.common_i18n.get('hydropathy')}**: {seq['gravy']:.2f}")

                # 二级结构
                ss = seq.get("secondary_structure", {})
                if ss:
                    lines.append(
                        f"**{self.common_i18n.get('secondary_structure')}**: α-helix {ss.get('helix', 0) * 100:.1f}%, β-sheet {ss.get('sheet', 0) * 100:.1f}%"
                    )

                lines.append("")

        return "\n".join(lines)

    def _generate_json(self, sequences: List[Dict], include_full: bool) -> Dict:
        """生成 JSON 格式 - 包含完整的生物信息学分析"""
        json_sequences = []

        for seq in sequences:
            json_seq = {
                "id": seq["id"],
                "name": seq.get("name", seq["id"]),
                "description": seq["description"],
                "length": seq["length"],
                "sequence_type": seq.get("sequence_type", "unknown"),
            }

            # 语义描述（RAG 核心）
            if seq.get("semantic_description"):
                json_seq["semantic_description"] = seq["semantic_description"]

            # 根据序列类型包含不同的分析结果
            if seq.get("sequence_type") == "nucleotide":
                # 核酸序列分析数据
                json_seq["analysis"] = {
                    "gc_content": seq.get("gc_content"),
                    "gc_skew": seq.get("gc_skew"),
                    "at_skew": seq.get("at_skew"),
                    "molecular_weight": seq.get("molecular_weight"),
                    "sequence_entropy": seq.get("sequence_entropy"),
                    "longest_orf_length": seq.get("longest_orf_length", 0),
                    "orf_count": len(seq.get("orfs", [])),
                    "cpg_island_count": len(seq.get("cpg_islands", [])),
                    "repeat_count": len(seq.get("repeats", [])),
                }

                # ORF 详情（前5个）
                if seq.get("orfs"):
                    json_seq["top_orfs"] = seq["orfs"][:5]

                # CpG 岛详情
                if seq.get("cpg_islands"):
                    json_seq["cpg_islands"] = seq["cpg_islands"]

            elif seq.get("sequence_type") == "protein":
                # 蛋白质序列分析数据
                json_seq["analysis"] = {
                    "molecular_weight": seq.get("molecular_weight"),
                    "isoelectric_point": seq.get("isoelectric_point"),
                    "aromaticity": seq.get("aromaticity"),
                    "instability_index": seq.get("instability_index"),
                    "stability_class": seq.get("stability_class"),
                    "gravy": seq.get("gravy"),
                    "charge_at_ph7": seq.get("charge_at_ph7"),
                }

                # 二级结构
                if seq.get("secondary_structure"):
                    json_seq["secondary_structure"] = seq["secondary_structure"]

                # 氨基酸分类
                if seq.get("amino_acid_classes"):
                    json_seq["amino_acid_classes"] = seq["amino_acid_classes"]

                # PTM 位点（前10个）
                if seq.get("ptm_sites"):
                    json_seq["ptm_sites_summary"] = {
                        "phosphorylation_count": len(seq["ptm_sites"].get("phosphorylation", [])),
                        "glycosylation_count": len(seq["ptm_sites"].get("glycosylation", [])),
                        "acetylation_count": len(seq["ptm_sites"].get("acetylation", [])),
                    }

            # 可选：包含完整序列
            if include_full:
                json_seq["sequence"] = seq["sequence"]

            json_sequences.append(json_seq)

        return {
            "sequences": json_sequences,
            "total_count": len(sequences),
            "total_length": sum(s["length"] for s in sequences),
            "analysis_version": "1.0",
            "bioinformatics_features": [
                "sequence_type_detection",
                "gc_content_analysis",
                "orf_prediction",
                "cpg_island_detection",
                "protein_properties",
                "secondary_structure",
                "ptm_site_prediction",
                "semantic_description",
            ],
        }

    def _generate_metadata(self, sequences: List[Dict]) -> Dict:
        """生成元数据"""
        return {
            "format": "FASTA",
            "sequence_count": len(sequences),
            "total_bases": sum(s["length"] for s in sequences),
            "file_type": "biological_sequence",
        }

    def _generate_summary(self, sequences: List[Dict]) -> str:
        """生成摘要"""
        count = len(sequences)
        total_length = sum(s["length"] for s in sequences)

        if count == 0:
            return self.common_i18n.get("empty_file")

        return self.common_i18n.get("sequence_summary", count=count, length=total_length)

    def _analyze_composition(self, sequence: str) -> Dict[str, int]:
        """分析碱基/氨基酸组成"""
        composition = {}
        for char in sequence.upper():
            composition[char] = composition.get(char, 0) + 1
        return composition
