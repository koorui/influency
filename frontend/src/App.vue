<script setup lang="ts">
import {ref, watch} from 'vue'
import {useRoute, useRouter} from 'vue-router'
import {SwitchButton, DataAnalysis} from '@element-plus/icons-vue'
import {api, post} from './api'
import type {User} from './types'
const route = useRoute(), router = useRouter(), user = ref<User | null>(null)
watch(() => route.path, async () => {user.value = await api<User>('/auth/me').catch(() => null)}, {immediate: true})
async function logout() {await post('/auth/logout'); user.value = null; router.push('/')}
</script>
<template>
  <div class="app-shell simplified-shell">
    <main class="main"><header class="topbar"><RouterLink to="/" class="top-brand"><span class="brand-icon"><el-icon><DataAnalysis /></el-icon></span><strong>知衡</strong><small>IMPACT</small></RouterLink><div><span class="environment-dot"></span>成果影响力评价 <RouterLink to="/submit">提交成果</RouterLink><RouterLink to="/tickets">我的需求</RouterLink><RouterLink to="/admin">管理入口 ↗</RouterLink><button v-if="user" class="icon-button" @click="logout" aria-label="退出登录"><el-icon><SwitchButton /></el-icon></button><RouterLink v-else to="/login">登录</RouterLink></div></header><RouterView /></main>
  </div>
</template>
