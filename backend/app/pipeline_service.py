from .pipeline_store import PipelineStore
from .pipeline_stages import wu_intake_stage,search_replay_stage,attribution_stage,wu_evaluation_stage
from .pipeline_v19 import v19_evaluation_stage,export_stage


def run_pipeline(root):
    return PipelineStore(root).execute({
        'wu_intake':wu_intake_stage,'search_replay':search_replay_stage,'attribution':attribution_stage,
        'wu_evaluation':wu_evaluation_stage,'v19_evaluation':v19_evaluation_stage,'export':export_stage,
    })
