"""
StreamVis 数据集质量验证器
用于验证逆向工程生成的数据集质量

验证维度：
1. 数据完整性
2. 格式合规性
3. 逻辑一致性
4. 多样性评估
5. 重复性检测
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""
    record_id: str
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    scores: Dict[str, float]


class DataQualityValidator:
    """数据质量验证器"""

    # 有效的主类型
    VALID_PRIMARY_CATEGORIES = {
        "flowchart", "sequence_diagram", "mind_map", "bar_chart",
        "line_chart", "gantt_chart", "network_graph", "pie_chart", "matrix_quadrant"
    }

    # 有效的场景类型
    VALID_SCENARIO_TYPES = {
        "requirements_elicitation", "design_discussion", "problem_solving",
        "progress_reporting", "decision_making", "knowledge_sharing",
        "planning_scheduling", "analysis_review"
    }

    # 有效的复杂度等级
    VALID_COMPLEXITY_LEVELS = {"simple", "medium", "complex", "highly_complex"}

    # 有效的通信模式
    VALID_COMM_MODES = {
        "synchronous_chat", "asynchronous_chat", "voice_meeting",
        "video_meeting", "email_thread"
    }

    # 有效的意图标记
    VALID_INTENT_MARKERS = {
        "initial_request", "clarification", "elaboration",
        "confirmation", "revision", "conclusion"
    }

    def __init__(self, dataset_dir: str):
        self.dataset_dir = Path(dataset_dir)
        self.validation_results: List[ValidationResult] = []
        self.category_stats: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "valid": 0})

    def validate_all(self) -> Dict[str, any]:
        """验证整个数据集"""
        logger.info("开始数据集质量验证...")

        # 收集所有JSON文件
        json_files = list(self.dataset_dir.rglob("*.json"))
        logger.info(f"找到 {len(json_files)} 个数据文件")

        # 验证每个文件
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    record = json.load(f)

                result = self.validate_record(record, file_path)
                self.validation_results.append(result)

                # 更新统计
                category = record.get("taxonomy", {}).get("primary_category", "unknown")
                self.category_stats[category]["count"] += 1
                if result.is_valid:
                    self.category_stats[category]["valid"] += 1

            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败 {file_path}: {str(e)}")
                self.validation_results.append(ValidationResult(
                    record_id=str(file_path),
                    is_valid=False,
                    errors=[f"JSON解析失败: {str(e)}"],
                    warnings=[],
                    scores={}
                ))
            except Exception as e:
                logger.error(f"验证失败 {file_path}: {str(e)}")

        # 生成验证报告
        report = self._generate_report()

        logger.info("验证完成!")
        return report

    def validate_record(self, record: Dict, file_path: Path) -> ValidationResult:
        """验证单个记录"""
        errors = []
        warnings = []
        scores = {}

        record_id = record.get("record_id", str(file_path))

        # 1. 必需字段检查
        required_fields = [
            "record_id", "timestamp_created", "source", "taxonomy",
            "visual_necessity", "conversation_context", "chart_elements",
            "reverse_engineering", "chart_representation"
        ]

        for field in required_fields:
            if field not in record:
                errors.append(f"缺少必需字段: {field}")

        # 2. 分类学验证
        taxonomy = record.get("taxonomy", {})
        if taxonomy:
            primary = taxonomy.get("primary_category")
            if primary not in self.VALID_PRIMARY_CATEGORIES:
                errors.append(f"无效的主类型: {primary}")

            complexity = taxonomy.get("structural_complexity")
            if complexity not in self.VALID_COMPLEXITY_LEVELS:
                warnings.append(f"未知的复杂度等级: {complexity}")

            semantic_domain = taxonomy.get("semantic_domain", [])
            if not semantic_domain:
                warnings.append("语义领域为空")

        # 3. 视觉必要性验证
        vn = record.get("visual_necessity", {})
        if vn:
            overall = vn.get("overall_score")
            if overall is None or not (0 <= overall <= 10):
                errors.append(f"视觉必要性总分无效: {overall}")

            dims = vn.get("dimensions", {})
            dim_names = ["information_density", "spatial_relationship", "temporal_sequence",
                        "comparative_analysis", "cognitive_load_reduction"]

            for dim in dim_names:
                val = dims.get(dim)
                if val is None or not (0 <= val <= 10):
                    errors.append(f"维度 {dim} 分数无效: {val}")

            justification = vn.get("justification", "")
            if len(justification) < 30:
                warnings.append("视觉必要性理由过短")

            # 计算一致性分数
            if dims:
                avg_dim = sum(dims.get(d, 0) for d in dim_names) / len(dim_names)
                consistency = 1 - abs(overall - avg_dim) / 10 if overall else 0
                scores["dimension_consistency"] = max(0, consistency)

        # 4. 对话重建验证
        re = record.get("reverse_engineering", {})
        if re:
            dialogue = re.get("reconstructed_dialogue", [])

            if len(dialogue) < 3:
                warnings.append(f"对话轮次过少 ({len(dialogue)}轮)")

            # 检查对话质量
            total_length = 0
            speaker_set = set()

            for i, turn in enumerate(dialogue):
                utterance = turn.get("utterance", "")
                total_length += len(utterance)

                if len(utterance) < 5:
                    warnings.append(f"第{i+1}轮对话过短")

                speaker = turn.get("speaker_id")
                if speaker:
                    speaker_set.add(speaker)

                intent = turn.get("intent_marker")
                if intent and intent not in self.VALID_INTENT_MARKERS:
                    warnings.append(f"第{i+1}轮意图标记无效: {intent}")

            if len(speaker_set) < 2:
                warnings.append("对话参与者过少")

            scores["dialogue_quality"] = min(1.0, total_length / 300)

        # 5. 图表元素验证
        ce = record.get("chart_elements", {})
        if ce:
            node_count = ce.get("node_count", 0)
            if node_count <= 0:
                warnings.append("节点数量为0")
            elif node_count > 100:
                warnings.append(f"节点数量异常多 ({node_count})")

        # 6. 意图信号验证
        is_signals = record.get("intent_signals", {})
        if is_signals:
            explicit = is_signals.get("explicit_triggers", [])
            implicit = is_signals.get("implicit_signals", [])

            if not explicit and not implicit:
                warnings.append("未识别到意图信号")

            scores["intent_coverage"] = min(1.0, (len(explicit) + len(implicit)) / 5)

        # 7. 对话场景验证
        context = record.get("conversation_context", {})
        if context:
            scenario = context.get("scenario_type")
            if scenario not in self.VALID_SCENARIO_TYPES:
                warnings.append(f"未知的场景类型: {scenario}")

            comm_mode = context.get("communication_mode")
            if comm_mode not in self.VALID_COMM_MODES:
                warnings.append(f"未知的通信模式: {comm_mode}")

        # 8. 计算综合质量分
        if scores:
            scores["overall_quality"] = sum(scores.values()) / len(scores)

        is_valid = len(errors) == 0

        return ValidationResult(
            record_id=record_id,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            scores=scores
        )

    def _generate_report(self) -> Dict:
        """生成验证报告"""
        total = len(self.validation_results)
        valid = sum(1 for r in self.validation_results if r.is_valid)
        invalid = total - valid

        # 错误统计
        error_counts = defaultdict(int)
        warning_counts = defaultdict(int)

        for result in self.validation_results:
            for error in result.errors:
                error_counts[error] += 1
            for warning in result.warnings:
                warning_counts[warning] += 1

        # 质量分数统计
        quality_scores = [r.scores.get("overall_quality", 0) for r in self.validation_results if r.scores]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_records": total,
                "valid_records": valid,
                "invalid_records": invalid,
                "valid_rate": valid / total if total > 0 else 0,
                "average_quality_score": avg_quality
            },
            "category_distribution": dict(self.category_stats),
            "common_errors": dict(sorted(error_counts.items(), key=lambda x: -x[1])[:10]),
            "common_warnings": dict(sorted(warning_counts.items(), key=lambda x: -x[1])[:10]),
            "quality_distribution": {
                "excellent (>=0.8)": sum(1 for s in quality_scores if s >= 0.8),
                "good (0.6-0.8)": sum(1 for s in quality_scores if 0.6 <= s < 0.8),
                "acceptable (0.4-0.6)": sum(1 for s in quality_scores if 0.4 <= s < 0.6),
                "poor (<0.4)": sum(1 for s in quality_scores if s < 0.4),
            }
        }

        return report

    def save_report(self, report: Dict, output_path: str = "validation_report.json"):
        """保存验证报告"""
        output_file = self.dataset_dir / output_path

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"验证报告已保存到: {output_file}")

    def export_invalid_records(self, output_path: str = "invalid_records.txt"):
        """导出无效记录列表"""
        invalid = [r for r in self.validation_results if not r.is_valid]

        output_file = self.dataset_dir / output_path
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"无效记录列表 (共{len(invalid)}条)\n")
            f.write("="*60 + "\n\n")

            for r in invalid:
                f.write(f"记录ID: {r.record_id}\n")
                f.write(f"错误:\n")
                for e in r.errors:
                    f.write(f"  - {e}\n")
                f.write(f"警告:\n")
                for w in r.warnings:
                    f.write(f"  - {w}\n")
                f.write("\n" + "-"*40 + "\n\n")

        logger.info(f"无效记录列表已保存到: {output_file}")


class DiversityAnalyzer:
    """数据多样性分析器"""

    def __init__(self, dataset_dir: str):
        self.dataset_dir = Path(dataset_dir)

    def analyze(self) -> Dict:
        """分析数据集多样性"""
        logger.info("开始多样性分析...")

        # 收集统计
        category_dist = defaultdict(int)
        complexity_dist = defaultdict(int)
        scenario_dist = defaultdict(int)
        domain_dist = defaultdict(int)

        # 文本特征
        utterance_lengths = []
        vocabulary = set()
        intent_patterns = defaultdict(int)

        json_files = list(self.dataset_dir.rglob("*.json"))

        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    record = json.load(f)

                # 类型分布
                cat = record.get("taxonomy", {}).get("primary_category", "unknown")
                category_dist[cat] += 1

                # 复杂度分布
                comp = record.get("taxonomy", {}).get("structural_complexity", "unknown")
                complexity_dist[comp] += 1

                # 场景分布
                scenario = record.get("conversation_context", {}).get("scenario_type", "unknown")
                scenario_dist[scenario] += 1

                # 领域分布
                domains = record.get("taxonomy", {}).get("semantic_domain", [])
                for d in domains:
                    domain_dist[d] += 1

                # 对话特征
                dialogue = record.get("reverse_engineering", {}).get("reconstructed_dialogue", [])
                for turn in dialogue:
                    utterance = turn.get("utterance", "")
                    utterance_lengths.append(len(utterance))

                    # 提取词汇
                    words = utterance.lower().split()
                    vocabulary.update(words)

                # 意图信号
                signals = record.get("intent_signals", {})
                for trigger in signals.get("explicit_triggers", []):
                    intent_patterns[trigger] += 1

            except Exception as e:
                logger.warning(f"分析文件失败 {file_path}: {str(e)}")

        # 计算多样性指标
        total = len(json_files)

        analysis = {
            "timestamp": datetime.now().isoformat(),
            "category_diversity": {
                "distribution": dict(category_dist),
                "entropy": self._calculate_entropy(category_dist),
                "coverage": len(category_dist) / len(DataQualityValidator.VALID_PRIMARY_CATEGORIES)
            },
            "complexity_diversity": dict(complexity_dist),
            "scenario_diversity": {
                "distribution": dict(scenario_dist),
                "entropy": self._calculate_entropy(scenario_dist)
            },
            "domain_diversity": dict(domain_dist),
            "dialogue_characteristics": {
                "avg_utterance_length": sum(utterance_lengths) / len(utterance_lengths) if utterance_lengths else 0,
                "vocabulary_size": len(vocabulary),
                "utterance_length_std": self._calculate_std(utterance_lengths) if utterance_lengths else 0
            },
            "intent_patterns": dict(sorted(intent_patterns.items(), key=lambda x: -x[1])[:20])
        }

        return analysis

    def _calculate_entropy(self, distribution: Dict) -> float:
        """计算熵（多样性指标）"""
        import math

        total = sum(distribution.values())
        if total == 0:
            return 0

        entropy = 0
        for count in distribution.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)

        return entropy

    def _calculate_std(self, values: List[float]) -> float:
        """计算标准差"""
        import statistics

        if len(values) < 2:
            return 0

        return statistics.stdev(values)

    def save_analysis(self, analysis: Dict, output_path: str = "diversity_analysis.json"):
        """保存分析结果"""
        output_file = self.dataset_dir / output_path

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

        logger.info(f"多样性分析已保存到: {output_file}")


class DuplicateDetector:
    """重复数据检测器"""

    def __init__(self, dataset_dir: str):
        self.dataset_dir = Path(dataset_dir)

    def detect_duplicates(self) -> List[Tuple[str, str, float]]:
        """检测重复/相似的记录"""
        logger.info("开始重复检测...")

        # 计算所有记录的哈希
        records = []
        hashes = {}

        json_files = list(self.dataset_dir.rglob("*.json"))

        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    record = json.load(f)

                # 提取关键字段计算指纹
                fingerprint = self._compute_fingerprint(record)
                hash_val = hashlib.md5(fingerprint.encode()).hexdigest()

                record_id = record.get("record_id", str(file_path))
                records.append((record_id, record, fingerprint))
                hashes[record_id] = hash_val

            except Exception as e:
                logger.warning(f"处理文件失败 {file_path}: {str(e)}")

        # 检测相似性
        duplicates = []
        checked = set()

        for i, (id1, rec1, fp1) in enumerate(records):
            if id1 in checked:
                continue

            for j, (id2, rec2, fp2) in enumerate(records[i+1:], i+1):
                if id2 in checked:
                    continue

                similarity = self._calculate_similarity(fp1, fp2, rec1, rec2)

                if similarity > 0.8:  # 阈值
                    duplicates.append((id1, id2, similarity))
                    checked.add(id2)

        logger.info(f"检测到 {len(duplicates)} 对相似记录")
        return duplicates

    def _compute_fingerprint(self, record: Dict) -> str:
        """计算记录指纹"""
        # 组合关键字段
        parts = []

        # 分类
        tax = record.get("taxonomy", {})
        parts.append(tax.get("primary_category", ""))
        parts.append(tax.get("subcategory", ""))

        # 元素统计
        ce = record.get("chart_elements", {})
        parts.append(str(ce.get("node_count", 0)))
        parts.append(str(ce.get("edge_count", 0)))

        # 对话摘要
        dialogue = record.get("reverse_engineering", {}).get("reconstructed_dialogue", [])
        for turn in dialogue[:2]:  # 只取前2轮
            parts.append(turn.get("utterance", "")[:50])  # 只取前50字符

        return "|".join(parts)

    def _calculate_similarity(self, fp1: str, fp2: str, rec1: Dict, rec2: Dict) -> float:
        """计算两条记录的相似度"""
        # 指纹相同则高度相似
        if fp1 == fp2:
            return 1.0

        # 分类相同增加相似度
        cat1 = rec1.get("taxonomy", {}).get("primary_category")
        cat2 = rec2.get("taxonomy", {}).get("primary_category")

        sim = 0.0

        if cat1 == cat2:
            sim += 0.3

        # 节点数量接近
            nc1 = rec1.get("chart_elements", {}).get("node_count", 0)
            nc2 = rec2.get("chart_elements", {}).get("node_count", 0)

        if max(nc1, nc2) > 0:
            node_sim = 1 - abs(nc1 - nc2) / max(nc1, nc2)
            sim += node_sim * 0.2

        # 对话内容相似度
        dial1 = rec1.get("reverse_engineering", {}).get("reconstructed_dialogue", [])
        dial2 = rec2.get("reverse_engineering", {}).get("reconstructed_dialogue", [])

        if len(dial1) > 0 and len(dial2) > 0:
            text1 = " ".join([t.get("utterance", "") for t in dial1])
            text2 = " ".join([t.get("utterance", "") for t in dial2])

            # 简单的词重叠率
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())

            if words1 and words2:
                overlap = len(words1 & words2) / len(words1 | words2)
                sim += overlap * 0.5

        return sim

    def export_duplicates(self, duplicates: List[Tuple[str, str, float]], output_path: str = "duplicates.txt"):
        """导出重复记录列表"""
        output_file = self.dataset_dir / output_path

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"相似记录列表 (共{len(duplicates)}对)\n")
            f.write("="*60 + "\n\n")

            for id1, id2, sim in sorted(duplicates, key=lambda x: -x[2]):
                f.write(f"记录1: {id1}\n")
                f.write(f"记录2: {id2}\n")
                f.write(f"相似度: {sim:.2%}\n")
                f.write("-"*40 + "\n")

        logger.info(f"重复记录列表已保存到: {output_file}")


def main():
    """主函数"""
    dataset_dir = "./processed_dataset"

    # 1. 质量验证
    validator = DataQualityValidator(dataset_dir)
    report = validator.validate_all()
    validator.save_report(report)
    validator.export_invalid_records()

    # 打印摘要
    print("\n" + "="*60)
    print("质量验证摘要")
    print("="*60)
    print(f"总记录数: {report['summary']['total_records']}")
    print(f"有效记录: {report['summary']['valid_records']}")
    print(f"无效记录: {report['summary']['invalid_records']}")
    print(f"有效率: {report['summary']['valid_rate']:.1%}")
    print(f"平均质量分: {report['summary']['average_quality_score']:.2f}")

    # 2. 多样性分析
    analyzer = DiversityAnalyzer(dataset_dir)
    analysis = analyzer.analyze()
    analyzer.save_analysis(analysis)

    print("\n" + "="*60)
    print("多样性分析摘要")
    print("="*60)
    print(f"类别熵: {analysis['category_diversity']['entropy']:.2f}")
    print(f"场景熵: {analysis['scenario_diversity']['entropy']:.2f}")
    print(f"词汇量: {analysis['dialogue_characteristics']['vocabulary_size']}")

    # 3. 重复检测
    detector = DuplicateDetector(dataset_dir)
    duplicates = detector.detect_duplicates()
    detector.export_duplicates(duplicates)

    print("\n" + "="*60)
    print("重复检测摘要")
    print("="*60)
    print(f"检测到相似记录对: {len(duplicates)}")


if __name__ == "__main__":
    main()
