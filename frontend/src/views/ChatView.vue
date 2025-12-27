<script setup>
import { ref, computed, watch, onMounted, nextTick, inject } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useChatStore } from "@/stores/chat";
import ChatMessage from "@/components/ChatMessage.vue";
import EvidencePanel from "@/components/EvidencePanel.vue";
import SettingsModal from "@/components/SettingsModal.vue";
import { settingsAPI } from "@/services/api";

const route = useRoute();
const router = useRouter();
const chatStore = useChatStore();
const { isDarkMode, toggleDarkMode } = inject("darkMode");

const inputMessage = ref("");
const chatContainer = ref(null);
const textareaRef = ref(null);
const showEvidence = ref(false);
const selectedMessage = ref(null);
const showSettings = ref(false);
const showSidebar = ref(false); // Mobile sidebar toggle
const llmStatus = ref(null);

// Resizable sidebar widths (px)
const leftWidth = ref(300) // default wider than before
const rightWidth = ref(420) // evidence panel default width

const minLeftWidth = 200
const maxLeftWidth = 520
const minRightWidth = 300
const maxRightWidth = 700

const dragState = ref({ active: false, side: null, startX: 0, startWidth: 0 })

function startResize(side, e) {
  dragState.value = { active: true, side, startX: e.clientX, startWidth: side === 'left' ? leftWidth.value : rightWidth.value }
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', stopResize)
}

function onMouseMove(e) {
  if (!dragState.value.active) return
  const dx = e.clientX - dragState.value.startX
  if (dragState.value.side === 'left') {
    let newW = dragState.value.startWidth + dx
    newW = Math.max(minLeftWidth, Math.min(maxLeftWidth, newW))
    leftWidth.value = newW
  } else if (dragState.value.side === 'right') {
    // moving mouse right should decrease right panel width, so subtract dx
    let newW = dragState.value.startWidth - dx
    newW = Math.max(minRightWidth, Math.min(maxRightWidth, newW))
    rightWidth.value = newW
  }
}

function stopResize() {
  dragState.value.active = false
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', stopResize)
}

// 多选删除状态
const isSelectionMode = ref(false);
const selectedSessionIds = ref(new Set());

// 最大高度限制 (px)
const MAX_TEXTAREA_HEIGHT = 200;

// 切换多选模式
const toggleSelectionMode = () => {
  isSelectionMode.value = !isSelectionMode.value;
  selectedSessionIds.value.clear();
};

// 切换会话选中状态
const toggleSessionSelection = (id) => {
  if (selectedSessionIds.value.has(id)) {
    selectedSessionIds.value.delete(id);
  } else {
    selectedSessionIds.value.add(id);
  }
};

// 是否全选
const isAllSelected = computed(() => {
  return (
    chatStore.sessions.length > 0 &&
    selectedSessionIds.value.size === chatStore.sessions.length
  );
});

// 切换全选
const toggleAll = () => {
  if (isAllSelected.value) {
    selectedSessionIds.value.clear();
  } else {
    chatStore.sessions.forEach((s) => selectedSessionIds.value.add(s.id));
  }
};

// 批量删除
const handleBatchDelete = () => {
  if (selectedSessionIds.value.size === 0) return;
  if (!confirm(`确定要删除选中的 ${selectedSessionIds.value.size} 个对话吗？`))
    return;

  chatStore.deleteSessions(Array.from(selectedSessionIds.value));
  isSelectionMode.value = false;
  selectedSessionIds.value.clear();
};

// 自动调整 textarea 高度
const adjustTextareaHeight = () => {
  const textarea = textareaRef.value;
  if (!textarea) return;

  // 先重置高度以获取正确的 scrollHeight
  textarea.style.height = "auto";
  // 设置新高度，但不超过最大值
  const newHeight = Math.min(textarea.scrollHeight, MAX_TEXTAREA_HEIGHT);
  textarea.style.height = newHeight + "px";
};

// 监听输入变化调整高度
watch(inputMessage, () => {
  nextTick(adjustTextareaHeight);
});

