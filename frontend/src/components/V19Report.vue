<script setup lang="ts">
defineProps<{value:any}>()
const states:Record<string,string>={insufficient_evidence:'证据不足',not_applicable:'不适用',conflict:'存在冲突',not_assessed:'尚未审阅'}
const labels:Record<string,string>={D1:'问题解决与先进性',D2:'原创与项目新增',D3:'学术影响',D4:'开放复用',D5:'真实应用',D6:'主线集成',D7:'外部认可'}
</script>
<template><section class="v19-report">
<div v-for="outcome in value.outcomes" :key="outcome.outcome_id" class="panel padded"><h2>{{outcome.title}}</h2><h3>成果整体：{{outcome.synthesis?.impact_level?.level || '待确认'}}</h3><p>{{outcome.synthesis?.impact_level?.reason}}</p><el-table :data="outcome.dimensions"><el-table-column label="维度" min-width="150"><template #default="{row}">{{row.dimension_id}} {{labels[row.dimension_id]}}</template></el-table-column><el-table-column label="等级" width="100"><template #default="{row}">{{row.grade?.level || states[row.grade?.assessment_state] || '待确认'}}</template></el-table-column><el-table-column label="判断与依据" min-width="300"><template #default="{row}"><p>{{row.conclusion}}</p><small class="muted">{{row.grade?.reason}}</small></template></el-table-column></el-table></div>
<div class="panel padded" v-for="(label,key) in {specific_layer:'特定层',global_layer:'全局层',system_collaboration:'协同判断'}" :key="key"><h2>{{label}}</h2><p>{{value.project_synthesis?.[key]?.status}}</p><p>{{value.project_synthesis?.[key]?.conclusion}}</p></div><p class="muted">{{value.project_synthesis?.scope_impact_level?.scope}}</p></section></template>
<style scoped>.panel{margin-bottom:16px}p{font-size:13px;overflow-wrap:anywhere}</style>
