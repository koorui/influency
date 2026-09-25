import { createRouter, createWebHistory } from 'vue-router'
export const router = createRouter({history: createWebHistory(), routes: [
  {path: '/submit', component: () => import('./views/SubmissionView.vue')},
  {path: '/', component: () => import('./views/SearchView.vue')}, {path: '/tickets', component: () => import('./views/TicketsView.vue')},
  {path: '/results/:id', component: () => import('./views/ResultView.vue')}, {path: '/login', component: () => import('./views/LoginView.vue')},
  {path: '/admin', component: () => import('./views/AdminView.vue')}, {path: '/:pathMatch(.*)*', redirect: '/'}
]})
