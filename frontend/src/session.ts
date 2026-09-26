import { ref } from 'vue'
import type { User } from './types'

export const currentUser = ref<User | null>(null)
