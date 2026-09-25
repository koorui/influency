<script setup lang="ts">
import {onMounted, onUnmounted, ref} from 'vue'
import {Search, ArrowUp, Right, CircleCheck, WarningFilled} from '@element-plus/icons-vue'
import {api, post} from '../api'
import type {Result} from '../types'
type ProjectOption = {id: string; title: string; keywords: string[]; category: string; is_demo: boolean}

const projectText = ref('')
const projectId = ref('')
const taskType = ref('成果影响力评价')
const detail = ref('')
const loading = ref(false)
const searched = ref(false)
const error = ref('')
const results = ref<Result[]>([])
const featured = ref<ProjectOption[]>([])
const candidates = ref<ProjectOption[]>([])
const selected = ref<ProjectOption | null>(null)
const submittedTask = ref('')
const activeIndex = ref(-1)
const suggesting = ref(false)
const focused = ref(false)
const taskTypes = ['成果影响力评价', '技术先进性核验', '外部应用证据核验']

let sequence = 0
let debounce: ReturnType<typeof setTimeout> | undefined
async function suggest(value: string) {
  const request = ++sequence; suggesting.value = true
  try {
    const items = await api<ProjectOption[]>(`/projects/suggestions?q=${encodeURIComponent(value)}`)
    if (request === sequence) {candidates.value = items; activeIndex.value = -1}
    return items
  } catch (e) {if(request===sequence) {candidates.value=[]; error.value=(e as Error).message}; return []}
  finally {if(request===sequence) suggesting.value=false}
}
onMounted(async () => {featured.value = await suggest('')})
onUnmounted(() => {clearTimeout(debounce); ++sequence})
function choose(item: ProjectOption) { clearTimeout(debounce); ++sequence; suggesting.value=false; selected.value = item; projectId.value = item.id; projectText.value = item.title; error.value = ''; focused.value = false; searched.value=false }
function clearSelection() { clearTimeout(debounce); ++sequence; suggesting.value=false; projectId.value = ''; selected.value=null; candidates.value=[]; activeIndex.value=-1; error.value = ''; searched.value=false; focused.value=true }
function onProjectInput(event:Event) {clearSelection(); projectText.value=(event.target as HTMLInputElement).value; const value=projectText.value; suggesting.value=true; debounce=setTimeout(()=>suggest(value),180)}
function move(direction:number) {focused.value=true; activeIndex.value=Math.max(0,Math.min(candidates.value.length-1,activeIndex.value+direction))}
function enter() {if(focused.value && activeIndex.value>=0 && candidates.value[activeIndex.value]) choose(candidates.value[activeIndex.value]); else submit()}
function validate() {
  if (!projectId.value || !selected.value || projectText.value !== selected.value.title) return '请从联想列表中选择一个已有成果，不能直接输入未收录项目。'
  if (!taskTypes.includes(taskType.value)) return '请选择有效的评价任务类型。'
  if (detail.value.length > 300) return '补充说明不能超过 300 个字。'
  if (/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(detail.value)) return '补充说明不能包含不可见控制字符。'
  return ''
}
async function submit() {
  const message = validate()
  if (message) { error.value = message; searched.value = false; return }
  if (loading.value) return
  loading.value = true; error.value = ''; searched.value=false
  try {
    const data = await post<{results: Result[]; task_type: string}>('/search', {project_id: projectId.value, task_type: taskType.value, detail: detail.value})
    results.value = data.results; submittedTask.value=data.task_type; searched.value = true; focused.value=false
  } catch (e) { error.value = (e as Error).message } finally { loading.value = false }
}
</script>
<template>
  <section class="search-page fixed-query-page">
    <div class="hero-orbit" aria-hidden="true"></div>
    <div class="hero"><div class="eyebrow">RESEARCH IMPACT EXPLORER</div><h1>选择成果，<span>开始评价。</span></h1><p>从已发布成果中选择项目，填写本次关注的核验内容</p></div>
    <form class="fixed-form" @submit.prevent="submit" novalidate>
      <div class="form-title"><div><span class="eyebrow">FIXED EVALUATION FORM</span><h2>评价任务</h2></div><span class="form-step">01 / 01</span></div>
      <div class="form-field project-field"><label for="project">已有成果 <b>*</b></label><div class="field-wrap" :class="{invalid: error && !projectId}"><el-icon><Search /></el-icon><input id="project" v-model="projectText" autocomplete="off" maxlength="200" placeholder="输入成果名称或关键词，从已有项目中选择" role="combobox" aria-autocomplete="list" aria-controls="project-options" :aria-expanded="focused" :aria-activedescendant="activeIndex >= 0 ? `project-option-${activeIndex}` : undefined" @focus="focused=true; suggest(projectText)" @blur="focused=false" @input="onProjectInput" @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)" @keydown.enter.prevent="enter" @keydown.esc="focused=false"/><button v-if="projectText" type="button" class="clear-field" aria-label="清空成果" @click="projectText='';clearSelection();suggest('')">×</button></div><div v-if="focused" id="project-options" role="listbox" aria-label="已有成果建议" class="suggestion-menu"><p v-if="suggesting" class="suggestion-empty">正在查找已有成果…</p><p v-else-if="!candidates.length" class="suggestion-empty">没有匹配的已发布成果，可从顶部“提交成果”填写评测申请。</p><button v-for="(item, i) in candidates" :key="item.id" :id="`project-option-${i}`" role="option" :aria-selected="activeIndex===i" type="button" class="suggestion-item" :class="{highlighted:activeIndex===i}" @mousedown.prevent @click="choose(item)"><span class="suggestion-icon"><el-icon><CircleCheck /></el-icon></span><span><strong>{{item.title}}</strong><small>{{item.keywords.join(' · ')}}</small></span><el-icon><Right /></el-icon></button></div><small class="field-help">此处只查询已发布成果；未收录成果请使用顶部“提交成果”入口</small></div>
      <div class="form-field"><label for="task-type">评价任务 <b>*</b></label><select id="task-type" v-model="taskType"><option v-for="item in taskTypes" :key="item" :value="item">{{item}}</option></select><small class="field-help">记录本次关注方向，当前展示已有评价，不会重新生成结论</small></div>
      <div class="form-field"><label for="detail">补充说明 <span>选填</span></label><textarea id="detail" v-model="detail" maxlength="300" placeholder="补充你希望核验的具体内容，例如：关注外部应用证据、技术指标口径……"></textarea><div class="field-counter" :class="{over: detail.length > 300}">{{detail.length}} / 300</div></div>
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false"><template #icon><el-icon><WarningFilled /></el-icon></template></el-alert>
      <div class="form-bottom"><span><el-icon><CircleCheck /></el-icon> 已启用固定格式校验</span><button class="form-submit" :disabled="loading" type="submit">{{loading ? '查询中…' : '开始查询'}} <el-icon v-if="!loading"><ArrowUp /></el-icon></button></div>
    </form>
    <div v-if="searched" class="search-results fixed-results"><div class="section-heading"><h2>查询结果 <small>{{results.length}} 项成果</small></h2><span>{{submittedTask}} · 表单已保存</span></div><p class="muted">当前展示已有评价，尚未执行新的模型核验。可在“我的需求”查看提交记录。</p><div class="result-grid"><RouterLink v-for="item in results" :key="item.id" :to="`/results/${item.id}`" class="result-card"><span class="card-category">{{item.payload.category}} <span v-if="item.payload.is_demo" class="demo-badge">演示</span></span><h3>{{item.title}}</h3><p>{{item.payload.summary}}</p><div class="card-footer"><span>{{item.payload.level ? `L${item.payload.level} · ${item.payload.level_name}` : item.payload.level_name}}</span><el-icon><Right /></el-icon></div></RouterLink></div></div>
    <section v-else class="featured compact-featured"><div class="section-heading"><h2>已有成果</h2><span>点击项目可自动补全表单</span></div><div class="result-grid"><button v-for="item in featured.slice(0, 3)" :key="item.id" class="result-card featured-button" @click="choose(item)"><span class="card-category">{{item.category}} <span v-if="item.is_demo" class="demo-badge">演示</span></span><h3>{{item.title}}</h3><p>{{item.keywords.join(' · ')}}</p><div class="card-footer"><span>选择并补全</span><el-icon><Right /></el-icon></div></button><div v-if="!featured.length" class="empty-library"><p>成果库暂无已发布项目</p></div></div></section>
    <footer class="page-foot">知衡 · 成果影响力评价平台 <span>固定表单 · 规范输入 · 可追溯评价</span></footer>
  </section>
</template>
