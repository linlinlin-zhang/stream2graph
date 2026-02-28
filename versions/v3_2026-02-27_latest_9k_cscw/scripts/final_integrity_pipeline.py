import json
import os
import re
import requests
import time
from pathlib import Path
from hashlib import md5
from datetime import datetime
from collections import Counter

class FinalIntegrityPipeline:
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
            'licenses': Counter()
        }
        
        # 初始化日志文件
        if not self.log_file.exists():
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write("# Stream2Graph 数据完整性校验日志\n\n")
                f.write(f"生成时间: {datetime.now().isoformat()}\n\n")
                f.write("| 时间 | 样本ID | 结果 | 原因 |\n| --- | --- | --- | --- |\n")

    def log_to_file(self, sample_id, status, reason=""):
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"| {datetime.now().strftime('%H:%M:%S')} | {sample_id} | {status} | {reason} |\n")

    def check_compilability(self, code):
        try:
            url = 'https://kroki.io/mermaid/svg'
            resp = requests.post(url, data=code.encode('utf-8'), timeout=10)
            return resp.status_code == 200
        except: return False

    def run(self, limit=500):
        print(f"--- 启动终极完整性流水线 (批次容量: {limit}) ---")
        
        all_samples = {}
        for d in [self.base_dir / 'final_100percent_real', self.base_dir / 'high_quality_subset', self.base_dir / 'real_data_raw']:
            if not d.exists(): continue
            for f in d.rglob('*.json'):
                if f.name.startswith('index') or 'v2_cleaned' in str(f) or 'v3_verified_final' in str(f): continue
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        if 'code' in data:
                            chash = md5(data['code'].encode()).hexdigest()
                            if chash not in all_samples:
                                all_samples[chash] = data
                except: continue

        print(f"待处理唯一样本总数: {len(all_samples)}")
        
        count = 0
        for chash, sample in all_samples.items():
            if count >= limit: break
            
            sid = sample['id']
            if (self.output_dir / f"{sid}.json").exists():
                continue
                
            self.stats['scanned'] += 1
            if not self.check_compilability(sample['code']):
                self.stats['rejected_compilation'] += 1
                self.log_to_file(sid, "REJECTED", "Compilation Failed")
                continue
            
            self.stats['compilation_passed'] += 1
            has_source = sample.get('source_url') or sample.get('github_repo')
            has_license = sample.get('license') not in self.invalid_licenses
            
            if has_source and has_license:
                self.stats['compliance_passed'] += 1
                self.stats['types'][sample.get('diagram_type', 'unknown')] += 1
                self.stats['licenses'][sample.get('license')] += 1
                with open(self.output_dir / f"{sid}.json", 'w', encoding='utf-8') as sf:
                    json.dump(sample, sf, ensure_ascii=False, indent=2)
                self.log_to_file(sid, "PASSED", "Compilable & Licensed")
                count += 1
            else:
                self.stats['rejected_license'] += 1
                self.log_to_file(sid, "REJECTED", "Missing Source or License")
            
            if count % 20 == 0:
                print(f"  进度: {count}/{limit}")
            time.sleep(0.3)

        self.generate_final_report()

    def generate_final_report(self):
        with open(self.report_file, 'w', encoding='utf-8') as f:
            f.write("# Stream2Graph 黄金数据集统计报告\n\n")
            f.write(f"**更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## 1. 审计概况\n")
            f.write(f"- 扫描样本总数: {self.stats['scanned']}\n")
            f.write(f"- 编译通过数: {self.stats['compilation_passed']}\n")
            f.write(f"- 最终录入黄金池: {self.stats['compliance_passed']}\n")
            f.write(f"- 编译未通过剔除: {self.stats['rejected_compilation']}\n")
            f.write(f"- 合规性未通过剔除: {self.stats['rejected_license']}\n\n")
            f.write("## 2. 授权分布\n| 许可证 | 数量 |\n| --- | --- |\n")
            for k, v in self.stats['licenses'].most_common():
                f.write(f"| {k} | {v} |\n")
            f.write("\n## 3. 图表类型分布\n| 类型 | 数量 |\n| --- | --- |\n")
            for k, v in self.stats['types'].most_common():
                f.write(f"| {k} | {v} |\n")
        print(f"\n报告已更新: {self.report_file}")

if __name__ == "__main__":
    pipeline = FinalIntegrityPipeline()
    pipeline.run(limit=200) # 减小批次以确保报告快速生成