// 加载 LLM 状态
const loadLLMStatus = async () => {
  try {
    llmStatus.value = await settingsAPI.getLLMStatus();
  } catch (e) {
    console.error("Failed to load LLM status:", e);
  }
};

// Handle initial query from URL
onMounted(async () => {
  await chatStore.loadExamples();
  await loadLLMStatus();

  // 如果有 new 参数，创建新会话
  if (route.query.new) {
    chatStore.createNewSession();
  }

  // 如果有查询参数，发送消息
  if (route.query.q) {
    inputMessage.value = route.query.q;
    await handleSend();
  }
  
  // Clear the query params
  if (route.query.q || route.query.new) {
    router.replace({ query: {} });
  }
});

// 设置关闭后刷新状态
const onSettingsClose = async () => {
  showSettings.value = false;
  await loadLLMStatus();
};

// Auto-scroll to bottom when new messages arrive
watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick();
    scrollToBottom();
  }
);

const scrollToBottom = () => {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
  }
};

const handleSend = async () => {
  if (!inputMessage.value.trim()) return;

  const query = inputMessage.value;
  inputMessage.value = "";

  // 重置 textarea 高度
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = "auto";
    }
  });

  await chatStore.sendMessage(query);
};

const handleExampleClick = (example) => {
  inputMessage.value = example.query;
  handleSend();
};

const handleMessageClick = (message) => {
  if (message.evidence || message.kgPaths) {
    selectedMessage.value = message;
    showEvidence.value = true;
  }
};

const handleClear = () => {
  chatStore.clearMessages();
  selectedMessage.value = null;
};

const handleNewChat = () => {
  chatStore.createNewSession();
  selectedMessage.value = null;
  // If on mobile, close sidebar
  if (window.innerWidth < 768) {
    showSidebar.value = false;
  }
};

const handleSwitchSession = (id) => {
  chatStore.switchSession(id);
  selectedMessage.value = null;
  // If on mobile, close sidebar
  if (window.innerWidth < 768) {
    showSidebar.value = false;
  }
};

const handleDeleteSession = (e, id) => {
  e.stopPropagation(); // Prevent switching when clicking delete
  if (confirm("确定要删除这条对话记录吗？")) {
    chatStore.deleteSession(id);
    selectedMessage.value = null;
  }
};

const currentEvidence = computed(() => {
  return selectedMessage.value?.evidence || [];
});

const currentKgPaths = computed(() => {
  return selectedMessage.value?.kgPaths || [];
});

// Format date for session list
const formatDate = (date) => {
  if (!date) return "";
  const d = new Date(date);
  const now = new Date();
  const diff = now - d;

  if (diff < 24 * 60 * 60 * 1000 && d.getDate() === now.getDate()) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
};
</script>

