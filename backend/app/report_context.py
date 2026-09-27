"""Expose stored source metadata without manufacturing historical facts."""
import json
from .project_service import stage_output


def with_source_context(payload,job):
    intake=stage_output(job,'wu_intake').get('intake',{})
    search=stage_output(job,'search_replay')
    sources={}
    for ev in search.get('replay',{}).get('evidence',[]):
        try:source=json.loads(ev['text'])
        except (ValueError,TypeError,KeyError):continue
        if isinstance(source,dict):sources[ev['id']]=source
    evidence=[]
    for ev in payload.get('evidence',[]):
        source=sources.get(ev['id'],{})
        evidence.append({**ev,'source_context':{k:source[k] for k in
            ('event_date','first_public_date','accessed_at','access_status','relationship') if source.get(k)},
            'time_eligibility':search.get('time_audit',{}).get('source_status',{}).get(ev['id'])})
    primary=next((o for o in intake.get('evaluation_objects',[]) if o['id']==intake.get('primary_object_id')),None)
    return {**payload,'evidence':evidence,'outcome_object':primary,
        'evaluation_started_at':job.started_at.isoformat() if job.started_at else None}
