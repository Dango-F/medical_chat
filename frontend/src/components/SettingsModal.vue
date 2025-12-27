<script setup>
import { ref, onMounted, computed } from "vue";
import { settingsAPI } from "@/services/api";

const emit = defineEmits(["close"]);

const isLoading = ref(false);
const isTesting = ref(false);
const testResult = ref(null);
const error = ref(null);

const llmStatus = ref(null);
const selectedProvider = ref("siliconflow"); // 默认使用硅基流动
const apiKey = ref("");
const selectedModel = ref("");
const baseUrl = ref("");
const hasDefaultApiKey = ref(false); // 当前提供商是否有默认的 API Key
const useKgOnly = ref(false); // 仅使用知识图谱模式（不使用 LLM）

// 目前只支持硅基流动
const supportedProviders = ["siliconflow"];
const isProviderSupported = (providerId) =>
  supportedProviders.includes(providerId);

// 加载当前状态
onMounted(async () => {
  await loadStatus();
});

const loadStatus = async () => {
  isLoading.value = true;
  try {
    const status = await settingsAPI.getLLMStatus();
    llmStatus.value = status;

    // 检查当前是否为 mock 模式（仅知识图谱）
    useKgOnly.value = status.current_provider === "mock";

    // 默认使用硅基流动（目前只支持这个）
    selectedProvider.value = "siliconflow";

    // 设置默认模型
    const provider = status.available_providers.find(
      (p) => p.id === selectedProvider.value
    );
    if (provider && provider.models.length > 0) {
      // 如果当前使用的就是硅基流动，尝试匹配当前模型
      if (status.current_provider === "siliconflow" && status.current_model) {
        // 先尝试精确匹配
        const exactMatch = provider.models.find(
          (m) => m.id === status.current_model
        );
        if (exactMatch) {
          selectedModel.value = exactMatch.id;
        } else {
          // 尝试模糊匹配：提取模型名称的基础部分进行比较
          // 例如 deepseek-ai/DeepSeek-V3.2 和 deepseek-ai/DeepSeek-V3
          const currentModelBase = status.current_model.replace(/[.\d]+$/, ""); // 去掉末尾的版本号
          const fuzzyMatch = provider.models.find((m) => {
            const modelBase = m.id.replace(/[.\d]+$/, "");
            return (
              currentModelBase === modelBase ||
              status.current_model.startsWith(m.id) ||
              m.id.startsWith(status.current_model)
            );
          });
          selectedModel.value = fuzzyMatch
            ? fuzzyMatch.id
            : provider.models[0].id;
        }
      } else {
        selectedModel.value = provider.models[0].id;
      }
    }

    // 检查当前提供商是否有默认 API Key
    hasDefaultApiKey.value =
      status.has_api_key?.[selectedProvider.value] || false;
  } catch (e) {
    error.value = "加载配置失败: " + e.message;
  } finally {
    isLoading.value = false;
  }
};

// 当前选择的提供商信息
const currentProviderInfo = computed(() => {
  if (!llmStatus.value) return null;
  return llmStatus.value.available_providers.find(
    (p) => p.id === selectedProvider.value
  );
});

// 可用模型列表
const availableModels = computed(() => {
  return currentProviderInfo.value?.models || [];
});

// 是否需要 API Key
const needsApiKey = computed(() => {
  return currentProviderInfo.value?.requires_key || false;
});

// 提供商变化时重置
const onProviderChange = () => {
  apiKey.value = "";
  testResult.value = null;
  error.value = null;

  const provider = currentProviderInfo.value;
  if (provider) {
    selectedModel.value = provider.models[0]?.id || "";
    baseUrl.value = provider.base_url || "";
  }

  // 更新是否有默认 API Key
  hasDefaultApiKey.value =
    llmStatus.value?.has_api_key?.[selectedProvider.value] || false;
};

