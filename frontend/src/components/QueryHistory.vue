<script setup lang="ts">
import {ref, onMounted} from 'vue'
import {api, formatDate} from '../api'
const props=defineProps<{admin?: boolean}>()
type Record = {id:string; project_title:string; task_type:string; detail:string; result_id:string; result_revision:number; created_at:string; prompt?:string; prompt_version:string}
const rows=ref<Record[]>([]), error=ref(''), selected=ref<Record|null>(null)
async function load(){try{rows.value=await api(props.admin?'/admin/queries':'/queries');error.value=''}catch(e){error.value=(e as Error).message}}
onMounted(load)
</script>
<template><section class="panel padded query-history"><div class="section-heading"><div><h2>表单提交记录</h2><p>已保存任务方向和补充说明；当前查看已有报告，不代表已重新评价。</p></div><el-button @click="load">刷新记录</el-button></div><el-alert v-if="error" :title="error" type="error" :closable="false"/><el-table :data="rows" empty-text="暂无表单提交记录"><el-table-column prop="project_title" label="成果名称" min-width="200"/><el-table-column prop="task_type" label="任务方向" min-width="160"/><el-table-column prop="detail" label="补充说明" min-width="180"/><el-table-column label="提交时间" min-width="180"><template #default="{row}">{{formatDate(row.created_at)}}</template></el-table-column><el-table-column label="查看" width="135"><template #default="{row}"><el-button v-if="admin" type="primary" link @click="selected=row">模板记录</el-button><RouterLink v-else class="text-link" :to="`/results/${row.result_id}`">成果报告 ↗</RouterLink></template></el-table-column></el-table><el-dialog :model-value="!!selected" @close="selected=null" title="固定模板记录" width="min(760px,94vw)"><template v-if="selected"><p class="muted">模板 {{selected.prompt_version}} · 引用报告版本 {{selected.result_revision}}</p><pre class="material-text">{{selected.prompt}}</pre><p>此模板已补全并保存，尚未调用评价模型执行。</p></template></el-dialog></section></template>
