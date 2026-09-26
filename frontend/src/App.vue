<script setup lang="ts">
import {computed} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {House,DocumentAdd,Files,Collection,SwitchButton,FolderOpened,Connection,Finished,List,Clock,Search} from '@element-plus/icons-vue'
import {post} from './api'
import {currentUser as user} from './session'
import BrandLogo from './components/BrandLogo.vue'
const route=useRoute(),router=useRouter()
const adminMode=computed(()=>route.path==='/admin')
const userLinks=[{to:'/',label:'需求提交',icon:DocumentAdd},{to:'/reports',label:'成果报告',icon:Collection}]
const adminLinks=[{key:'projects',label:'项目材料库',icon:FolderOpened},{key:'requests',label:'工单与工作流',icon:Connection}]
const activeTab=computed(()=>['projects','materials'].includes(String(route.query.tab))?'projects':'requests')
const pageTitle=computed(()=>adminMode.value?adminLinks.find(x=>x.key===activeTab.value)?.label||'评价管理':userLinks.find(x=>x.to===route.path)?.label||'成果报告')
async function logout(){await post('/auth/logout');user.value=null;router.push('/login')}
</script>
<template>
  <RouterView v-if="route.path==='/login'" />
  <div v-else-if="user" class="workspace-shell">
    <a class="skip-link" href="#page-content">跳到正文</a>
    <aside class="workspace-sidebar">
      <RouterLink :to="adminMode?'/admin':'/'" class="product-brand"><BrandLogo/></RouterLink>
      <nav v-if="adminMode" class="workspace-nav" aria-label="管理导航"><RouterLink v-for="item in adminLinks" :key="item.key" :to="{path:'/admin',query:{tab:item.key}}" :class="{active:activeTab===item.key}"><el-icon><component :is="item.icon"/></el-icon>{{item.label}}</RouterLink></nav>
      <nav v-else class="workspace-nav" aria-label="用户导航"><RouterLink v-for="item in userLinks" :key="item.to" :to="item.to" :class="{active:route.path===item.to||(item.to==='/reports'&&route.path.startsWith('/results/'))}"><el-icon><component :is="item.icon"/></el-icon>{{item.label}}</RouterLink></nav>
      <div class="sidebar-account"><RouterLink v-if="user.role==='admin'" :to="adminMode?'/':'/admin'" class="workspace-switch">{{adminMode?'进入用户工作台':'进入管理工作台'}} <span>↗</span></RouterLink><div class="account-line"><span class="account-avatar">{{user.username.slice(0,1).toUpperCase()}}</span><div><strong>{{user.username}}</strong><small>{{user.role==='admin'?'管理员':'普通用户'}}</small></div><button class="icon-button" @click="logout" aria-label="退出登录" title="退出登录"><el-icon><SwitchButton/></el-icon></button></div></div>
    </aside>
    <div class="workspace-main"><header class="workspace-topbar"><div><span>{{adminMode?'评价管理':'用户工作台'}}</span><span class="path-separator">/</span><strong>{{pageTitle}}</strong></div><span class="role-label">{{adminMode?'管理端':'用户端'}}</span></header><main id="page-content" tabindex="-1"><RouterView/></main></div>
  </div>
</template>
