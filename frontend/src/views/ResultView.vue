<script setup lang="ts">
import {ref,watch} from 'vue'
import {useRoute} from 'vue-router'
import {api,post,formatDate} from '../api'
import {ElMessageBox,ElMessage} from 'element-plus'
import EvaluationReport from '../components/EvaluationReport.vue'
import V19Report from '../components/V19Report.vue'
import UnifiedEvaluation from '../components/UnifiedEvaluation.vue'
const siblings=ref<any[]>([])
const route=useRoute(),result=ref<any>(null),error=ref(''),loading=ref(true),tab=ref('summary'),accepting=ref(false)
watch(()=>route.params.id,async()=>{loading.value=true;result.value=null;error.value='';try{result.value=await api('/reports/'+route.params.id);siblings.value=await api<any[]>('/reports?project_id='+result.value.project_id)}catch(e){error.value=(e as Error).message}finally{loading.value=false}},{immediate:true})
async function refresh(){result.value=await api('/reports/'+route.params.id)}
async function accept(){
 try{await ElMessageBox.confirm('确认已阅读并验收这份报告？','验收报告',{confirmButtonText:'验收通过',cancelButtonText:'继续查看'})}catch{return}
 accepting.value=true;try{await post('/requests/'+result.value.ticket_id+'/accept-report');result.value=await api('/reports/'+route.params.id);ElMessage.success('报告已验收')}catch(e){error.value=(e as Error).message}finally{accepting.value=false}
}
</script>
<template><div class="content-page project-page"><div class="breadcrumb"><RouterLink to="/reports">成果报告</RouterLink><span>/</span>报告详情</div><el-skeleton v-if="loading" :rows="8" animated/><el-alert v-if="error" :title="error" type="error" :closable="false"/><template v-if="result"><div class="report-document-heading"><p>{{result.project_name}}</p><h1>{{result.title}}</h1><time>{{formatDate(result.published_at)}}</time><div class="report-acceptance"><el-button v-if="result.can_accept" type="primary" :loading="accepting" @click="accept">验收通过</el-button><span v-else-if="result.accepted_at" class="status-pill accepted">已验收 · {{formatDate(result.accepted_at)}}</span></div></div><p class="muted">本报告为系统评价建议；用户验收表示收到并审阅报告，不等于专家认定。</p><el-alert v-if="result.unified?.blocking_disagreement" title="部分事实仍待核验，请结合主报告中的证据边界阅读。" type="warning" :closable="false"/><el-tabs v-model="tab"><el-tab-pane label="成果报告" name="summary"><EvaluationReport :value="result.payload" :report-id="result.id" :siblings="siblings" @changed="refresh"/></el-tab-pane><el-tab-pane label="内部审查与依据" name="dual"><UnifiedEvaluation v-if="result.unified" :value="result.unified"/><details class="panel padded"><summary>展开七维原始审查底稿</summary><V19Report :value="result.v19"/></details></el-tab-pane></el-tabs></template></div></template>
