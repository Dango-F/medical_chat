<script setup>
import { ref, provide } from 'vue'
import { RouterView } from 'vue-router'

// Dark mode state
const isDarkMode = ref(false)

// Toggle dark mode
const toggleDarkMode = () => {
  isDarkMode.value = !isDarkMode.value
  document.documentElement.classList.toggle('dark', isDarkMode.value)
}

// Check system preference on mount
if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
  isDarkMode.value = true
  document.documentElement.classList.add('dark')
}

provide('darkMode', { isDarkMode, toggleDarkMode })
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
    <RouterView />
  </div>
</template>