<template>
  <div class="h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
    <!-- Header -->
    <header
      class="flex-shrink-0 bg-white/80 dark:bg-gray-800/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-700 z-10 sticky top-0"
    >
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center h-16">
          <div class="flex items-center space-x-4">
            <!-- Mobile Sidebar Toggle -->
            <button
              @click="showSidebar = !showSidebar"
              class="md:hidden p-2 -ml-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300"
            >
              <svg
                class="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            </button>

            <router-link to="/" class="flex items-center space-x-2 group">
              <span
                class="text-2xl transform group-hover:scale-110 transition-transform duration-200"
                >🏥</span
              >
              <span
                class="font-bold text-gray-800 dark:text-white hidden sm:inline group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors"
                >医疗知识问答</span
              >
            </router-link>
          </div>

          <div class="flex items-center space-x-2">
            <!-- 当前模型状态 -->
            <button
              @click="showSettings = true"
              class="hidden sm:flex items-center px-3 py-1.5 text-xs font-medium rounded-full bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-white dark:hover:bg-gray-700 hover:shadow-sm transition-all duration-200"
            >
              <span class="mr-1.5">
                {{
                  llmStatus?.current_provider === "siliconflow"
                    ? "🚀"
                    : llmStatus?.current_provider === "gemini"
                    ? "✨"
                    : llmStatus?.current_provider === "openai"
                    ? "🤖"
                    : "📊"
                }}
              </span>
              <span class="max-w-32 truncate">{{
                llmStatus?.current_model || "加载中..."
              }}</span>
            </button>

            <div class="h-6 w-px bg-gray-200 dark:bg-gray-700 mx-2"></div>

            <button
              @click="showEvidence = !showEvidence"
              class="btn btn-ghost text-sm rounded-full px-3"
              :class="{
                'bg-primary-50 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400':
                  showEvidence,
              }"
            >
              <svg
                class="w-5 h-5 sm:mr-1"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <span class="hidden sm:inline">证据</span>
            </button>
            <router-link
              to="/graph"
              class="btn btn-ghost text-sm rounded-full px-3"
            >
              <svg
                class="w-5 h-5 sm:mr-1"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                />
              </svg>
              <span class="hidden sm:inline">图谱</span>
            </router-link>
            <!-- 设置按钮 -->
            <button
              @click="showSettings = true"
              class="btn btn-ghost p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700"
              title="模型设置"
            >
              <svg
                class="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                />
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            </button>
            <button
              @click="handleClear"
              class="btn btn-ghost p-2 rounded-full hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/30 dark:hover:text-red-400 transition-colors"
              v-if="chatStore.hasMessages"
              title="清空本对话"
            >
              <svg
                class="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </button>
            <button
              @click="toggleDarkMode"
              class="btn btn-ghost p-2 rounded-full"
            >
              <span v-if="isDarkMode">🌞</span>
              <span v-else>🌙</span>
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <div class="flex-1 flex overflow-hidden relative">
      <!-- Chat History Sidebar -->
      <aside
        class="flex-shrink-0 flex flex-col border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 transition-transform duration-300 absolute md:static inset-y-0 left-0 z-20 md:transform-none transform"
        :class="showSidebar ? 'translate-x-0' : '-translate-x-full'"
        :style="{ width: leftWidth + 'px' }"
      >
        <!-- Consolidated Top Action Bar: Manage + New Chat (same style) -->
        <div class="p-4 border-b border-gray-100 dark:border-gray-800">
          <div class="flex flex-col gap-3">
            <!-- Normal mode: Manage (top) + New Chat (below) -->
            <template v-if="!isSelectionMode">
              <button
                @click="toggleSelectionMode"
                class="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300 rounded-xl hover:bg-primary-100 dark:hover:bg-primary-900/40 transition-colors border border-primary-100 dark:border-primary-800/50 shadow-sm"
                title="管理对话"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
                <span class="font-medium">管理对话</span>
              </button>

              <button
                @click="handleNewChat"
                class="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300 rounded-xl hover:bg-primary-100 dark:hover:bg-primary-900/40 transition-colors border border-primary-100 dark:border-primary-800/50 shadow-sm"
                title="新对话"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
                <span class="font-medium">新对话</span>
              </button>
            </template>

            <!-- Selection mode: actions + complete button (same visual style) -->
            <template v-else>
              <div class="flex items-center space-x-2">
                <button
                  @click="toggleAll"
                  class="flex-1 px-3 py-2 text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                >
                  {{ isAllSelected ? "取消" : "全选" }}
                </button>
                <button
                  @click="handleBatchDelete"
                  class="flex-1 px-3 py-2 text-sm font-medium bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  :disabled="selectedSessionIds.size === 0"
                >
                  删除 ({{ selectedSessionIds.size }})
                </button>
              </div>

              <button
                @click="toggleSelectionMode"
                class="w-full mt-2 flex items-center justify-center space-x-2 px-4 py-3 bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300 rounded-xl hover:bg-primary-100 dark:hover:bg-primary-900/40 transition-colors border border-primary-100 dark:border-primary-800/50 shadow-sm"
                title="完成管理"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4" />
                </svg>
                <span class="font-medium">完成管理</span>
              </button>
            </template>
          </div>
        </div>

        <!-- Session List -->
        <div class="flex-1 overflow-y-auto px-2 py-2 space-y-1 scrollbar-thin">
          <div
            v-for="session in chatStore.sessions"
            :key="session.id"
            @click="
              isSelectionMode
                ? toggleSessionSelection(session.id)
                : handleSwitchSession(session.id)
            "
            class="group relative flex items-center p-3 rounded-xl cursor-pointer transition-all duration-200"
            :class="[
              !isSelectionMode && chatStore.currentSessionId === session.id
                ? 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white font-medium'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50',
            ]"
          >
            <!-- Checkbox for Selection Mode -->
            <div
              v-if="isSelectionMode"
              class="mr-3 flex-shrink-0"
              @click.stop="toggleSessionSelection(session.id)"
            >
              <div
                class="w-5 h-5 rounded border flex items-center justify-center transition-colors"
                :class="
                  selectedSessionIds.has(session.id)
                    ? 'bg-primary-500 border-primary-500'
                    : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800'
                "
              >
                <svg
                  v-if="selectedSessionIds.has(session.id)"
                  class="w-3.5 h-3.5 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="3"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
            </div>

            <div class="flex-1 min-w-0 pr-8">
              <div class="truncate text-sm">
                {{ session.title || "新对话" }}
              </div>
              <div class="text-xs text-gray-400 mt-0.5">
                {{ formatDate(session.updatedAt) }}
              </div>
            </div>

            <!-- Delete Button (Visible on hover or active) - Only in Normal Mode -->
            <button
              v-if="!isSelectionMode"
              @click="handleDeleteSession($event, session.id)"
              class="absolute right-2 p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 opacity-0 group-hover:opacity-100 transition-opacity"
              :class="{
                'opacity-100': chatStore.currentSessionId === session.id,
              }"
              title="删除对话"
            >
              <svg
                class="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </button>
          </div>
        </div>

      </aside>

      <!-- Mobile Sidebar Overlay -->
      <div
        v-if="showSidebar"
        @click="showSidebar = false"
        class="absolute inset-0 bg-black/50 z-10 md:hidden backdrop-blur-sm transition-opacity"
      ></div>

      <!-- Left Resizer (drag to resize left sidebar) -->
      <div
        class="hidden md:flex items-center justify-center cursor-col-resize select-none"
        style="width: 8px"
        @mousedown.prevent="startResize('left', $event)"
        title="拖动调整侧边栏宽度"
      >
        <div class="w-px h-12 bg-gray-200 dark:bg-gray-700"></div>
      </div>

      <!-- Chat Area -->
      <div class="flex-1 flex flex-col min-w-0">
        <!-- Messages -->
        <div
          ref="chatContainer"
          class="flex-1 overflow-y-auto px-4 py-6 scroll-smooth"
        >
          <!-- Welcome message when empty -->
          <div v-if="!chatStore.hasMessages" class="max-w-2xl mx-auto py-12">
            <div class="text-center mb-12">
              <div
                class="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-primary-100 dark:bg-primary-900/30 text-5xl mb-6 shadow-lg shadow-primary-500/10"
              >
                👋
              </div>
              <h2 class="text-3xl font-bold text-gray-800 dark:text-white mb-4">
                欢迎使用医疗知识问答系统
              </h2>
              <p
                class="text-lg text-gray-600 dark:text-gray-400 max-w-lg mx-auto"
              >
                我可以帮助您了解疾病、症状、用药等医疗相关信息，所有回答都有来源支持。
              </p>
            </div>

            <!-- Example Questions -->
            <div class="mb-8">
              <h3
                class="text-sm font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-4 text-center"
              >
                您可以这样问我
              </h3>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <button
                  v-for="example in chatStore.examples.slice(0, 4)"
                  :key="example.id"
                  @click="handleExampleClick(example)"
                  class="text-left p-4 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-primary-400 dark:hover:border-primary-500 hover:shadow-md transition-all duration-200 text-gray-700 dark:text-gray-200 group"
                >
                  <span
                    class="text-primary-500 mr-2 opacity-50 group-hover:opacity-100"
                    >●</span
                  >
                  {{ example.query }}
                </button>
              </div>
            </div>

            <!-- Disclaimer -->
            <div
              class="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-xl flex items-start space-x-3"
            >
              <span class="text-amber-500 text-xl mt-0.5">⚠️</span>
              <div class="text-sm text-amber-800 dark:text-amber-200">
                <p class="font-bold mb-1">重要免责声明</p>
                <p>
                  本系统输出内容由 AI 生成，仅供医疗信息参考，<span
                    class="font-bold underline"
                    >绝不能</span
                  >替代专业医生的诊断和治疗建议。如有身体不适，请务必及时就医。
                </p>
              </div>
            </div>
          </div>

          <!-- Chat Messages -->
          <div v-else class="max-w-3xl mx-auto space-y-6 pb-4">
            <ChatMessage
              v-for="message in chatStore.messages"
              :key="message.id"
              :message="message"
              @click="handleMessageClick(message)"
              :class="{
                'bg-primary-50/50 dark:bg-primary-900/10 rounded-2xl':
                  selectedMessage?.id === message.id,
              }"
            />
          </div>
        </div>

        <!-- Input Area -->
        <div class="flex-shrink-0 bg-transparent p-4 pb-6">
          <div class="max-w-3xl mx-auto">
            <div
              class="flex items-end bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden transition-shadow p-2"
            >
              <textarea
                ref="textareaRef"
                v-model="inputMessage"
                placeholder="请输入您的症状或医疗问题，例如：偏头痛如何缓解？"
                class="flex-1 w-full pl-4 py-3 bg-transparent border-none focus:ring-0 focus:outline-none outline-none resize-none text-gray-800 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
                rows="1"
                @keydown.enter.exact.prevent="handleSend"
                @input="adjustTextareaHeight"
                style="min-height: 48px; max-height: 200px; overflow-y: auto"
              ></textarea>

              <div class="flex-shrink-0 pb-1.5 pr-1">
                <button
                  @click="handleSend"
                  class="btn p-2 rounded-xl transition-all duration-200"
                  :class="
                    inputMessage.trim()
                      ? 'bg-primary-500 text-white hover:bg-primary-600 shadow-md'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                  "
                  :disabled="!inputMessage.trim()"
                  :title="
                    chatStore.isCurrentLoading
                      ? '发送将取消当前请求并重新提问'
                      : '发送消息'
                  "
                >
                  <svg
                    v-if="!chatStore.isCurrentLoading"
                    class="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M5 12h14M12 5l7 7-7 7"
                    />
                  </svg>
                  <svg
                    v-else
                    class="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                </button>
              </div>
            </div>
            <p
              class="text-xs text-gray-400 dark:text-gray-500 mt-2 text-center"
            >
              {{
                chatStore.isCurrentLoading
                  ? "正在等待回复，再次发送将重新提问"
                  : "AI 内容仅供参考，请核实重要信息"
              }}
            </p>
          </div>
        </div>
      </div>

      <!-- Right Resizer (drag to resize evidence panel) -->
      <div
        v-if="showEvidence && selectedMessage"
        class="hidden md:flex items-center justify-center cursor-col-resize select-none"
        style="width: 8px"
        @mousedown.prevent="startResize('right', $event)"
        title="拖动调整证据面板宽度"
      >
        <div class="w-px h-12 bg-gray-200 dark:bg-gray-700"></div>
      </div>

      <!-- Evidence Panel (Right Sidebar) -->
      <transition name="slide">
        <aside
          v-if="showEvidence && selectedMessage"
          class="flex-shrink-0 border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden hidden md:block"
          :style="{ width: rightWidth + 'px' }"
        >
          <EvidencePanel
            :evidence="currentEvidence"
            :kg-paths="currentKgPaths"
            :confidence="selectedMessage?.confidence"
            @close="showEvidence = false"
          />
        </aside>
      </transition>
    </div>

    <!-- Settings Modal -->
    <SettingsModal v-if="showSettings" @close="onSettingsClose" />
  </div>
</template>
