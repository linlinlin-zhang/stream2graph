"""
StreamVis 训练数据准备脚本
将处理后的数据集转换为模型训练所需的格式

支持的任务：
1. 意图识别 (Intent Detection)
2. 图表生成 (Chart Generation)
3. 图表分类 (Chart Classification)
4. 视觉必要性预测 (Visual Necessity Prediction)
"""

import json
import random
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TrainingDataPreparer:
    """训练数据准备器"""

    # 任务定义
    TASKS = {
        "intent_detection": {
            "description": "从对话中识别是否需要可视化以及图表类型",
            "input_format": "conversation_context",
            "output_format": "intent_label"
        },
        "chart_generation": {
            "description": "根据对话生成图表规范",
            "input_format": "conversation_full",
            "output_format": "chart_specification"
        },
        "chart_classification": {
            "description": "根据图表内容分类",
            "input_format": "chart_specification",
            "output_format": "taxonomy"
        },
        "visual_necessity": {
            "description": "预测视觉展示必要性",
            "input_format": "conversation_context",
            "output_format": "necessity_score"
        },
        "incremental_generation": {
            "description": "增量式图表生成",
            "input_format": "dialogue_turns",
            "output_format": "chart_delta"
        }
    }

    # 数据集划分比例
    SPLIT_RATIOS = {
        "train": 0.7,
        "validation": 0.15,
        "test": 0.15
    }

    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 加载所有数据
        self.records: List[Dict] = []
        self._load_data()

    def _load_data(self):
        """加载所有处理后的数据记录"""
        json_files = list(self.input_dir.rglob("*.json"))

        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    record = json.load(f)
                    # 验证基本结构
                    if self._validate_record(record):
                        self.records.append(record)
            except Exception as e:
                logger.warning(f"加载文件失败 {file_path}: {str(e)}")

        logger.info(f"成功加载 {len(self.records)} 条记录")

    def _validate_record(self, record: Dict) -> bool:
        """验证记录基本结构"""
        required_fields = [
            "record_id", "taxonomy", "visual_necessity",
            "reverse_engineering", "chart_representation"
        ]
        return all(field in record for field in required_fields)

    def _split_data(self, data: List[Dict], stratify_by: str = None) -> Dict[str, List[Dict]]:
        """划分数据集

        Args:
            data: 待划分的数据
            stratify_by: 分层字段（如 primary_category）
        """
        if stratify_by:
            # 分层抽样
            groups = defaultdict(list)
            for item in data:
                key = item.get("taxonomy", {}).get(stratify_by, "unknown")
                groups[key].append(item)

            splits = {"train": [], "validation": [], "test": []}

            for group_data in groups.values():
                random.shuffle(group_data)
                n = len(group_data)

                train_end = int(n * self.SPLIT_RATIOS["train"])
                val_end = train_end + int(n * self.SPLIT_RATIOS["validation"])

                splits["train"].extend(group_data[:train_end])
                splits["validation"].extend(group_data[train_end:val_end])
                splits["test"].extend(group_data[val_end:])

            return splits
        else:
            # 随机划分
            random.shuffle(data)
            n = len(data)

            train_end = int(n * self.SPLIT_RATIOS["train"])
            val_end = train_end + int(n * self.SPLIT_RATIOS["validation"])

            return {
                "train": data[:train_end],
                "validation": data[train_end:val_end],
                "test": data[val_end:]
            }

    def _format_conversation(self, dialogue: List[Dict], max_turns: int = 10) -> str:
        """格式化对话为文本"""
        turns = dialogue[-max_turns:] if len(dialogue) > max_turns else dialogue

        formatted = []
        for turn in turns:
            speaker = turn.get("speaker_id", "Unknown")
            utterance = turn.get("utterance", "")
            formatted.append(f"[{speaker}] {utterance}")

        return "\n".join(formatted)

    def prepare_intent_detection(self) -> Dict[str, List[Dict]]:
        """准备意图识别任务数据"""
        logger.info("准备意图识别任务数据...")

        samples = []

        for record in self.records:
            dialogue = record.get("reverse_engineering", {}).get("reconstructed_dialogue", [])
            if len(dialogue) < 2:
                continue

            # 构建不同长度的上下文样本
            for i in range(2, min(len(dialogue) + 1, 8)):
                context = dialogue[:i]
                input_text = self._format_conversation(context)

                # 标签：是否需要可视化
                taxonomy = record.get("taxonomy", {})
                category = taxonomy.get("primary_category", "unknown")

                # 查找触发点
                turning_points = record.get("reverse_engineering", {}).get("turning_points", [])
                trigger_indices = [tp.get("turn_index") for tp in turning_points

                # 如果在当前上下文中触发了可视化
                should_visualize = i >= min(trigger_indices) if trigger_indices else False

                samples.append({
                    "input": input_text,
                    "output": {
                        "trigger": should_visualize,
                        "category": category if should_visualize else None,
                        "confidence": 1.0 if should_visualize else 0.0
                    },
                    "metadata": {
                        "record_id": record["record_id"],
                        "turn_index": i
                    }
                })

        logger.info(f"意图识别任务: {len(samples)} 个样本")
        return self._split_data(samples)

    def prepare_chart_generation(self) -> Dict[str, List[Dict]]:
        """准备图表生成任务数据"""
        logger.info("准备图表生成任务数据...")

        samples = []

        for record in self.records:
            dialogue = record.get("reverse_engineering", {}).get("reconstructed_dialogue", [])
            if len(dialogue) < 3:
                continue

            input_text = self._format_conversation(dialogue)

            # 输出：图表规范
            chart_spec = record.get("chart_representation", {}).get("specification", "")

            samples.append({
                "instruction": "根据以下对话生成对应的图表：",
                "input": input_text,
                "output": chart_spec,
                "metadata": {
                    "record_id": record["record_id"],
                    "category": record.get("taxonomy", {}).get("primary_category")
                }
            })

        logger.info(f"图表生成任务: {len(samples)} 个样本")
        return self._split_data(samples)

    def prepare_chart_classification(self) -> Dict[str, List[Dict]]:
        """准备图表分类任务数据"""
        logger.info("准备图表分类任务数据...")

        samples = []

        for record in self.records:
            # 输入：图表规范
            chart_spec = record.get("chart_representation", {}).get("specification", "")
            natural_desc = record.get("chart_representation", {}).get("natural_language_description", "")

            input_text = f"图表描述：{natural_desc}\n\n图表规范：\n{chart_spec[:1000]}"

            # 输出：分类信息
            taxonomy = record.get("taxonomy", {})

            samples.append({
                "input": input_text,
                "output": {
                    "primary_category": taxonomy.get("primary_category"),
                    "subcategory": taxonomy.get("subcategory"),
                    "complexity": taxonomy.get("structural_complexity"),
                    "domains": taxonomy.get("semantic_domain", [])
                },
                "metadata": {
                    "record_id": record["record_id"]
                }
            })

        logger.info(f"图表分类任务: {len(samples)} 个样本")
        return self._split_data(samples, stratify_by="primary_category")

    def prepare_visual_necessity(self) -> Dict[str, List[Dict]]:
        """准备视觉必要性预测任务数据"""
        logger.info("准备视觉必要性预测任务数据...")

        samples = []

        for record in self.records:
            dialogue = record.get("reverse_engineering", {}).get("reconstructed_dialogue", [])
            if len(dialogue) < 2:
                continue

            input_text = self._format_conversation(dialogue)

            # 输出：必要性评分
            vn = record.get("visual_necessity", {})

            samples.append({
                "instruction": "评估以下对话内容使用图表进行可视化的必要性：",
                "input": input_text,
                "output": {
                    "overall_score": vn.get("overall_score"),
                    "dimensions": vn.get("dimensions", {}),
                    "justification": vn.get("justification", "")[:500]
                },
                "metadata": {
                    "record_id": record["record_id"]
                }
            })

        logger.info(f"视觉必要性任务: {len(samples)} 个样本")
        return self._split_data(samples)

    def prepare_incremental_generation(self) -> Dict[str, List[Dict]]:
        """准备增量式生成任务数据"""
        logger.info("准备增量式生成任务数据...")

        samples = []

        for record in self.records:
            dialogue = record.get("reverse_engineering", {}).get("reconstructed_dialogue", [])
            evolution = record.get("reverse_engineering", {}).get("incremental_evolution", [])

            if len(dialogue) < 3 or len(evolution) < 2:
                continue

            # 基于演化阶段生成样本
            for i in range(1, min(len(evolution), len(dialogue))):
                context_dialogue = dialogue[:i+1]
                current_stage = evolution[i]
                previous_stage = evolution[i-1] if i > 0 else None

                input_text = self._format_conversation(context_dialogue)

                samples.append({
                    "instruction": "根据对话增量更新图表：",
                    "input": input_text,
                    "previous_state": previous_stage.get("chart_delta") if previous_stage else {},
                    "output": current_stage.get("chart_delta"),
                    "description": current_stage.get("description", ""),
                    "metadata": {
                        "record_id": record["record_id"],
                        "stage": i
                    }
                })

        logger.info(f"增量生成任务: {len(samples)} 个样本")
        return self._split_data(samples)

    def save_task_data(self, task_name: str, data: Dict[str, List[Dict]], format: str = "json"):
        """保存任务数据"""
        task_dir = self.output_dir / task_name
        task_dir.mkdir(exist_ok=True)

        for split_name, split_data in data.items():
            if format == "json":
                output_file = task_dir / f"{split_name}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(split_data, f, ensure_ascii=False, indent=2)

            elif format == "jsonl":
                output_file = task_dir / f"{split_name}.jsonl"
                with open(output_file, 'w', encoding='utf-8') as f:
                    for item in split_data:
                        f.write(json.dumps(item, ensure_ascii=False) + '\n')

            elif format == "alpaca":
                # Alpaca格式（指令微调）
                output_file = task_dir / f"{split_name}_alpaca.json"
                alpaca_data = []
                for item in split_data:
                    alpaca_item = {
                        "instruction": item.get("instruction", ""),
                        "input": item.get("input", ""),
                        "output": json.dumps(item.get("output", {}), ensure_ascii=False) if isinstance(item.get("output"), dict) else str(item.get("output", ""))
                    }
                    alpaca_data.append(alpaca_item)

                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(alpaca_data, f, ensure_ascii=False, indent=2)

            logger.info(f"  {split_name}: {len(split_data)} 条 -> {output_file}")

        # 保存数据信息
        info = {
            "task": task_name,
            "description": self.TASKS.get(task_name, {}).get("description", ""),
            "splits": {k: len(v) for k, v in data.items()},
            "total": sum(len(v) for v in data.values())
        }

        with open(task_dir / "info.json", 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

    def prepare_all(self, format: str = "json"):
        """准备所有任务的数据"""
        logger.info("="*60)
        logger.info("开始准备训练数据")
        logger.info("="*60)

        tasks_to_prepare = [
            ("intent_detection", self.prepare_intent_detection),
            ("chart_generation", self.prepare_chart_generation),
            ("chart_classification", self.prepare_chart_classification),
            ("visual_necessity", self.prepare_visual_necessity),
            ("incremental_generation", self.prepare_incremental_generation)
        ]

        for task_name, prepare_func in tasks_to_prepare:
            try:
                logger.info(f"\n处理任务: {task_name}")
                data = prepare_func()
                self.save_task_data(task_name, data, format=format)
            except Exception as e:
                logger.error(f"准备任务 {task_name} 失败: {str(e)}")
                import traceback
                traceback.print_exc()

        logger.info("\n" + "="*60)
        logger.info("训练数据准备完成")
        logger.info("="*60)


def main():
    parser = argparse.ArgumentParser(description="准备StreamVis训练数据")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="./processed_dataset",
        help="输入数据目录 (默认: ./processed_dataset)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./training_data",
        help="输出目录 (默认: ./training_data)"
    )
    parser.add_argument(
        "--format",
        type=str,
        default="jsonl",
        choices=["json", "jsonl", "alpaca"],
        help="输出格式 (默认: jsonl)"
    )
    parser.add_argument(
        "--task",
        type=str,
        default="all",
        choices=["all", "intent_detection", "chart_generation", "chart_classification", "visual_necessity", "incremental_generation"],
        help="准备特定任务的数据 (默认: all)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子 (默认: 42)"
    )

    args = parser.parse_args()

    # 设置随机种子
    random.seed(args.seed)

    preparer = TrainingDataPreparer(args.input_dir, args.output_dir)

    if args.task == "all":
        preparer.prepare_all(format=args.format)
    else:
        task_map = {
            "intent_detection": preparer.prepare_intent_detection,
            "chart_generation": preparer.prepare_chart_generation,
            "chart_classification": preparer.prepare_chart_classification,
            "visual_necessity": preparer.prepare_visual_necessity,
            "incremental_generation": preparer.prepare_incremental_generation
        }

        prepare_func = task_map.get(args.task)
        if prepare_func:
            data = prepare_func()
            preparer.save_task_data(args.task, data, format=args.format)
        else:
            logger.error(f"未知任务: {args.task}")


if __name__ == "__main__":
    main()
