<script setup>
import { ref, onMounted, inject } from "vue";
import { useRouter } from "vue-router";
import { useChatStore } from "@/stores/chat";

const router = useRouter();
const chatStore = useChatStore();
const { isDarkMode, toggleDarkMode } = inject("darkMode");

const searchQuery = ref("");
const isLoading = ref(false);

onMounted(() => {
  chatStore.loadExamples();
});

const handleSearch = async () => {
  if (!searchQuery.value.trim()) return;

  // Navigate to chat with new session flag and send the query
  router.push({ name: "chat", query: { q: searchQuery.value, new: "1" } });
};

const handleExampleClick = (example) => {
  router.push({ name: "chat", query: { q: example.query, new: "1" } });
};

// 进入问答页面时创建新会话
const goToChat = () => {
  router.push({ name: "chat", query: { new: "1" } });
};

const features = [
  {
    icon: "🔍",
    title: "智能问答",
    description: "基于知识图谱的智能医疗问答，提供准确、可靠的信息",
  },
  {
    icon: "📚",
    title: "证据溯源",
    description: "每条回答都有文献来源，可追溯至 PubMed、临床指南等权威资源",
  },
  {
    icon: "🕸️",
    title: "知识图谱",
    description: "可视化浏览疾病、症状、药物之间的关联关系",
  },
  {
    icon: "⚡",
    title: "实时响应",
    description: "快速处理您的问题，平均响应时间小于 1 min",
  },
];
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <!-- Header -->
    <header
      class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700"
    >
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center h-16">
          <div class="flex items-center space-x-3">
            <span class="text-2xl">🏥</span>
            <h1 class="text-xl font-bold text-gray-800 dark:text-white">
              医疗知识问答系统
            </h1>
          </div>
          <nav class="flex items-center space-x-4">
            <a
              @click="goToChat"
              class="text-gray-600 dark:text-gray-300 hover:text-primary-500 transition-colors cursor-pointer"
            >
              问答
            </a>
            <router-link
              to="/graph"
              class="text-gray-600 dark:text-gray-300 hover:text-primary-500 transition-colors"
            >
              知识图谱
            </router-link>
            <button
              @click="toggleDarkMode"
              class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              <span v-if="isDarkMode">🌞</span>
              <span v-else>🌙</span>
            </button>
          </nav>
        </div>
      </div>
    </header>

    <!-- Hero Section -->
    <main class="flex-1">
      <div class="relative overflow-hidden">
        <!-- Background Pattern -->
        <div
          class="absolute inset-0 bg-gradient-to-br from-blue-50 via-white to-teal-50 dark:from-gray-900 dark:via-gray-800 dark:to-teal-900/20"
        ></div>
        <div class="absolute inset-0 opacity-[0.15] dark:opacity-10">
          <svg class="w-full h-full" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern
                id="grid"
                width="40"
                height="40"
                patternUnits="userSpaceOnUse"
              >
                <path
                  d="M 40 0 L 0 0 0 40"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="0.5"
                  class="text-primary-300 dark:text-gray-600"
                />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>
        </div>

        <!-- Decorative Blobs -->
        <div
          class="absolute top-0 right-0 -mt-20 -mr-20 w-96 h-96 rounded-full bg-primary-200/30 blur-3xl filter pointer-events-none"
        ></div>
        <div
          class="absolute bottom-0 left-0 -mb-20 -ml-20 w-80 h-80 rounded-full bg-teal-200/30 blur-3xl filter pointer-events-none"
        ></div>

        <div
          class="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-24 text-center"
        >
          <div
            class="inline-flex items-center px-3 py-1 rounded-full bg-white/50 dark:bg-gray-800/50 border border-primary-100 dark:border-gray-700 backdrop-blur-sm mb-8 animate-fade-in"
          >
            <span class="flex h-2 w-2 rounded-full bg-primary-500 mr-2"></span>
            <span
              class="text-xs font-medium text-primary-700 dark:text-primary-300"
              >AI 驱动的专业医疗助手</span
            >
          </div>

          <h2
            class="text-5xl sm:text-6xl font-bold tracking-tight text-gray-900 dark:text-white mb-6"
          >
            基于知识图谱的
            <span
              class="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-teal-500 dark:from-primary-400 dark:to-teal-300"
              >医疗问答系统</span
            >
          </h2>
          <p
            class="text-xl text-gray-600 dark:text-gray-300 mb-12 max-w-2xl mx-auto leading-relaxed"
          >
            为您提供准确、可靠的医疗信息。每一条回答都基于权威数据源，并提供完整的证据溯源。
          </p>

          <!-- Search Box -->
          <div
            class="max-w-2xl mx-auto transform hover:-translate-y-1 transition-transform duration-300"
          >
            <div class="relative group">
              <div
                class="absolute -inset-1 bg-gradient-to-r from-primary-400 to-teal-400 rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-1000 group-hover:duration-200"
              ></div>
              <div
                class="relative bg-white dark:bg-gray-800 rounded-xl shadow-xl"
              >
                <input
                  v-model="searchQuery"
                  type="text"
                  placeholder="请输入您的症状或医疗问题，例如：偏头痛如何缓解？"
                  class="w-full pl-6 pr-14 py-5 text-lg rounded-xl border-none focus:ring-0 bg-transparent text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
                  @keyup.enter="handleSearch"
                />
                <button
                  @click="handleSearch"
                  class="absolute right-3 top-1/2 -translate-y-1/2 p-2.5 bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors duration-200 shadow-lg shadow-primary-500/30"
                  :disabled="!searchQuery.trim()"
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
                      d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                    />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <!-- Disclaimer -->
          <p
            class="mt-6 text-sm text-gray-500 dark:text-gray-400 flex items-center justify-center gap-2"
          >
            <svg
              class="w-4 h-4 text-amber-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            本系统仅供参考，不能替代专业医生的诊断和治疗建议
          </p>
        </div>
      </div>

      <!-- Example Questions -->
      <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <h3
          class="text-xl font-semibold text-gray-800 dark:text-white mb-6 flex items-center gap-2"
        >
          <span class="text-2xl">💡</span> 常见问题示例
        </h3>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <button
            v-for="example in chatStore.examples.slice(0, 6)"
            :key="example.id"
            @click="handleExampleClick(example)"
            class="group text-left p-5 rounded-2xl bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 hover:border-primary-200 dark:hover:border-primary-600 hover:shadow-lg hover:shadow-primary-500/5 transition-all duration-300 relative overflow-hidden"
          >
            <div
              class="absolute top-0 right-0 -mt-4 -mr-4 w-16 h-16 bg-primary-50 dark:bg-primary-900/20 rounded-full group-hover:scale-150 transition-transform duration-500"
            ></div>
            <div class="relative">
              <span
                class="inline-block px-2 py-1 rounded-md text-xs font-medium bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 mb-2"
              >
                {{ example.category }}
              </span>
              <p
                class="font-medium text-gray-700 dark:text-gray-200 group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors"
              >
                {{ example.query }}
              </p>
            </div>
          </button>
        </div>
      </div>

      <!-- Features -->
      <div
        class="bg-gray-50/50 dark:bg-gray-800/30 py-16 border-t border-gray-100 dark:border-gray-800"
      >
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div class="text-center mb-12">
            <h2 class="text-3xl font-bold text-gray-900 dark:text-white">
              为什么选择我们？
            </h2>
            <p class="mt-4 text-gray-600 dark:text-gray-400">
              结合先进的人工智能与权威医学知识库
            </p>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div
              v-for="feature in features"
              :key="feature.title"
              class="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm hover:shadow-xl hover:shadow-primary-500/5 transition-all duration-300 border border-gray-100 dark:border-gray-700"
            >
              <div
                class="w-12 h-12 rounded-xl bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center text-2xl mb-4 text-primary-500"
              >
                {{ feature.icon }}
              </div>
              <h4 class="text-lg font-bold text-gray-900 dark:text-white mb-2">
                {{ feature.title }}
              </h4>
              <p
                class="text-gray-600 dark:text-gray-400 text-sm leading-relaxed"
              >
                {{ feature.description }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Footer -->
    <footer
      class="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 py-8"
    >
      <div
        class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-gray-500 dark:text-gray-400 text-sm"
      >
        <p>© 2025 医疗知识问答系统. 仅供参考，不构成医疗建议。</p>
        <p class="mt-2">数据来源：PubMed、临床指南、DrugBank 等公开医学资源</p>
      </div>
    </footer>
  </div>
</template>
