<script setup lang="ts">
import {ref} from 'vue'
import {useRouter,useRoute} from 'vue-router'
import {post} from '../api'
import type {User} from '../types'
const route=useRoute(), router=useRouter(), username=ref(''), password=ref(''), register=ref(false), busy=ref(false), error=ref('')
async function submit() {busy.value=true; error.value=''; try {const user=await post<User>(register.value ? '/auth/register' : '/auth/login', {username:username.value,password:password.value});let destination=user.role==='admin'?'/admin':'/';if(typeof route.query.redirect==='string'){const target=new URL(route.query.redirect,window.location.origin);if(target.origin===window.location.origin)destination=target.pathname+target.search+target.hash}router.push(destination)} catch(e) {error.value=(e as Error).message} finally {busy.value=false}}
</script>
<template><div class="login-wrap"><form class="panel login-panel" @submit.prevent="submit"><div class="eyebrow">WELCOME TO IMPACT</div><h1>{{register ? '创建账户' : '欢迎回来'}}</h1><p>登录后管理需求，或进入评价工作台。</p><label for="username">账号</label><el-input id="username" v-model="username" autocomplete="username" placeholder="字母、数字、下划线，至少3位" maxlength="80" /><label for="password">密码</label><el-input id="password" v-model="password" type="password" show-password :autocomplete="register ? 'new-password' : 'current-password'" placeholder="至少6位" maxlength="128"/><el-alert v-if="error" :title="error" type="error" :closable="false" /><el-button native-type="submit" type="primary" :loading="busy" class="full-width">{{register ? '创建普通用户账户' : '登录'}}</el-button><button type="button" class="link-button" @click="register=!register; error=''">{{register ? '已有账户？返回登录' : '没有账户？注册普通用户'}}</button><p class="muted small">管理员账户由服务端初始化命令创建。</p></form></div></template>
