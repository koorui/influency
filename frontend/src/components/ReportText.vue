<script setup lang="ts">
import {computed,ref,watch} from 'vue'
const props=defineProps<{text?:string;limit?:number}>()
const expanded=ref(false)
const long=computed(()=>(props.text||'').length>(props.limit||200))
const preview=computed(()=>{
  const text=props.text||'',limit=props.limit||200
  const end=text.slice(0,limit).search(/[。！？]/)
  return end>=30?text.slice(0,end+1):text.slice(0,limit)+'…'
})
watch(()=>props.text,()=>expanded.value=false)
</script>
<template><div class="report-text"><p>{{long&&!expanded?preview:text}}</p><button v-if="long" type="button" :aria-expanded="expanded" @click="expanded=!expanded">{{expanded?'收起全文':'展开完整说明'}} <span aria-hidden="true">{{expanded?'−':'+'}}</span></button></div></template>
<style scoped>
.report-text p{margin:8px 0;white-space:pre-line;line-height:1.85;overflow-wrap:anywhere}.report-text button{border:0;background:transparent;color:#28688a;font:inherit;font-size:12px;cursor:pointer;padding:4px 0}.report-text button:focus-visible{outline:2px solid #28688a;outline-offset:3px}
</style>
