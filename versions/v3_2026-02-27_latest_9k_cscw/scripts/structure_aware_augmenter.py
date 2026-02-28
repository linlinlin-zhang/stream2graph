import json
import os
import re
import random
import requests
import time
from pathlib import Path
from hashlib import md5
from datetime import datetime

class StructureAwareAugmenter:
    def __init__(self):
        self.seed_dir = Path('/home/lin-server/pictures/stream2graph_dataset/v3_verified_final')
        self.output_dir = Path('/home/lin-server/pictures/stream2graph_dataset/v5_augmented')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = Path('/home/lin-server/pictures/AUGMENTATION_EXECUTION_LOG.md')
        
        self.domains = {
            'FinTech': ['PaymentGateway', 'FraudDetection', 'LedgerService', 'AuthVault', 'TransactionQueue'],
            'HealthTech': ['DiagnosticEngine', 'PatientRecords', 'EMR_Sync', 'HIPAA_Vault', 'LabAnalyzer'],
            'IoT_Industrial': ['EdgeNode', 'MQTT_Broker', 'ActuatorController', 'TelemetryStream', 'PLC_Logic'],
            'Infra': ['LoadBalancer', 'RedisCache', 'EtcdCluster', 'WorkerNode', 'IngressController'],
            'Education': ['LMS_Portal', 'GradeSync', 'ContentCDN', 'StudentDB', 'ClassroomService'],
            'Groupware': ['KanbanBoard', 'SprintBacklog', 'IssueTracker', 'WikiPage', 'ChatRoom'],
            'CloudNative': ['K8sCluster', 'DockerImage', 'HelmChart', 'ServiceMesh', 'Serverless'],
            'Security': ['Firewall', 'IntrusionDetection', 'ZeroTrust', 'OAuth2', 'Encryption'],
            'Retail': ['Inventory', 'PointOfSale', 'CouponSystem', 'CustomerLoyalty', 'OrderManagement'],
            'Logistics': ['Warehouse', 'DeliveryRoute', 'FleetManagement', 'StockLevel', 'TrackingNumber']
        }
        
        if not self.log_file.exists():
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write("# 数据增强执行日志\n\n| 时间 | 种子ID | 目标领域 | 增广ID | 结果 |\n| --- | --- | --- | --- | --- |\n")

    def check_compilability(self, code):
        try:
            url = 'https://kroki.io/mermaid/svg'
            resp = requests.post(url, data=code.encode('utf-8'), timeout=8)
            return resp.status_code == 200
        except: return False

    def augment_sample(self, sample, domain_name):
        code = sample['code']
        # 更加激进的匹配：包括带括号的和不带括号但看起来像标识符的（可选，这里先增加领域）
        pattern = r'([\[\(\{])([^\]\)\}]*)([\]\)\}])'
        
        dictionary = self.domains[domain_name]
        def replacer(match):
            new_val = f"{domain_name}_" + random.choice(dictionary)
            return f"{match.group(1)}{new_val}{match.group(3)}"
            
        new_code = re.sub(pattern, replacer, code)
        return new_code if new_code != code else None

    def run(self, multiplier=10):
        seeds = list(self.seed_dir.glob('*.json'))
        print(f"--- 启动结构感知型增强 (种子数: {len(seeds)}) ---")
        
        # 统计已有的增广样本
        existing_files = list(self.output_dir.glob('*.json'))
        count = len(existing_files)
        # 目标是总数 6000 增强数据
        target = 6000
        
        print(f"  当前已有增广样本: {count}, 目标增广总数: {target}")
        
        if count >= target:
            print("--- 目标已达成，无需继续增强 ---")
            return

        for seed_path in seeds:
            print(f"  正在处理种子: {seed_path.name}")
            with open(seed_path, 'r', encoding='utf-8') as f:
                seed_data = json.load(f)
            
            available_domains = list(self.domains.keys())
            for i in range(min(multiplier, len(available_domains))):
                domain = available_domains[i]
                aug_id = f"aug_{seed_data['id']}_{domain[:3]}_{i}"
                output_path = self.output_dir / f"{aug_id}.json"
                
                # 如果文件已存在，跳过
                if output_path.exists():
                    continue

                new_code = self.augment_sample(seed_data, domain)
                
                if new_code and self.check_compilability(new_code):
                    new_sample = seed_data.copy()
                    new_sample.update({
                        'id': aug_id, 
                        'code': new_code, 
                        'source': 'augmented_real_structure', 
                        'augmentation_domain': domain, 
                        'seed_id': seed_data['id']
                    })
                    
                    with open(output_path, 'w', encoding='utf-8') as sf:
                        json.dump(new_sample, sf, ensure_ascii=False, indent=2)
                    
                    with open(self.log_file, 'a', encoding='utf-8') as lf:
                        lf.write(f"| {datetime.now().strftime('%H:%M:%S')} | {seed_data['id']} | {domain} | {aug_id} | ✅ |\n")
                    
                    count += 1
                    if count % 20 == 0: 
                        print(f"  进度: {count}/{target} 增广样本已就绪")
                    
                    time.sleep(0.1)
                
                if count >= target: break
            if count >= target: break
        
        print(f"--- 增强任务完成: 最终总数 {count} ---")

if __name__ == "__main__":
    augmenter = StructureAwareAugmenter()
    augmenter.run(multiplier=10)
