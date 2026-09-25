"""Associate delivered citation lists by reviewed work identity, not by keywords.

This imports the upstream index's reported relationships. It does not verify the
citing paper, independent authorship, citation context, or a positive judgment.
"""
from __future__ import annotations

import copy
import csv
import json
import re
from datetime import date
from pathlib import Path


_DIRECTORY = '03_成果使用评价与媒体报道/evidence/nmr/'
_CUTOFF_TABLE = '00_项目输入与审计边界/评审时间窗口表.csv'
_SUBJECTS = {
    '10.1038/s41467-026-71315-0': {
        'name': 'NMR-Solver',
        'title': 'NMR-Solver: automated structure elucidation via large-scale spectral matching and physics-guided fragment optimization',
        'child_outcome_ids': ['ACH-014'], 'branch_ids': ['D3.1'],
        'role': '成果相关论文的引用线索',
        'basis': '上游使用评价总表U06、U07明确识别NMR-Solver；结合SpecXMaster核磁解析成果范围，仅用于其核磁解析组件的引用分析。',
    },
    '10.1038/s41597-025-06245-5': {
        'name': 'NMRexp', 'title': 'NMRexp: A database of 3.3 million experimental NMR spectra',
        'child_outcome_ids': ['ACH-014'], 'branch_ids': ['D3.1'],
        'role': '成果相关数据库论文的引用线索',
        'basis': '已确认分支ACH-014明确包含NMRexp数据库；引用材料只涉及该数据库，不扩展到其他数据库或整项系统。',
    },
    '10.1038/s43588-025-00783-z': {
        'name': 'NMRNet',
        'title': 'Toward a unified benchmark and framework for deep learning-based prediction of nuclear magnetic resonance chemical shifts',
        'child_outcome_ids': [], 'branch_ids': ['D2.1'],
        'role': '前期成果的后续引用背景',
        'basis': '上游使用评价总表X02明确将NMRNet列为项目前成果。本清单仅补充前期成果背景，不能计入本期新成果的学术影响。',
    },
}


def normalized_doi(value):
    return re.sub(r'^https?://(?:dx\.)?doi\.org/', '', str(value or '').strip(), flags=re.I).lower()


def citation_subject(table, project_id, package):
    if project_id != 'P02':
        return None
    for doi, definition in _SUBJECTS.items():
        stem = doi.replace('/', '_')
        if table.get('relative_path') != f'{_DIRECTORY}openalex_citing_summary_{stem}.csv':
            continue
        # Check the delivered subject metadata as well as the exact table path.
        metadata_path = Path(package) / _DIRECTORY / f'openalex_summary_{stem}.json'
        try:
            metadata = json.loads(metadata_path.read_text(encoding='utf8'))
        except (OSError, ValueError):
            return None
        if normalized_doi(metadata.get('doi')) != doi or metadata.get('title') != definition['title']:
            return None
        try:
            with (Path(package) / _CUTOFF_TABLE).open(encoding='utf-8-sig', newline='') as stream:
                windows = [row for row in csv.DictReader(stream) if row.get('窗口ID') == 'P02-USE']
            cutoff = windows[0].get('检索截止日', '') if len(windows) == 1 else ''
        except OSError:
            cutoff = ''
        return {**copy.deepcopy(definition), 'doi': doi, 'outcome_ids': ['MAIN-003'],
                'metadata_path': metadata_path.relative_to(package).as_posix(),
                'publication_date': metadata.get('publication_date', ''),
                'author_names': [(a.get('author') or {}).get('display_name') for a in metadata.get('authorships') or []
                                 if (a.get('author') or {}).get('display_name')],
                'review_cutoff': cutoff,
                'cutoff_source': _CUTOFF_TABLE+' · P02-USE' if cutoff else '上游检索截止日待核对'}
    return None


def citation_record_fields(raw, subject):
    citing_doi = normalized_doi(raw.get('doi'))
    citing_id = citing_doi or str(raw.get('openalex_id') or '').strip()
    event_date = str(raw.get('publication_date') or '')
    eligible = bool(citing_id and raw.get('title'))
    reason = '' if eligible else '引用记录缺少论文题名或唯一标识，需补齐后确认对应关系。'
    try:
        outside = date.fromisoformat(event_date) > date.fromisoformat(subject['review_cutoff'])
    except ValueError:
        outside = False
    if outside:
        eligible, reason = False, '发表日期超出该上游模块的检索截止日，暂存为窗口外参考材料。'
    limitation = ('上游引文索引仅报告引用关系；是否自引、是否独立、原文引用语境及是否实际采用均待核验。'
                  '不能据此认定独立复现、真实应用或正面专业认可。发表日期来自上游索引，里程碑适用范围仍须核对。')
    if subject['name'] == 'NMRNet':
        limitation += '被引对象属于项目前基础；后续引用只作背景，不能证明本期新增或计作本期新成果影响。'
    return {
        'title': f"{subject['name']}的引用线索：{raw.get('title') or '题名待补'}",
        'statement': f"上游引文清单将该论文列为引用{subject['name']}的记录。" +
                     f"论文：{raw.get('title') or '待补'}；发表日期：{event_date or '待核对'}。",
        'citation': {'cited_doi': subject['doi'], 'citing_doi': citing_doi,
                     'citing_record_id': citing_id, 'subject_name': subject['name'],
                     'subject_author_names': subject['author_names'],
                     'subject_publication_date': subject['publication_date'],
                     'event_date': event_date, 'review_cutoff': subject['review_cutoff'],
                     'cutoff_source': subject['cutoff_source'],
                     'independence': '待核验', 'citation_context': '待核验',
                     'relationship_status': '上游索引报告，尚未逐篇核对原文'},
        'material_role': subject['role'], 'association_basis': subject['basis'],
        'subject_child_outcome_ids': subject['child_outcome_ids'],
        'limitation': limitation, 'association_eligible': eligible, 'reference_reason': reason,
    }
