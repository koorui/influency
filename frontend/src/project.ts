export type Project = {id:string;name:string;code:string;material_count?:number;ticket_count?:number;report_count?:number;search_boundary?:{project_start_date:string;review_cutoff:string;cutoff_basis:string}|null}
export type Step = {name:string;status:string}
export type RequestRow = {id:string;project_id:string;project_name:string;outcome_name:string;status:string;steps:Step[];result_id:string|null;pipeline_id:string|null;created_at:string;note:string;revision?:number;error?:string;received_at?:string|null;accepted_at?:string|null}
export const states:Record<string,string>={pending_acceptance:'待受理',awaiting_acceptance:'待验收',accepted:'已验收',pending:'未开始',queued:'排队中',running:'处理中',processing:'处理中',waiting:'待补充',failed:'处理异常',succeeded:'已完成',published:'已完成',cancelled:'已取消'}
