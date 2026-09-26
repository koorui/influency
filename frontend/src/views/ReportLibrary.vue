<script setup lang="ts">
import {ref,computed,onMounted,watch} from 'vue'
import {api,formatDate} from '../api'
import type {Project} from '../project'
import ProjectGate from '../components/ProjectGate.vue'
const projects=ref<Project[]>([]),projectId=ref(''),reports=ref<{id:string;title:string;project_name:string;published_at:string}[]>([]),error=ref(''),ready=ref(false),query=ref('')
const filtered=computed(()=>reports.value.filter(r=>r.title.includes(query.value.trim())))
async function load(){try{projects.value=await api('/projects');if(!projects.value.some(p=>p.id===projectId.value))projectId.value=projects.value[0]?.id||'';await loadReports();ready.value=true}catch(e){error.value=(e as Error).message}}
async function loadReports(){reports.value=[];const id=projectId.value;if(!id)return;try{const rows=await api<typeof reports.value>('/reports?project_id='+encodeURIComponent(id));if(projectId.value===id){reports.value=rows;error.value=''}}catch(e){if(projectId.value===id)error.value=(e as Error).message}}
async function joined(p:Project){await load();projectId.value=p.id}
watch(projectId,loadReports);onMounted(load)
</script>
<template><div class="content-page project-page"><el-alert v-if="error" :title="error" type="error" :closable="false"/><ProjectGate v-if="ready&&!projects.length" empty @unlocked="joined"/><template v-if="projects.length"><div class="project-toolbar"><el-select v-model="projectId" aria-label="报告所属项目" class="project-select"><el-option v-for="p in projects" :key="p.id" :value="p.id" :label="p.name"/></el-select><ProjectGate @unlocked="joined"/></div><div class="section-heading"><h2>成果报告 <span class="count-pill">{{reports.length}}</span></h2><el-input v-model="query" aria-label="查找成果报告" placeholder="查找成果名称" clearable style="max-width:280px"/></div><div class="project-grid"><RouterLink v-for="r in filtered" :key="r.id" :to="`/results/${r.id}`" class="panel report-tile"><span class="report-tile-mark">报告</span><h3>{{r.title}}</h3><div><time>{{formatDate(r.published_at)}}</time><span>查看报告 ↗</span></div></RouterLink></div><div v-if="!filtered.length" class="panel empty-project">暂无符合条件的已完成报告</div></template></div></template>