// 测试连接
const testConnection = async () => {
  // 如果需要 API Key 但既没有输入也没有默认配置
  if (needsApiKey.value && !apiKey.value && !hasDefaultApiKey.value) {
    error.value = "请输入 API Key";
    return;
  }

  isTesting.value = true;
  testResult.value = null;
  error.value = null;

  try {
    const result = await settingsAPI.testLLM({
      provider: selectedProvider.value,
      api_key: apiKey.value || undefined, // 如果没有输入，传 undefined 让后端用默认的
      model: selectedModel.value,
      base_url: baseUrl.value || undefined,
    });
    testResult.value = result;
  } catch (e) {
    error.value = "测试失败: " + e.message;
  } finally {
    isTesting.value = false;
  }
};

// 切换仅知识图谱模式
const toggleKgOnlyMode = async () => {
  isLoading.value = true;
  error.value = null;
  testResult.value = null;

  try {
    if (!useKgOnly.value) {
      // 开启仅知识图谱模式
      const result = await settingsAPI.updateLLM({ provider: "mock" });
      if (result.success) {
        useKgOnly.value = true;
        await loadStatus();
      } else {
        error.value = result.message;
      }
    } else {
      // 关闭仅知识图谱模式，恢复到 siliconflow
      useKgOnly.value = false;
    }
  } catch (e) {
    error.value = "切换失败: " + e.message;
  } finally {
    isLoading.value = false;
  }
};

// 保存配置
const saveConfig = async () => {
  // 如果开启了仅知识图谱模式，直接保存 mock
  if (useKgOnly.value) {
    isLoading.value = true;
    error.value = null;
    try {
      const result = await settingsAPI.updateLLM({ provider: "mock" });
      if (result.success) {
        await loadStatus();
        emit("close");
      } else {
        error.value = result.message;
      }
    } catch (e) {
      error.value = "保存失败: " + e.message;
    } finally {
      isLoading.value = false;
    }
    return;
  }

  // 如果需要 API Key 但既没有输入也没有默认配置
  if (needsApiKey.value && !apiKey.value && !hasDefaultApiKey.value) {
    error.value = "请输入 API Key";
    return;
  }

  isLoading.value = true;
  error.value = null;

  try {
    const result = await settingsAPI.updateLLM({
      provider: selectedProvider.value,
      api_key: apiKey.value || undefined, // 如果没有输入，传 undefined 让后端用默认的
      model: selectedModel.value,
      base_url: baseUrl.value || undefined,
    });

    if (result.success) {
      await loadStatus();
      emit("close");
    } else {
      error.value = result.message;
    }
  } catch (e) {
    error.value = "保存失败: " + (e.response?.data?.detail || e.message);
  } finally {
    isLoading.value = false;
  }
};

// 获取提供商图标
const getProviderIcon = (providerId) => {
  const icons = {
    siliconflow: "🚀",
    gemini: "✨",
    openai: "🤖",
    mock: "📊",
  };
  return icons[providerId] || "🔧";
};
</script>

