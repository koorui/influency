<script setup lang="ts">
import ReportText from "./ReportText.vue"
import {computed, ref, watch} from 'vue'
import {ElMessage} from 'element-plus'
import {api, post, formatDate} from '../api'
import type {Evaluation} from '../types'
const props=defineProps<{reportId:string,value:Evaluation}>()
const emit=defineEmits<{changed:[]}>()
const review=ref<any>(null),error=ref(''),busy=ref(false),task=ref<any>(null),body=ref(''),deadline=ref(''),taskStatus=ref('draft'),resolution=ref<string[]>([])
const reviewer=ref(''),factId=ref(''),verdict=ref(''),reason=ref(''),refs=ref<string[]>([]),reviewOpen=ref(false)
const history=ref<any[]>([]),historyOpen=ref(false),rerunOpen=ref(false),changeReason=ref('additional_evidence'),description=ref(''),requestKey=ref(''),rerun=ref<any>(null)
const rerunPreview=ref<any>(null)
const facts=computed(()=>props.value.fact_ledger?.impact_facts || [])
const taskSource=computed(()=>props.value.follow_ups[Number((task.value?.source_key||'').replace('suggestion-',''))])
const taskFacts=computed(()=>facts.value.filter((f:any)=>taskSource.value?.fact_ids?.includes(f.id)))
const dirty=computed(()=>task.value && (body.value!==task.value.body || deadline.value!==(task.value.deadline||'') || taskStatus.value!==task.value.status || JSON.stringify(resolution.value)!==JSON.stringify(task.value.resolution_refs||[])))
async function load(){try{review.value=await api('/reports/'+props.reportId+'/review');error.value=''}catch(e){error.value=(e as Error).message}}
watch(()=>props.reportId,()=>{task.value=null;rerun.value=null;void load()},{immediate:true})
async function act(fn:()=>Promise<void>){busy.value=true;error.value='';try{await fn()}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
async function openTask(index:number){await act(async()=>{const t=await post<any>('/reports/'+props.reportId+'/followups',{revision:review.value.revision,source_index:index});task.value=t;body.value=t.body;deadline.value=t.deadline||'';taskStatus.value=t.status;resolution.value=t.resolution_refs||[];await load()})}
async function save(){await act(async()=>{task.value=await post('/reports/'+props.reportId+'/followups/'+task.value.id,{result_revision:review.value.revision,revision:task.value.revision,body:body.value,status:taskStatus.value,deadline:deadline.value||null,resolution_refs:resolution.value});ElMessage.success('草稿已保存');await load()})}
async function copy(){try{await navigator.clipboard.writeText(body.value);ElMessage.success('已复制当前文案')}catch{ElMessage.error('复制失败，请手动选择文案')}}
function download(){const url=URL.createObjectURL(new Blob([body.value],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='核验任务.txt';a.click();URL.revokeObjectURL(url)}
async function assign(){await act(async()=>{review.value=await post('/reports/'+props.reportId+'/reviewers',{revision:review.value.revision,username:reviewer.value,active:true});reviewer.value='';ElMessage.success('已指定审阅人')})}
async function revoke(username:string){await act(async()=>{review.value=await post('/reports/'+props.reportId+'/reviewers',{revision:review.value.revision,username,active:false});ElMessage.success('已取消后续审阅权限，历史意见保留')})}
async function decide(){await act(async()=>{review.value=await post('/reports/'+props.reportId+'/decisions',{revision:review.value.revision,fact_id:factId.value,verdict:verdict.value,reason:reason.value,evidence_ids:refs.value});reason.value='';verdict.value='';refs.value=[];ElMessage.success('复核意见已保存');emit('changed')})}
async function showHistory(){await act(async()=>{history.value=await api('/reports/'+props.reportId+'/history');historyOpen.value=true})}
async function openRerun(){await act(async()=>{rerunPreview.value=await api('/reports/'+props.reportId+'/reevaluation-preview');requestKey.value=crypto.randomUUID();rerunOpen.value=true})}
async function recheck(){await act(async()=>{rerun.value=await post('/reports/'+props.reportId+'/reevaluate',{revision:review.value.revision,request_key:requestKey.value,change_reason:changeReason.value,description:description.value,expected_inputs:rerunPreview.value?.expected_inputs});rerunOpen.value=false;ElMessage.success('已创建核验工单，等待受理')})}
const kinds:Record<string,string>={material:'补已有材料',expert:'专业复核',improvement:'试用与观察',maintenance:'维护'}
const taskStates:Record<string,string>={draft:'草稿',open:'待处理',submitted:'已提交',resolved:'已解决',cancelled:'已取消'}
function savedTask(index:number){return review.value?.tasks.find((t:any)=>t.source_key==='suggestion-'+index)}
</script>
<template>
  <section class="review-tasks">
    <el-alert v-if="error" :title="error" type="error" :closable="false"/>
    <div v-for="(item,i) in value.follow_ups" :key="i" class="task-row"><div><small>{{kinds[item.kind]||item.kind}} · {{taskStates[savedTask(i)?.status]||'尚未创建'}}</small><h3>{{item.title}}</h3><ReportText :text="item.detail" :limit="140"/><small v-if="savedTask(i)">草稿第 {{savedTask(i).revision}} 版 · {{formatDate(savedTask(i).updated_at)}}</small></div><el-button :disabled="!review" :loading="busy" @click="openTask(i)">查看任务</el-button></div>
    <p v-if="!value.follow_ups.length">当前无必须补充事项。</p>
    <div class="review-actions"><a :href="`/api/reports/${reportId}/export`" class="export-link">导出当前报告</a><el-button :disabled="!review" @click="reviewOpen=true">专家复核</el-button><el-button @click="showHistory">评价历史</el-button><el-button type="primary" :disabled="!review||!!rerun" @click="openRerun">重新核验</el-button></div>
    <p v-if="rerun">核验工单已创建：{{rerun.outcome_name}} · 等待管理员受理。可在“我的申请”查看进度；原报告继续保留。</p>
    <el-dialog :model-value="!!task" @close="task=null" title="核验任务与草稿" width="min(760px,94vw)" :close-on-click-modal="!dirty" :close-on-press-escape="!dirty" :show-close="!dirty">
      <template v-if="task"><h3>{{task.title}}</h3><p v-for="f in taskFacts" :key="f.id">关联事实：{{f.fact_text}}</p><p v-if="dirty" class="pending-note">有尚未保存的修改。请保存，或明确放弃后关闭。</p>
        <el-input v-model="body" type="textarea" :rows="12" aria-label="任务文案"/>
        <div class="task-fields"><label>截止日期（可不填）<input v-model="deadline" type="date"></label><el-select v-model="taskStatus" aria-label="任务状态"><el-option v-for="(label,key) in {draft:'草稿',open:'待处理',submitted:'已提交',resolved:'已解决',cancelled:'已取消'}" :key="key" :label="label" :value="key"/></el-select></div>
        <el-select v-if="taskStatus==='resolved'" v-model="resolution" multiple placeholder="选择解决依据" class="full"><el-option v-for="ev in value.evidence" :key="ev.id" :label="ev.title" :value="ev.id"/><el-option v-for="d in review?.decisions||[]" :key="d.id" :label="'专家意见：'+d.reason" :value="d.id"/></el-select>
        <details><summary>预览当前文案</summary><pre>{{body}}</pre></details>
        <div class="review-actions"><el-button :loading="busy" type="primary" @click="save">保存草稿</el-button><el-button @click="copy">复制文案</el-button><el-button @click="download">导出发送稿</el-button><el-button v-if="dirty" @click="task=null">放弃修改并关闭</el-button></div><p class="muted">复制和导出采用当前编辑内容，不会自动发送消息。</p>
      </template>
    </el-dialog>
    <el-dialog v-model="reviewOpen" title="专家事实复核" width="min(800px,94vw)">
      <template v-if="review"><p>复核绑定当前报告第 {{review.revision}} 版。确认某个事实不等于确认整份报告。</p>
        <div v-if="review.can_assign" class="review-actions"><el-input v-model="reviewer" placeholder="已有项目访问权限的审阅账号" aria-label="审阅账号"/><el-button :loading="busy" :disabled="!reviewer.trim()" @click="assign">指定审阅人</el-button></div>
        <p>当前审阅人：{{review.assignments.filter((a:any)=>a.active).map((a:any)=>a.username).join('、')||'尚未指定'}}</p>
        <div v-if="review.can_assign" class="review-actions"><el-button v-for="a in review.assignments.filter((a:any)=>a.active)" :key="a.user_id" size="small" :loading="busy" @click="revoke(a.username)">取消 {{a.username}} 的审阅权限</el-button></div>
        <template v-if="review.can_review">
          <el-select v-model="factId" placeholder="选择需要复核的事实" class="full"><el-option v-for="f in facts" :key="f.id" :label="f.fact_text" :value="f.id"/><el-option label="当前报告整体复核" value="__overall__"/></el-select>
          <p v-if="factId!=='__overall__'">{{facts.find((f:any)=>f.id===factId)?.notes}}</p>
          <el-radio-group v-model="verdict"><el-radio value="confirmed">有依据确认</el-radio><el-radio value="partial">部分支持</el-radio><el-radio value="insufficient">证据不足</el-radio><el-radio value="conflict">存在冲突</el-radio></el-radio-group>
          <el-input v-model="reason" type="textarea" :rows="4" placeholder="说明事实、适用条件、边界与判断理由" aria-label="专家意见"/>
          <el-select v-model="refs" multiple placeholder="选择所依据的来源" class="full"><el-option v-for="ev in value.evidence" :key="ev.id" :label="ev.title" :value="ev.id"/></el-select>
          <el-button type="primary" :loading="busy" :disabled="!factId||!verdict||!reason.trim()" @click="decide">提交复核意见</el-button>
        </template><p v-else class="muted">只有指定审阅人可以提交复核意见。</p>
        <el-alert v-if="error" :title="error" type="error" :closable="false"/>
        <div v-for="d in review.decisions" :key="d.id" class="decision"><strong>{{d.fact_id==='__overall__'?'报告整体复核':facts.find((f:any)=>f.id===d.fact_id)?.fact_text||'历史事实意见'}}</strong><p>{{({confirmed:'有依据确认',partial:'部分支持',insufficient:'证据不足',conflict:'存在冲突'} as Record<string,string>)[d.verdict]}}：{{d.reason}}</p><small>{{formatDate(d.created_at)}}</small></div>
      </template>
    </el-dialog>
    <el-dialog v-model="historyOpen" title="评价历史" width="min(700px,94vw)"><div v-for="h in history" :key="h.id" class="decision"><RouterLink :to="'/results/'+h.id">{{h.title}} · {{h.level?'L'+h.level:'待核验'}}</RouterLink><p>评价截止：{{h.evaluation_cutoff||'历史记录未提供'}} · {{h.rule_version||'历史规则'}}</p><p v-if="h.difference_to_current&&!h.difference_to_current.is_current">与正在查看的报告相比：等级{{h.difference_to_current.level_changed?'有变化':'相同'}}；{{h.difference_to_current.dimension_changes.length}} 个维度档位、{{h.difference_to_current.changed_facts}} 条事实记录有变化；引用来源 {{h.difference_to_current.sources_before}} → {{h.difference_to_current.sources_current}} 条。<small>事实按编号对照，文字或引用变化也计入，不等于新增实际影响。</small></p><small>{{h.change_reason||'首次记录'}} · {{formatDate(h.published_at)}}</small></div></el-dialog>
    <el-dialog v-model="rerunOpen" title="重新核验" width="min(640px,94vw)"><p>保持当前成果对象，以项目当前选用材料和评价截止日创建新工单。新增材料请先在项目材料中提交。</p><div v-if="rerunPreview" class="rerun-preview"><p><strong>主评价对象：</strong>{{rerunPreview.primary_object?.name||'历史记录缺少冻结对象，需另行提交'}}</p><p>原截止日：{{rerunPreview.previous_cutoff||'未记录'}} → 本次截止日：{{rerunPreview.expected_inputs.search_boundary?.review_cutoff||'未设置'}}</p><strong>本次选用 {{rerunPreview.materials.length}} 份材料</strong><ul><li v-for="m in rerunPreview.materials" :key="m.id">{{m.filename}}</li></ul><p class="muted">提交时再次核对材料与日期；若已变化，需重新打开本预览。</p></div><el-select v-model="changeReason" class="full"><el-option v-for="(label,key) in {additional_evidence:'补充已有事实的证据',new_facts:'出现新的实际作用',correction:'纠正事实或判断',rule_change:'按更新后的规则审阅'}" :key="key" :label="label" :value="key"/></el-select><el-input v-model="description" type="textarea" :rows="4" placeholder="说明发生了什么变化，需重点核验什么"/><el-button type="primary" :loading="busy" :disabled="!rerunPreview?.primary_object||!rerunPreview?.materials.length" @click="recheck">创建核验工单</el-button></el-dialog>
  </section>
</template>
<style scoped>
.task-row{display:flex;gap:20px;align-items:center;justify-content:space-between;padding:18px 0;border-bottom:1px solid #e3ebf3}.task-row h3{margin:5px 0;font-size:16px}.task-row p{margin:0;color:#526777}.task-row small{color:#497299}.review-actions,.task-fields{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}.review-actions .el-input{flex:1;min-width:180px}.task-fields input{display:block;padding:8px;border:1px solid #d6e1eb;border-radius:4px}.full{width:100%;margin:12px 0}.decision{padding:16px 0;border-top:1px solid #dce6ef}.pending-note{color:#996217}pre{white-space:pre-wrap;overflow-wrap:anywhere}.review-tasks{overflow-wrap:anywhere}.el-radio-group{margin:14px 0}
@media(max-width:700px){.task-row{align-items:flex-start;flex-direction:column;gap:12px}.task-row>div{min-width:0;width:100%}}
.rerun-preview{padding:16px;background:#f3f7fa;border-radius:8px;margin:16px 0}.rerun-preview ul{max-height:180px;overflow:auto;padding-left:20px}
</style>
