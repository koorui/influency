<script setup lang="ts">
import {ref, onMounted} from 'vue'
import {useRoute} from 'vue-router'
import {api} from '../api'
import type {Result} from '../types'
import EvaluationReport from '../components/EvaluationReport.vue'
const route = useRoute(), result = ref<Result | null>(null), error = ref(''), loading = ref(true)
onMounted(async () => {try {result.value = await api(`/results/${route.params.id}`)} catch(e) {error.value = (e as Error).message} finally {loading.value=false}})
</script>
<template><div class="content-page"><div class="breadcrumb"><RouterLink to="/">成果检索</RouterLink><span>/</span>评价详情</div><el-skeleton v-if="loading" :rows="8" animated /><el-alert v-if="error" :title="error" type="error" :closable="false" /><EvaluationReport v-if="result" :value="result.payload" /></div></template>
