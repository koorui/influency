"""Ask the CLI to correct invalid Search output without repeating public research."""
import json
from .pipeline_model import execute_json_stage
from .pipeline_store import atomic_json
from .search_skill_loader import SEARCH_SKILL_ROOT


def assess_with_repair(folder,model,payload,instruction,finalize,max_calls=3):
    atomic_json(folder/'synthesis-input.json',payload)
    previous=None
    feedback=None
    # A resumed stage can continue the last synthesis against identical evidence.
    attempts=sorted((p for p in folder.parent.glob('attempt-*') if p!=folder),
                    key=lambda p:int(p.name.split('-')[-1]),reverse=True)
    for attempt in attempts:
        request=attempt/'synthesis-input.json'
        if not request.exists():request=attempt/'input.json'
        try:
            if json.loads(request.read_text(encoding='utf-8'))!=payload:continue
            responses=sorted(attempt.glob('synthesis-*/response.json'),reverse=True)
            responses=responses or [attempt/'response.json']
            previous=json.loads(responses[0].read_text(encoding='utf-8-sig'))
        except (OSError,ValueError,IndexError):continue
        try:
            value=finalize(model.model_validate(previous))
            atomic_json(folder/'synthesis-reuse.json',{'from_attempt':attempt.name})
            return value
        except ValueError as exc:
            feedback=str(exc)
            atomic_json(folder/'previous-validation-error.json',{'from_attempt':attempt.name,'error':feedback})
        break
    for number in range(1,max_calls+1):
        run=folder/f'synthesis-{number}';run.mkdir()
        request=payload
        prompt=instruction
        if previous is not None and feedback:
            request={**payload,'correction':{'previous_response':previous,'validation_error':feedback}}
            prompt+=(' Your previous synthesis failed validation. Read correction.validation_error and the exact '
                     'previous_response. Recheck every source reference against your sources list, candidate IDs and '
                     'source-specific quote excerpts, then return the COMPLETE corrected report. '
                     'Preserve supported analysis. Supply an omitted source record only from actual collected evidence; '
                     'change a conclusion or reference only when justified by that evidence. Do not invent records, '
                     'blindly remove citations, weaken validation, or turn unrelated sources into project proof.')
        try:
            analysis=execute_json_stage(run,model,request,prompt,skill_root=SEARCH_SKILL_ROOT,
                                        timeout=900,live_search=False,inline_input=True)
            return finalize(analysis)
        except ValueError as exc:
            feedback=str(exc)
            atomic_json(run/'validation-error.json',{'error':feedback})
            response=run/'response.json'
            # Timeouts and process failures need operational recovery, not JSON correction.
            if not response.is_file():raise
            try:previous=json.loads(response.read_text(encoding='utf-8-sig'))
            except ValueError:previous={'invalid_json':response.read_text(encoding='utf-8-sig')}
            if number==max_calls:raise
