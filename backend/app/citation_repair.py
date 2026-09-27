"""One bounded source-text correction; source identities and scientific fields freeze."""
import re
from pydantic import Field
from .schema import StrictModel
from .pipeline_contracts import IntakeEvidence
from .pipeline_model import execute_json_stage
from .pipeline_store import atomic_json


class CitationRepair(StrictModel):
    evidence: list[IntakeEvidence]=Field(min_length=1)


def repair_intake_citations(value,materials,invalid,folder):
    root=folder/'citation-repair';root.mkdir()
    (root/'materials').mkdir()
    requested=[e for e in value.evidence if e.id in invalid]
    material_ids={e.material_id for e in requested}
    records=[]
    for i,m in enumerate(materials):
        if m['id'] not in material_ids:continue
        file=f'materials/{i+1:03d}.txt';(root/file).write_text(m['text'],encoding='utf-8')
        records.append({'id':m['id'],'filename':m['filename'],'text_file':file})
    repair=execute_json_stage(root,CitationRepair,{'outcome':value.canonical_name,'materials':records,
        'candidate_citations':[e.model_dump() for e in requested]},
        'Correct ONLY the listed invalid source quotations using their bound original UTF-8 material files. '
        'A quotation must be one exact contiguous passage. Previously joined paragraphs, omitted figure text, '
        'reordered slide labels and changed punctuation are not literal quotes. Read the original section. '
        'Choose a contiguous span covering the same cited factual claims; include intervening source text if necessary. '
        'Do not invent, summarize, drop a factual qualifier or move a citation to another document. '
        'Preserve each requested evidence id and material_id, correct quote and physical-page/line locator only. '
        'Return exactly the requested citation IDs. Never add a citation or a grade. If the source cannot support the candidate, '
        'retain the candidate so validation fails rather than fabricate a substitute.',inline_input=True)
    original={e.id:e for e in requested};fixed={e.id:e for e in repair.evidence}
    if len(fixed)!=len(repair.evidence) or set(fixed)!=set(original):raise ValueError('引文修复改变了来源编号集合')
    texts={m['id']:re.sub(r'\s+','',m['text']) for m in materials}
    for key,e in fixed.items():
        if e.material_id!=original[key].material_id or not e.quote.strip() or re.sub(r'\s+','',e.quote) not in texts.get(e.material_id,''):
            raise ValueError(f'引文 {key} 修复后仍不对应绑定材料，不能交付')
    result=value.model_copy(deep=True)
    result.evidence=[fixed.get(e.id,e) for e in result.evidence]
    atomic_json(folder/'citation-repair-receipt.json',{'raw_response_preserved':True,
        'source_identity_changed':False,'scientific_fields_changed':False,
        'corrections':[{'evidence_id':key,'before':original[key].model_dump(),'after':fixed[key].model_dump()} for key in fixed]})
    return result
