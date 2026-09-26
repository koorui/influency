<script setup lang="ts">
import {computed} from 'vue'
import {useRoute} from 'vue-router'
import ProjectManager from './ProjectManager.vue'
import WorkflowConsole from './WorkflowConsole.vue'
const route=useRoute()
const projectMode=computed(()=>['projects','materials'].includes(String(route.query.tab)))
</script>
<template><ProjectManager v-if="projectMode"/><WorkflowConsole v-else/></template>
