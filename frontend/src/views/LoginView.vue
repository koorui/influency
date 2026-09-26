<script setup lang="ts">
import {ref} from 'vue'
import {useRouter,useRoute} from 'vue-router'
import {post} from '../api'
import BrandLogo from '../components/BrandLogo.vue'
import type {User} from '../types'
const route=useRoute(),router=useRouter(),username=ref(''),password=ref(''),confirmation=ref(''),register=ref(false),busy=ref(false),error=ref('')
function switchMode(value:boolean){register.value=value;error.value='';confirmation.value=''}
async function submit(){
 if(busy.value)return
 error.value=''
 if(register.value&&password.value!==confirmation.value){error.value='两次输入的密码不一致';return}
 busy.value=true
 try{const user=await post<User>(register.value?'/auth/register':'/auth/login',{username:username.value,password:password.value});let destination=user.role==='admin'?'/admin':'/';if(typeof route.query.redirect==='string'){const target=new URL(route.query.redirect,window.location.origin);if(target.origin===window.location.origin&&target.pathname!=='/login')destination=target.pathname+target.search+target.hash}await router.push(destination)}catch(e){error.value=(e as Error).message}finally{busy.value=false}
}
</script>
<template>
  <main class="login-page">
    <section class="login-card" aria-label="知衡impact账号登录">
      <div class="login-brand"><BrandLogo /></div>
      <div class="login-tabs" aria-label="登录或注册">
        <button type="button" :class="{active:!register}" :aria-pressed="!register" @click="switchMode(false)">账号登录</button>
        <button type="button" :class="{active:register}" :aria-pressed="register" @click="switchMode(true)">注册账号</button>
      </div>
      <form class="login-form" @submit.prevent="submit">
        <label for="username">账号</label>
        <el-input id="username" v-model="username" autocomplete="username" :placeholder="register?'至少 3 位字母、数字、下划线或短横线':'输入账号'" minlength="3" maxlength="80" pattern="[a-zA-Z0-9_\-]+" required/>
        <label for="password">密码</label>
        <el-input id="password" v-model="password" type="password" show-password :autocomplete="register?'new-password':'current-password'" :placeholder="register?'设置密码，至少 6 位':'输入密码'" minlength="6" maxlength="128" required/>
        <template v-if="register">
          <label for="confirmation">确认密码</label>
          <el-input id="confirmation" v-model="confirmation" type="password" show-password autocomplete="new-password" placeholder="再次输入密码" required/>
        </template>
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/>
        <el-button native-type="submit" type="primary" :loading="busy" class="login-submit">{{register?'注册并登录':'登录'}}</el-button>
      </form>
    </section>
  </main>
</template>