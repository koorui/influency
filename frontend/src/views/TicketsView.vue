<script setup lang="ts">
import {ref, onMounted, onUnmounted} from 'vue'
import {api, statusNames, formatDate} from '../api'
import type {Ticket} from '../types'
import QueryHistory from '../components/QueryHistory.vue'
const rows = ref<Ticket[]>([]), error = ref('')
async function load() {try {rows.value=await api('/tickets'); error.value=''} catch(e) {error.value=(e as Error).message}}
let timer: ReturnType<typeof setInterval>
onMounted(()=> {load(); timer=setInterval(load, 8000)})
onUnmounted(()=>clearInterval(timer))
</script>
<template><div class="content-page"><div class="page-heading"><div><div class="eyebrow">MY REQUESTS</div><h1>我的需求</h1><p>查看固定表单提交记录和历史资料补充需求。</p></div><el-button @click="load">刷新进度</el-button></div><el-alert v-if="error" :title="error" type="error" :closable="false" /><QueryHistory /><div class="panel padded"><h2>成果评测工单</h2><el-empty v-if="!rows.length" description="暂无历史工单，可在上方查看表单提交记录"><RouterLink to="/" class="text-link">开始查询 →</RouterLink></el-empty><el-table v-else :data="rows"><el-table-column label="成果 / 需求" prop="query" min-width="180" /><el-table-column label="状态" width="130"><template #default="{row}"><el-tag :type="row.status==='published' ? 'success' : 'info'">{{statusNames[row.status]}}</el-tag></template></el-table-column><el-table-column label="提交时间" min-width="180"><template #default="{row}">{{formatDate(row.created_at)}}</template></el-table-column><el-table-column label="进度说明" prop="note" min-width="180"/><el-table-column label="成果" width="110"><template #default="{row}"><RouterLink v-if="row.result_id" :to="`/results/${row.result_id}`" class="text-link">查看结果 ↗</RouterLink><span v-else class="muted">等待处理</span></template></el-table-column></el-table></div><p class="muted">访客需求绑定当前浏览器会话；登录后可在不同设备查看账号下的需求。登录前后的需求分别保存。</p></div></template>
