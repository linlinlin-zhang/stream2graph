import json
import os
import requests
import time
from pathlib import Path
from hashlib import md5
from datetime import datetime
from collections import Counter

class MasterIntegrityPipeline:
    """终极完整性流水线：全量处理所有存量数据并生成学术报告"""
    def __init__(self):
        self.base_dir = Path('/home/lin-server/pictures/stream2graph_dataset')
        self.output_dir = self.base_dir / 'v3_verified_final'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = Path('/home/lin-server/pictures/INTEGRITY_CHECK_LOG.md')
        self.report_file = Path('/home/lin-server/pictures/FINAL_GOLDEN_DATASET_SUMMARY.md')
        
        self.invalid_licenses = ['none', 'error', 'unknown', 'rate_limited']
        self.stats = {
            'scanned': 0,
            'compilation_passed': 0,
            'compliance_passed': 0,
            'rejected_compilation': 0,
            'rejected_license': 0,
            'types': Counter(),
            'licenses': Counter(),
            'sources': Counter()
        }

    def log_to_file(self, sample_id, status, reason="", repo=""):
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"| {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {sample_id} | {status} | {reason} | {repo} |
")

    def check_compilability(self, code):
        try:
            url = 'https://kroki.io/mermaid/svg'
            resp = requests.post(url, data=code.encode('utf-8'), timeout=10)
            return resp.status_code == 200
        except: return False

    def run_full_purge(self):
        print("--- 启动全量存量数据提纯 (Phase 1) ---")
        
        # 预先扫描所有唯一的代码样本
        all_samples = {}
        for d in [self.base_dir / 'final_100percent_real', self.base_dir / 'high_quality_subset', self.base_dir / 'real_data_raw']:
            if not d.exists(): continue
            for f in d.rglob('*.json'):
                if f.name.startswith('index') or 'v3_verified_final' in str(f): continue
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        if 'code' in data:
                            chash = md5(data['code'].encode()).hexdigest()
                            if chash not in all_samples:
                                all_samples[chash] = data
                except: continue

        total_unique = len(all_samples)
        print(f"待处理唯一样本总数: {total_unique}")

        processed = 0
        for chash, sample in all_samples.items():
            sid = sample['id']
            # 跳过已存在的
            if (self.output_dir / f"{sid}.json").exists():
                processed += 1
                continue
            
            self.stats['scanned'] += 1
            
            # 1. 编译验证
            if not self.check_compilability(sample['code']):
                self.stats['rejected_compilation'] += 1
                self.log_to_file(sid, "REJECTED", "Compile Fail", sample.get('github_repo', 'N/A'))
                continue
            
            self.stats['compilation_passed'] += 1
            
            # 2. 合规性验证
            has_source = sample.get('source_url') or sample.get('github_repo')
            has_license = sample.get('license') not in self.invalid_licenses
            
            if has_source and has_license:
                self.stats['compliance_passed'] += 1
                self.stats['types'][sample.get('diagram_type', 'unknown')] += 1
                self.stats['licenses'][sample.get('license')] += 1
                self.stats['sources'][sample.get('source')] += 1
                
                with open(self.output_dir / f"{sid}.json", 'w', encoding='utf-8') as sf:
                    json.dump(sample, sf, ensure_ascii=False, indent=2)
                
                self.log_to_file(sid, "PASSED", "Verified", sample.get('github_repo', 'N/A'))
            else:
                self.stats['rejected_license'] += 1
                self.log_to_file(sid, "REJECTED", "License/Source Missing", sample.get('github_repo', 'N/A'))
            
            processed += 1
            if processed % 50 == 0:
                print(f"  进度: {processed}/{total_unique} | 当前黄金池: {self.stats['compliance_passed']}")
                self.generate_report() # 实时刷新报告
            
            time.sleep(0.1) # 维持验证速率

        self.generate_report()
        print(f"
--- 第一阶段完成！最终黄金池规模: {len(list(self.output_dir.glob('*.json')))} ---")

    def generate_report(self):
        current_golden = len(list(self.output_dir.glob('*.json')))
        with open(self.report_file, 'w', encoding='utf-8') as f:
            f.write("# Stream2Graph 黄金数据集全量审计报告 (8,000 目标)

")
            f.write(f"**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

")
            f.write(f"## 1. 核心进度指标
")
            f.write(f"- **当前黄金样本总数**: {current_golden}
")
            f.write(f"- **距离 8,000 目标缺口**: {8000 - current_golden}
")
            f.write(f"- **总体合规率**: {current_golden / (self.stats['scanned'] or 1) * 100:.1f}%

")
            
            f.write("## 2. 详细统计
")
            f.write(f"- 已扫描原始样本: {self.stats['scanned']}
")
            f.write(f"- 编译失败剔除: {self.stats['rejected_compilation']}
")
            f.write(f"- 授权不明剔除: {self.stats['rejected_license']}

")
            
            f.write("## 3. 已通过样本的许可证分布
| 许可证 | 数量 |
| --- | --- |
")
            for k, v in self.stats['licenses'].most_common():
                f.write(f"| {k} | {v} |
")
                
            f.write("
## 4. 图表类型分布
| 类型 | 数量 |
| --- | --- |
")
            for k, v in self.stats['types'].most_common():
                f.write(f"| {k} | {v} |
")

if __name__ == "__main__":
    pipeline = MasterIntegrityPipeline()
    pipeline.run_full_purge()
