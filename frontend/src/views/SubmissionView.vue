<script setup lang="ts">
import {onMounted, reactive, ref} from 'vue'
import {api, post} from '../api'
import type {Material, User} from '../types'
const user=ref<User|null>(null), loading=ref(true), busy=ref(false), error=ref(''), ticket=ref('')
const materials=ref<Material[]>([]), rejected=ref<{filename:string;error:string}[]>([])
const requestKey=ref(crypto.randomUUID())
const form=reactive({project_name:'',outcome_name:'',outcome_type:'分子',description:'',ai_involved:true,ai_role:'',organizations:'',members:'',related_outputs:'',metrics_baseline:'',external_validation:'',supplementary_notes:'',project_start_date:'',review_cutoff:'',cutoff_basis:''})
onMounted(async()=>{user.value=await api<User>('/auth/me').catch(()=>null);loading.value=false})
async function upload(event:Event){
  const input=event.target as HTMLInputElement
  if(!input.files?.length)return
  busy.value=true;error.value=''
  try{const body=new FormData();Array.from(input.files).forEach(f=>body.append('files',f,f.webkitRelativePath||f.name))
    const result=await api<{accepted:Material[];rejected:{filename:string;error:string}[]}>('/submission-materials/batch',{method:'POST',body})
    materials.value.push(...result.accepted);rejected.value=result.rejected
  }catch(e){error.value=(e as Error).message}finally{busy.value=false;input.value=''}
}
async function submit(){
  if(busy.value)return
  error.value=''
  if(form.ai_involved&&!form.ai_role.trim()){error.value='请填写AI具体参与环节及作用';return}
  if(form.review_cutoff&&!form.cutoff_basis.trim()){error.value='请填写评审日期来源';return}
  busy.value=true
  try{const result=await post<{ticket_id:string}>('/submissions',{...form,request_key:requestKey.value,material_ids:materials.value.map(m=>m.id),project_start_date:form.project_start_date||null,review_cutoff:form.review_cutoff||null});ticket.value=result.ticket_id}
  catch(e){error.value=(e as Error).message}finally{busy.value=false}
}
</script>
<template><div class="content-page submission-page"><div class="page-heading"><div><h1>提交成果</h1></div><RouterLink to="/tickets" class="text-link">查看我的评测 →</RouterLink></div>
<el-skeleton v-if="loading" :rows="5" animated/><el-alert v-else-if="!user" title="请先登录后提交成果。" type="info" :closable="false"/>
<section v-else-if="ticket" class="panel submission-success"><span class="success-mark">✓</span><h2>成果已提交</h2><div class="receipt-number">申请编号 <code>{{ticket}}</code></div><RouterLink to="/tickets" class="primary-link">查看评测进度</RouterLink></section>
<div v-else class="submission-layout"><nav class="form-index" aria-label="填写目录"><strong>填写内容</strong><a href="#outcome-basic"><span>1</span>成果信息</a><a href="#outcome-team"><span>2</span>参与单位与人员</a><a href="#outcome-evidence"><span>3</span>成果与支撑材料</a><a href="#outcome-time"><span>4</span>评审时间</a></nav>
<form class="submission-form" @submit.prevent="submit">
<section id="outcome-basic" class="panel form-section"><div class="form-section-heading"><span>1</span><h2>成果信息</h2></div><fieldset :disabled="busy"><div class="two-column-fields"><label>所属项目 <b>*</b><input v-model="form.project_name" required maxlength="300" placeholder="项目名称或编号"></label><label>成果名称 <b>*</b><input v-model="form.outcome_name" required maxlength="200" placeholder="具体模型、材料、分子或软件名称"></label></div><label class="short-field">成果形态 <b>*</b><select v-model="form.outcome_type"><option v-for="t in ['模型','数据库','软件','平台','材料','分子','反应','装置','产品','其他']" :key="t">{{t}}</option></select></label><label>成果描述 <b>*</b><textarea v-model="form.description" required minlength="10" maxlength="10000" rows="4" placeholder="描述具体产出、解决的问题，以及项目新增的贡献。"></textarea></label><label class="short-field">是否涉及 AI<select v-model="form.ai_involved"><option :value="true">涉及 AI</option><option :value="false">不涉及 AI</option></select></label><label v-if="form.ai_involved">AI 参与环节及作用 <b>*</b><textarea v-model="form.ai_role" required maxlength="5000" rows="3" placeholder="说明 AI 在哪些环节发挥作用，以及相较传统方式带来的变化。"></textarea></label></fieldset></section>
<section id="outcome-team" class="panel form-section"><div class="form-section-heading"><span>2</span><h2>参与单位与人员</h2></div><fieldset :disabled="busy"><label>参与单位 <b>*</b><textarea v-model="form.organizations" required maxlength="5000" rows="3" placeholder="填写单位全称及其主要贡献。"></textarea></label><label>负责人及核心成员 <b>*</b><textarea v-model="form.members" required maxlength="5000" rows="3" placeholder="填写姓名、所在单位及主要贡献。"></textarea></label></fieldset></section>
<section id="outcome-evidence" class="panel form-section"><div class="form-section-heading"><span>3</span><h2>成果与支撑材料</h2></div><fieldset :disabled="busy"><label>相关成果清单 <span class="optional-label">选填</span><textarea v-model="form.related_outputs" maxlength="10000" rows="3" placeholder="论文、专利、软件、数据库等，尽量提供名称、编号或链接。"></textarea></label><label>关键数据与对照基线 <span class="optional-label">选填</span><textarea v-model="form.metrics_baseline" maxlength="10000" rows="3" placeholder="性能、样本规模、周期、成本等数据，以及可比条件下的对照结果。"></textarea></label><label>应用或外部验证 <span class="optional-label">选填</span><textarea v-model="form.external_validation" maxlength="10000" rows="3" placeholder="外部使用、第三方测评、开源复用或转化证明。"></textarea></label><div class="upload-zone"><h3>上传支撑材料</h3><p>支持 PDF、Word、Excel、TXT、Markdown 和 ZIP。</p><div class="upload-actions"><label class="file-picker"><span>选择文件 / ZIP</span><input type="file" multiple accept=".txt,.md,.pdf,.docx,.xlsx,.zip" @change="upload"></label><label class="file-picker secondary"><span>选择文件夹</span><input type="file" multiple webkitdirectory @change="upload"></label></div><p v-if="busy" role="status">正在处理，请稍候…</p><details class="upload-limits"><summary>文件大小与格式要求</summary><p>单文件不超过 200MB，每批最多 200 个、合计 2GB；ZIP 解压后不超过 5GB。PDF 最多 1000 页，扫描件需先完成文字识别。</p></details></div><ul v-if="materials.length" class="attachment-list"><li v-for="(m,i) in materials" :key="m.id"><span>{{m.filename}}</span><el-button link type="primary" @click="materials.splice(i,1)">移除</el-button></li></ul><el-alert v-for="(r,i) in rejected" :key="i" type="warning" :closable="false" :title="r.filename+'：'+r.error"/><label>补充说明 <span class="optional-label">选填</span><textarea v-model="form.supplementary_notes" maxlength="5000" rows="2"></textarea></label></fieldset></section>
<section id="outcome-time" class="panel form-section"><div class="form-section-heading"><span>4</span><h2>评审时间</h2></div><fieldset :disabled="busy"><div class="two-column-fields"><label>项目启动日<input v-model="form.project_start_date" type="date"></label><label>评审 / 统计截止日<input v-model="form.review_cutoff" type="date"></label></div><label>日期依据 <b v-if="form.review_cutoff">*</b><input v-model="form.cutoff_basis" :required="!!form.review_cutoff" maxlength="1000" placeholder="例如：报告名称、页码及统计截止说明"></label></fieldset></section>
<div class="submission-actions"><el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/><div><el-button type="primary" native-type="submit" :loading="busy">提交评测申请</el-button></div></div>
</form></div></div></template>