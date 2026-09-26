import { createRouter, createWebHistory } from 'vue-router'
import { api } from './api'
import { currentUser } from './session'
import type { User } from './types'
export const router = createRouter({history: createWebHistory(), routes: [
  {path:'/',component:()=>import('./views/RequestPortal.vue')},
  {path:'/reports',component:()=>import('./views/ReportLibrary.vue')},
  {path:'/results/:id',component:()=>import('./views/ResultView.vue')},
  {path:'/login',component:()=>import('./views/LoginView.vue')},
  {path:'/admin',component:()=>import('./views/AdminView.vue')},
  {path:'/submit',redirect:'/'},{path:'/tickets',redirect:'/'},{path:'/library',redirect:'/reports'},
  {path:'/:pathMatch(.*)*',redirect:'/'}
]})

router.beforeEach(async (to) => {
  try {
    currentUser.value = await api<User>('/auth/me')
  } catch {
    currentUser.value = null
  }
  const user = currentUser.value
  if (!user && to.path !== '/login') {
    return {path: '/login', query: {redirect: to.fullPath}}
  }
  if (user && to.path === '/login') return user.role === 'admin' ? '/admin' : '/'
  if (user && to.path === '/admin' && user.role !== 'admin') return '/'
})
