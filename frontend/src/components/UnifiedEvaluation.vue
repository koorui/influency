<script setup lang="ts">
defineProps<{value:{comparison:string;levels:{management_level:string|null;dimension_level:string|null;scope_level:string|null};differences:{field:string;management:string;dimensions:string}[]}}>()
const states:Record<string,string>={consistent:'两份报告等级一致',different:'两份报告存在等级差异，请核对依据',incomplete:'等级或成果映射尚不完整',legacy_or_mixed:'历史报告：尚未按统一标准重新评价'}
</script>
<template><section class="panel padded unified-evaluation"><h2>评价结果对照</h2><p>{{states[value.comparison]||value.comparison}}</p><dl><div><dt>管理者报告</dt><dd>{{value.levels.management_level||'未提供'}}</dd></div><div><dt>七维综合</dt><dd>{{value.levels.dimension_level||'未提供'}}</dd></div><div><dt>本轮范围</dt><dd>{{value.levels.scope_level||'未提供'}}</dd></div></dl><ul v-if="value.differences.length"><li v-for="d in value.differences" :key="d.field">{{d.field==='impact_level'?'成果整体等级':d.field}}：管理者报告 {{d.management}}，七维分析 {{d.dimensions}}</li></ul><p v-if="value.comparison==='different'" class="muted">请结合下方两份报告核对证据覆盖、时间范围与成果粒度；不取平均或自动采用较高等级。</p></section></template>
<style scoped>
.unified-evaluation{margin-bottom:20px}.unified-evaluation h2{margin-top:0}.unified-evaluation dl{display:flex;flex-wrap:wrap;gap:24px}.unified-evaluation dt{font-size:13px;color:var(--text-muted,#667085)}.unified-evaluation dd{margin:6px 0 0;font-size:22px;font-weight:600}.unified-evaluation li{line-height:1.8}
</style>
