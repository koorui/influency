<script setup lang="ts">
import type {Step} from '../project'
import {states} from '../project'
defineProps<{steps:Step[];selected?:number;interactive?:boolean}>()
defineEmits<{select:[index:number]}>()
</script>
<template><ol class="workflow-progress"><li v-for="(step,i) in steps" :key="step.name" :class="[step.status,{selected:selected===i}]"><button v-if="interactive" @click="$emit('select',i)" :aria-pressed="selected===i"><span class="step-dot">{{step.status==='succeeded'?'✓':i+1}}</span><span><strong>{{step.name}}</strong><small>{{states[step.status]||step.status}}</small></span></button><div v-else><span class="step-dot">{{step.status==='succeeded'?'✓':i+1}}</span><span><strong>{{step.name}}</strong><small>{{states[step.status]||step.status}}</small></span></div></li></ol></template>
