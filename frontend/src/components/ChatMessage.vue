<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  message: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['click'])

const isUser = computed(() => props.message.role === 'user')
const isLoading = computed(() => props.message.isLoading)
const isStreaming = computed(() => props.message.isStreaming)
const isError = computed(() => props.message.isError)

// 判断是否显示加载动画（只有在加载中且没有内容时才显示）
const showLoadingSpinner = computed(() => isLoading.value && !props.message.content)

// 判断是否显示流式内容（正在流式输出且有内容）
const showStreamingContent = computed(() => isStreaming.value && props.message.content)

const formattedContent = computed(() => {
  if (!props.message.content) return ''
  // Parse markdown content
  return marked(props.message.content, {
    breaks: true,
    gfm: true
  })
})

const confidenceColor = computed(() => {
  const conf = props.message.confidence
  if (!conf) return 'bg-gray-300'
  if (conf >= 0.9) return 'bg-green-500'
  if (conf >= 0.7) return 'bg-yellow-500'
  return 'bg-orange-500'
})

const confidencePercent = computed(() => {
  return Math.round((props.message.confidence || 0) * 100)
})

const handleClick = () => {
  if (!isUser.value && !isLoading.value) {
    emit('click', props.message)
  }
}
</script>

<template>
  <div 
    class="flex w-full mb-6 group"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <!-- Avatar for assistant -->
    <div v-if="!isUser" class="flex-shrink-0 mr-4 flex flex-col items-center">
      <div class="w-10 h-10 rounded-full bg-gradient-to-br from-primary-100 to-teal-50 dark:from-primary-900 dark:to-teal-900 border border-primary-200 dark:border-primary-800 flex items-center justify-center shadow-sm">
        <span class="text-lg">🏥</span>
      </div>
    </div>

    <!-- Message Bubble -->
    <div 
      class="chat-bubble relative max-w-[90%] sm:max-w-[85%] lg:max-w-[75%] outline-none focus:outline-none"
      :class="[
        isUser ? 'chat-bubble-user' : 'chat-bubble-assistant',
        isError ? 'border-red-300 bg-red-50 dark:bg-red-900/10 dark:border-red-700' : '',
        !isUser && !isLoading ? 'hover:shadow-lg transition-shadow duration-300 cursor-pointer' : ''
      ]"
      @click="handleClick"
    >
      <!-- Loading State (no content yet) -->
      <div v-if="showLoadingSpinner" class="flex items-center space-x-3 py-2 px-1">
        <div class="relative w-8 h-8">
          <div class="absolute inset-0 border-2 border-primary-200 rounded-full"></div>
          <div class="absolute inset-0 border-2 border-primary-500 rounded-full border-t-transparent animate-spin"></div>
        </div>
        <div class="flex flex-col">
          <span class="text-sm font-medium text-gray-700 dark:text-gray-200">正在思考...</span>
          <span class="text-xs text-gray-500 dark:text-gray-400">{{ message.statusMessage || '查询知识图谱中' }}</span>
        </div>
      </div>

      <!-- Streaming Content (content is being received) -->
      <div v-else-if="showStreamingContent">
        <div 
          class="markdown-content prose prose-slate dark:prose-invert max-w-none prose-p:leading-relaxed prose-a:text-primary-600 dark:prose-a:text-primary-400 hover:prose-a:underline"
          v-html="formattedContent"
        ></div>
        <!-- Streaming indicator -->
        <div class="mt-2 flex items-center space-x-2 text-xs text-gray-500 dark:text-gray-400">
          <span class="inline-flex">
            <span class="animate-pulse">●</span>
            <span class="animate-pulse animation-delay-200">●</span>
            <span class="animate-pulse animation-delay-400">●</span>
          </span>
          <span>正在生成回答...</span>
        </div>
      </div>

      <!-- Message Content (completed) -->
      <template v-else>
        <!-- User message - plain text -->
        <p v-if="isUser" class="whitespace-pre-wrap text-base leading-relaxed">{{ message.content }}</p>

        <!-- Assistant message - markdown -->
        <div v-else>
          <div 
            class="markdown-content prose prose-slate dark:prose-invert max-w-none prose-p:leading-relaxed prose-a:text-primary-600 dark:prose-a:text-primary-400 hover:prose-a:underline"
            v-html="formattedContent"
          ></div>

          <!-- Footer Info (Confidence & Evidence) -->
          <div v-if="message.confidence || message.evidence?.length" class="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700/50 space-y-3">
            
            <!-- Confidence Score -->
            <div v-if="message.confidence" class="bg-gray-50 dark:bg-gray-800/50 px-3 py-2 rounded-lg">
              <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1.5">
                <span>置信度</span>
                <span class="font-medium" :class="confidencePercent >= 70 ? 'text-green-600 dark:text-green-400' : 'text-orange-600 dark:text-orange-400'">{{ confidencePercent }}%</span>
              </div>
              <div class="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div 
                  class="h-full rounded-full transition-all duration-1000 ease-out"
                  :class="confidenceColor"
                  :style="{ width: `${confidencePercent}%` }"
                ></div>
              </div>
            </div>

            <!-- Evidence Badge -->
            <div 
              v-if="message.evidence?.length > 0" 
              class="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-primary-50 dark:bg-primary-900/20 text-xs font-medium text-primary-700 dark:text-primary-300 border border-primary-100 dark:border-primary-800/50 cursor-pointer hover:bg-primary-100 dark:hover:bg-primary-900/40 transition-colors w-fit"
            >
              <span>📚</span>
              <span>{{ message.evidence.length }} 条证据来源</span>
              <svg class="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
            </div>
          </div>

          <!-- Warning for missing evidence -->
          <div v-if="message.warnings?.length > 0" class="mt-3 space-y-2">
            <div 
              v-for="(warning, index) in message.warnings" 
              :key="index"
              class="text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-800 rounded-md px-3 py-2 flex items-start"
            >
              <span class="mr-2 text-lg leading-none">⚠️</span>
              <span class="mt-0.5">{{ warning }}</span>
            </div>
          </div>

          <!-- Disclaimer -->
          <div v-if="message.disclaimer" class="mt-3 px-3 py-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg text-[10px] text-gray-400 dark:text-gray-500 leading-tight">
            {{ message.disclaimer }}
          </div>
        </div>
      </template>
    </div>

    <!-- Avatar for user -->
    <div v-if="isUser" class="flex-shrink-0 ml-4 flex flex-col items-center">
      <div class="w-10 h-10 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center overflow-hidden">
        <span class="text-lg">👤</span>
      </div>
    </div>
  </div>
</template>