<template>
  <div class="fixed inset-0 z-50 overflow-y-auto">
    <!-- Backdrop -->
    <div
      class="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
      @click="$emit('close')"
    ></div>

    <!-- Modal -->
    <div class="flex min-h-full items-center justify-center p-4">
      <div
        class="relative w-full max-w-lg bg-white dark:bg-gray-800 rounded-2xl shadow-2xl transform transition-all border border-gray-200 dark:border-gray-700"
      >
        <!-- Header -->
        <div
          class="flex items-center justify-between p-5 border-b border-gray-100 dark:border-gray-700"
        >
          <h2
            class="text-xl font-bold text-gray-900 dark:text-white flex items-center"
          >
            <span class="mr-2 text-2xl">⚙️</span>
            模型设置
          </h2>
          <button
            @click="$emit('close')"
            class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
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
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <!-- Content -->
        <div class="p-6 space-y-6">
          <!-- 当前状态 -->
          <div
            v-if="llmStatus"
            class="p-4 bg-primary-50 dark:bg-primary-900/20 rounded-xl border border-primary-100 dark:border-primary-800/50"
          >
            <div class="text-xs font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400 mb-1">
              当前使用
            </div>
            <div
              class="font-semibold text-gray-900 dark:text-white flex items-center text-lg"
            >
              <span class="mr-2">{{
                getProviderIcon(llmStatus.current_provider)
              }}</span>
              {{ llmStatus.current_model }}
            </div>
          </div>

          <!-- 仅使用知识图谱模式开关 -->
          <div class="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-xl border border-amber-200 dark:border-amber-800/50">
            <div class="flex items-center justify-between">
              <div class="flex-1">
                <div class="flex items-center">
                  <span class="text-lg mr-2">📊</span>
                  <span class="font-semibold text-gray-900 dark:text-white">仅使用知识图谱</span>
                </div>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  开启后不调用 AI 大模型，仅根据知识图谱数据回答问题，响应更快但回答可能不够智能
                </p>
              </div>
              <button
                @click="toggleKgOnlyMode"
                :disabled="isLoading"
                :class="[
                  'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                  useKgOnly ? 'bg-primary-500' : 'bg-gray-200 dark:bg-gray-600'
                ]"
              >
                <span
                  :class="[
                    'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                    useKgOnly ? 'translate-x-5' : 'translate-x-0'
                  ]"
                />
              </button>
            </div>
          </div>

          <!-- 提供商选择 -->
          <div :class="{ 'opacity-50 pointer-events-none': useKgOnly }">
            <label
              class="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3"
            >
              选择模型提供商
              <span class="text-xs font-normal text-gray-400 ml-2"
                >{{ useKgOnly ? '（已开启仅知识图谱模式）' : '（目前仅支持硅基流动）' }}</span
              >
            </label>
            <div class="grid grid-cols-2 gap-3">
              <button
                v-for="provider in llmStatus?.available_providers"
                :key="provider.id"
                @click="
                  isProviderSupported(provider.id) &&
                    ((selectedProvider = provider.id), onProviderChange())
                "
                :disabled="!isProviderSupported(provider.id)"
                :class="[
                  'p-4 rounded-xl border-2 text-left transition-all relative',
                  !isProviderSupported(provider.id)
                    ? 'border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 opacity-60 cursor-not-allowed'
                    : selectedProvider === provider.id
                    ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20 shadow-md shadow-primary-500/10'
                    : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 bg-white dark:bg-gray-800 cursor-pointer',
                ]"
              >
                <div class="flex items-center mb-1">
                  <span
                    class="mr-2 text-xl"
                    :class="{ 'opacity-50': !isProviderSupported(provider.id) }"
                    >{{ getProviderIcon(provider.id) }}</span
                  >
                  <span
                    :class="[
                      'font-bold text-sm',
                      isProviderSupported(provider.id)
                        ? 'text-gray-900 dark:text-white'
                        : 'text-gray-400 dark:text-gray-500',
                    ]"
                    >{{ provider.name }}</span
                  >
                </div>
                <p
                  :class="[
                    'text-xs',
                    isProviderSupported(provider.id)
                      ? 'text-gray-500 dark:text-gray-400'
                      : 'text-gray-400 dark:text-gray-600',
                  ]"
                >
                  {{ provider.description }}
                </p>
                <!-- 不支持标签 -->
                <span
                  v-if="!isProviderSupported(provider.id)"
                  class="absolute top-2 right-2 text-[10px] font-bold px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded"
                >
                  暂不支持
                </span>
              </button>
            </div>
          </div>

          <!-- API Key 输入 -->
          <div v-if="needsApiKey && !useKgOnly" :class="{ 'opacity-50 pointer-events-none': useKgOnly }">
            <label
              class="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2"
            >
              API Key
              <span v-if="hasDefaultApiKey" class="text-green-500 text-xs ml-2 font-medium"
                >✓ 已配置</span
              >
            </label>
            <input
              v-model="apiKey"
              type="password"
              :placeholder="
                hasDefaultApiKey
                  ? '••••••••••••••••（已有默认配置，留空使用默认）'
                  : '输入你的 API Key'
              "
              class="input"
            />
            <p class="mt-2 text-xs text-gray-500 dark:text-gray-400">
              <template v-if="selectedProvider === 'siliconflow'">
                获取 API Key:
                <a
                  href="https://cloud.siliconflow.cn/"
                  target="_blank"
                  class="text-primary-500 hover:text-primary-600 hover:underline font-medium"
                  >cloud.siliconflow.cn</a
                >
              </template>
              <template v-else-if="selectedProvider === 'gemini'">
                获取 API Key:
                <a
                  href="https://aistudio.google.com/app/apikey"
                  target="_blank"
                  class="text-primary-500 hover:text-primary-600 hover:underline font-medium"
                  >aistudio.google.com</a
                >
              </template>
              <template v-else-if="selectedProvider === 'openai'">
                获取 API Key:
                <a
                  href="https://platform.openai.com/api-keys"
                  target="_blank"
                  class="text-primary-500 hover:text-primary-600 hover:underline font-medium"
                  >platform.openai.com</a
                >
              </template>
            </p>
          </div>

          <!-- 模型选择 -->
          <div v-if="availableModels.length > 1 && !useKgOnly" :class="{ 'opacity-50 pointer-events-none': useKgOnly }">
            <label
              class="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2"
            >
              选择模型
            </label>
            <div class="relative">
              <select
                v-model="selectedModel"
                class="input appearance-none"
              >
                <option
                  v-for="model in availableModels"
                  :key="model.id"
                  :value="model.id"
                >
                  {{ model.name }}
                </option>
              </select>
              <div class="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none">
                <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
              </div>
            </div>
          </div>

          <!-- 错误提示 -->
          <div
            v-if="error"
            class="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl flex items-start gap-3"
          >
            <svg class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <p class="text-sm text-red-600 dark:text-red-400 font-medium">{{ error }}</p>
          </div>

          <!-- 测试结果 -->
          <div
            v-if="testResult"
            :class="[
              'p-4 rounded-xl border flex items-start gap-3',
              testResult.success
                ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800',
            ]"
          >
            <span class="text-xl flex-shrink-0">{{ testResult.success ? "✅" : "❌" }}</span>
            <div class="flex-1 min-w-0">
              <p
                :class="[
                  'text-sm font-medium',
                  testResult.success
                    ? 'text-green-700 dark:text-green-300'
                    : 'text-red-700 dark:text-red-300',
                ]"
              >
                {{ testResult.message }}
              </p>
              <p v-if="testResult.response" class="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
                响应: {{ testResult.response }}
              </p>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div
          class="flex items-center justify-between p-5 border-t border-gray-100 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50 rounded-b-2xl"
        >
          <button
            @click="testConnection"
            :disabled="
              isTesting || useKgOnly || (needsApiKey && !apiKey && !hasDefaultApiKey)
            "
            class="btn btn-secondary text-sm"
            :class="{ 'opacity-50 cursor-not-allowed': useKgOnly }"
          >
            <svg v-if="!isTesting" class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            <div v-else class="loading-dots mr-2"><span></span><span></span><span></span></div>
            <span>{{ isTesting ? '测试中...' : '测试连接' }}</span>
          </button>

          <div class="flex space-x-3">
            <button
              @click="$emit('close')"
              class="btn btn-secondary text-sm"
            >
              取消
            </button>
            <button
              @click="saveConfig"
              :disabled="
                isLoading || (!useKgOnly && needsApiKey && !apiKey && !hasDefaultApiKey)
              "
              class="btn btn-primary text-sm shadow-lg shadow-primary-500/20"
            >
              <div v-if="isLoading" class="loading-dots mr-2"><span></span><span></span><span></span></div>
              <span>{{ isLoading ? '保存中...' : '保存设置' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
