<script setup lang="ts">
import {ref} from 'vue'
import {post} from '../api'
import type {Project} from '../project'
defineProps<{empty?:boolean}>()
const emit=defineEmits<{unlocked:[project:Project]}>()
const open=ref(false),code=ref(''),busy=ref(false),error=ref('')
async function unlock(){busy.value=true;error.value='';try{const p=await post<Project>('/projects/unlock',{code:code.value.trim()});emit('unlocked',p);open.value=false;code.value=''}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
</script>
<template><div v-if="empty" class="project-gate panel"><svg width="52" height="52" viewBox="0 0 52 52" fill="none" aria-hidden="true"><rect x="10" y="23" width="32" height="24" rx="5" stroke="currentColor" stroke-width="2"/><path d="M17 23v-9a9 9 0 0118 0v9M26 32v6" stroke="currentColor" stroke-width="2"/></svg><h2>输入项目安全码</h2><form @submit.prevent="unlock"><el-input v-model="code" aria-label="项目安全码" placeholder="项目安全码" autocomplete="off"/><el-button type="primary" native-type="submit" :loading="busy" :disabled="!code.trim()">加入项目</el-button></form><el-alert v-if="error" :title="error" type="error" :closable="false"/></div><template v-else><el-button @click="open=true;error=''">加入项目</el-button><el-dialog v-model="open" title="输入项目安全码" width="min(460px,94vw)"><form @submit.prevent="unlock"><el-input v-model="code" aria-label="项目安全码" placeholder="项目安全码" autocomplete="off"/><el-alert v-if="error" :title="error" type="error" :closable="false"/><div class="dialog-actions"><el-button type="primary" native-type="submit" :loading="busy" :disabled="!code.trim()">加入项目</el-button></div></form></el-dialog></template></template>
