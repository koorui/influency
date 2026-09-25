"""Adapters receive extracted materials, and return the common evaluation contract.
No model credentials or arbitrary commands are accepted from browser requests.
"""
from typing import Protocol
from .schema import Evaluation


class EvaluationAdapter(Protocol):
    name: str
    version: str
    def evaluate(self, title: str, keywords: list[str], materials: list[dict]) -> Evaluation: ...


class MockAdapter:
    name = 'mock'
    version = 'mock-v1'
    model = 'mock-deterministic'

    def evaluate(self, title, keywords, materials):
        evidence = [{'id': f'E{i+1}', 'title': m['filename'], 'source': '管理员上传材料',
            'material_id': m['id'], 'locator': '提取文本开头（未核验）', 'excerpt': m['text'][:600]}
            for i, m in enumerate(materials)]
        return Evaluation.model_validate({
            'title': title, 'keywords': keywords, 'summary': '演示流程已完成材料读取；正式评价需待 Skill 接入后重新运行。',
            'level': None, 'level_name': '待正式评价', 'is_demo': True,
            'reasons': ['当前由模拟适配器生成，不代表真实评价结论。', '材料仅做文本摘录，尚未核验真实性和外部影响。'],
            'dimensions': [{'topic': '材料完整性', 'claim': f'已提供 {len(materials)} 份材料',
                'assessment': '已完成文本读取，等待正式规则判断。', 'evidence_ids': [x['id'] for x in evidence]}],
            'evidence': evidence, 'follow_ups': [{'title': '接入正式评价 Skill', 'detail': '配置评价规则后重新发起任务，并人工审核证据与等级。', 'kind': 'material'}]
        })


def get_adapter(name):
    if name == 'mock':
        return MockAdapter()
    if name == 'codex':
        from .codex_adapter import CodexAdapter
        return CodexAdapter()
    raise ValueError('不支持的评价适配器')
