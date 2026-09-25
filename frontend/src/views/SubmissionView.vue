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
<template><div class="content-page submission-page"><div class="page-heading"><div><div class="eyebrow">NEW OUTCOME</div><h1>提交代表性成果</h1><p>每项成果单独填写，说明具体产出、新增贡献与支撑依据。</p></div></div>
  <p v-if="loading">正在加载…</p><el-alert v-else-if="!user" type="info" :closable="false" title="请先登录或注册，以便上传材料和跟踪评测进度"><RouterLink to="/login?redirect=/submit">前往登录 / 注册</RouterLink></el-alert>
  <div v-else-if="ticket" class="panel padded"><h2>已提交，等待管理员受理</h2><p>工单编号：{{ticket}}</p><p>管理员会核对材料、成果范围与评审日期，再启动评价。提交成功不代表已完成评测。</p><RouterLink to="/tickets" class="text-link">查看我的需求 →</RouterLink></div>
  <form v-else class="panel padded submission-form" @submit.prevent="submit">
    <fieldset :disabled="busy"><legend>一、成果名称</legend><label>所属项目 *<input v-model="form.project_name" required maxlength="300" placeholder="项目名称或编号"></label><label>成果名称 *<input v-model="form.outcome_name" required maxlength="200" placeholder="具体模型、材料、分子、软件等"></label><label>成果形态 *<select v-model="form.outcome_type"><option v-for="t in ['模型','数据库','软件','平台','材料','分子','反应','装置','产品','其他']" :key="t">{{t}}</option></select></label></fieldset>
    <fieldset :disabled="busy"><legend>二、成果描述 / 总结</legend><label>具体产出、解决的问题和新增贡献 *<textarea v-model="form.description" required minlength="10" maxlength="10000" rows="4"></textarea></label><label>是否涉及AI<select v-model="form.ai_involved"><option :value="true">涉及AI</option><option :value="false">不涉及AI</option></select></label><label v-if="form.ai_involved">AI具体参与环节及作用 *<textarea v-model="form.ai_role" required maxlength="5000" rows="3" placeholder="说明相较传统方式带来的变化；无法确定净贡献时请如实说明"></textarea></label></fieldset>
    <fieldset :disabled="busy"><legend>三、参与单位</legend><label>单位全称及主要贡献 *<textarea v-model="form.organizations" required maxlength="5000" rows="3"></textarea></label></fieldset>
    <fieldset :disabled="busy"><legend>四、负责人及核心成员</legend><label>姓名、单位和主要贡献 *<textarea v-model="form.members" required maxlength="5000" rows="3" placeholder="无法区分核心成员时，可列出相关参与人员"></textarea></label></fieldset>
    <fieldset :disabled="busy"><legend>五、相关成果清单</legend><label>论文、专利、软件、数据库、模型、平台或转化项目<textarea v-model="form.related_outputs" maxlength="10000" rows="3" placeholder="尽量提供名称、编号或链接"></textarea></label></fieldset>
    <fieldset :disabled="busy"><legend>六、关键数据与对照基线</legend><label>样本规模、性能、周期、成本、人工介入及同口径对比<textarea v-model="form.metrics_baseline" maxlength="10000" rows="4" placeholder="不适用项可不填写，请勿无依据估算"></textarea></label></fieldset>
    <fieldset :disabled="busy"><legend>七、已有应用或外部验证</legend><label>外部使用、第三方验证、开源复用或转化证明（如有）<textarea v-model="form.external_validation" maxlength="10000" rows="3"></textarea></label></fieldset>
    <fieldset :disabled="busy"><legend>八、补充材料</legend><label>补充说明<textarea v-model="form.supplementary_notes" maxlength="5000" rows="2"></textarea></label><label>选择文件或ZIP<input type="file" multiple accept=".txt,.md,.pdf,.docx,.xlsx,.zip" @change="upload"></label><label>选择文件夹<input type="file" multiple webkitdirectory @change="upload"></label><p class="muted">单文件200MB，单批200个、合计2GB；ZIP解压后5GB。PDF最多1000页，扫描件需先OCR。上传后请核对成功和失败列表。</p><ul><li v-for="(m,i) in materials" :key="m.id">{{m.filename}} <button type="button" @click="materials.splice(i,1)">取消关联</button></li></ul><el-alert v-for="(r,i) in rejected" :key="i" type="warning" :closable="false" :title="`${r.filename}：${r.error}`"/></fieldset>
    <fieldset :disabled="busy"><legend>评审时间边界</legend><p class="muted">不明确时可暂不填写，管理员会在检索前确认。不得用今天替代原评审日期。</p><label>项目启动日<input v-model="form.project_start_date" type="date"></label><label>评审 / 统计截止日<input v-model="form.review_cutoff" type="date"></label><label>日期来源<input v-model="form.cutoff_basis" :required="!!form.review_cutoff" maxlength="1000" placeholder="报告名称与页码、统计截止说明等"></label></fieldset>
    <el-alert v-if="error" :title="error" type="error" :closable="false"/><el-button type="primary" native-type="submit" :loading="busy">提交给管理员</el-button><p class="muted">填写内容会作为项目方自报材料保留，评测将独立核验。提交不会直接发布结果。</p>
  </form></div></template>
<style scoped>
.submission-page{max-width:1000px;margin:auto}.submission-form fieldset{border:0;border-bottom:1px solid #e4e9ee;padding:20px 0;margin:0 0 20px}.submission-form legend{font-size:18px;font-weight:600}.submission-form label{display:block;margin:14px 0}.submission-form input:not([type=file]),.submission-form textarea,.submission-form select{display:block;box-sizing:border-box;width:100%;margin-top:8px;border:1px solid #cbd5e1;border-radius:8px;padding:10px;font:inherit;background:white;color:#172a40}.submission-form input[type=file]{display:block;margin:8px 0}.submission-form li{margin:8px 0;overflow-wrap:anywhere}
</style>
