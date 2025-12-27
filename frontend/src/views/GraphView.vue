<script setup>
import { ref, onMounted, onUnmounted, inject, watch } from "vue";
import { useRouter } from "vue-router";
import cytoscape from "cytoscape";
import { kgAPI } from "@/services/api";

const router = useRouter();
const { isDarkMode, toggleDarkMode } = inject("darkMode");

const graphContainer = ref(null);
const cy = ref(null);
const isLoading = ref(true);
const error = ref(null);
const stats = ref(null);
const nodeTypes = ref([]);
const selectedNode = ref(null);
const searchQuery = ref("");
const activeFilters = ref([]);
const nodeLimit = ref(100); // 节点数量限制
const isReloading = ref(false); // 重新加载状态
const currentNodeCount = ref(0); // 当前加载的节点数量
const currentEdgeCount = ref(0); // 当前加载的关系数量

// Node type colors - 与后端保持一致
const nodeColors = {
  Disease: "#ef4444",
  Symptom: "#f97316",
  Drug: "#22c55e",
  Food: "#eab308",
  Check: "#3b82f6",
  Department: "#8b5cf6",
  Cure: "#14b8a6",
  Producer: "#6366f1",
  Guideline: "#3b82f6",
  Reference: "#8b5cf6",
  WarningSign: "#dc2626",
};

// Cytoscape style
const getCyStyle = () => [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "text-valign": "center",
      "text-halign": "center",
      "background-color": "data(color)",
      color: "#fff",
      "text-outline-color": "data(color)",
      "text-outline-width": 2,
      "font-size": "12px",
      width: 60,
      height: 60,
      "border-width": 2,
      "border-color": isDarkMode.value ? "#374151" : "#e5e7eb",
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 4,
      "border-color": "#3b82f6",
      width: 75,
      height: 75,
    },
  },
  {
    selector: "edge",
    style: {
      width: 2,
      "line-color": isDarkMode.value ? "#4b5563" : "#d1d5db",
      "target-arrow-color": isDarkMode.value ? "#4b5563" : "#d1d5db",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      label: "data(label)",
      "font-size": "10px",
      "text-rotation": "autorotate",
      "text-margin-y": -10,
      color: isDarkMode.value ? "#9ca3af" : "#6b7280",
    },
  },
  {
    selector: "edge:selected",
    style: {
      "line-color": "#3b82f6",
      "target-arrow-color": "#3b82f6",
      width: 3,
    },
  },
];

const initGraph = async (showFullLoading = true) => {
  if (showFullLoading) {
    isLoading.value = true;
  } else {
    isReloading.value = true;
  }
  error.value = null;

  try {
    // Load data
    const [graphData, statsData, typesData] = await Promise.all([
      kgAPI.getGraphData(nodeLimit.value),
      kgAPI.getStats(),
      kgAPI.getNodeTypes(),
    ]);

    stats.value = statsData;
    nodeTypes.value = typesData.types;

    // Transform data for Cytoscape
    const nodes = graphData.nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
        type: node.type,
        color: nodeColors[node.type] || "#6b7280",
        properties: node.properties,
      },
    }));

    const edges = graphData.edges.map((edge, index) => ({
      data: {
        id: `e${index}`,
        source: edge.source,
        target: edge.target,
        label: edge.type,
        properties: edge.properties,
      },
    }));

    // 更新当前加载的节点和关系数量
    currentNodeCount.value = nodes.length;
    currentEdgeCount.value = edges.length;

    // Initialize Cytoscape
    cy.value = cytoscape({
      container: graphContainer.value,
      elements: [...nodes, ...edges],
      style: getCyStyle(),
      layout: {
        name: "cose",
        animate: true,
        animationDuration: 500,
        nodeRepulsion: 8000,
        idealEdgeLength: 100,
        gravity: 0.25,
      },
      minZoom: 0.2,
      maxZoom: 3,
    });

    // Event handlers
    cy.value.on("tap", "node", (event) => {
      const node = event.target;
      selectedNode.value = {
        id: node.data("id"),
        label: node.data("label"),
        type: node.data("type"),
        properties: node.data("properties"),
      };
    });

    cy.value.on("tap", (event) => {
      if (event.target === cy.value) {
        selectedNode.value = null;
      }
    });
  } catch (err) {
    console.error("Failed to load graph:", err);
    error.value = "加载知识图谱失败";
  } finally {
    isLoading.value = false;
    isReloading.value = false;
  }
};

// 节点数量变化时重新加载图谱
const handleLimitChange = () => {
  initGraph(false);
};

const handleSearch = () => {
  if (!cy.value || !searchQuery.value.trim()) return;

  const query = searchQuery.value.toLowerCase();

  // Find matching nodes
  const matchedNodes = cy.value.nodes().filter((node) => {
    return node.data("label").toLowerCase().includes(query);
  });

  if (matchedNodes.length > 0) {
    // Select first match
    cy.value.nodes().unselect();
    matchedNodes[0].select();

    // Focus on matched node
    cy.value.animate(
      {
        center: { eles: matchedNodes[0] },
        zoom: 1.5,
      },
      { duration: 500 }
    );

    selectedNode.value = {
      id: matchedNodes[0].data("id"),
      label: matchedNodes[0].data("label"),
      type: matchedNodes[0].data("type"),
      properties: matchedNodes[0].data("properties"),
    };
  }
};

const filterByType = (type) => {
  if (!cy.value) return;

  const index = activeFilters.value.indexOf(type);
  if (index > -1) {
    activeFilters.value.splice(index, 1);
  } else {
    activeFilters.value.push(type);
  }

  if (activeFilters.value.length === 0) {
    // Show all nodes
    cy.value.nodes().show();
    cy.value.edges().show();
  } else {
    // Show only filtered types
    cy.value.nodes().forEach((node) => {
      if (activeFilters.value.includes(node.data("type"))) {
        node.show();
      } else {
        node.hide();
      }
    });

    // Show edges between visible nodes
    cy.value.edges().forEach((edge) => {
      const source = edge.source();
      const target = edge.target();
      if (source.visible() && target.visible()) {
        edge.show();
      } else {
        edge.hide();
      }
    });
  }
};

const resetView = () => {
  if (!cy.value) return;
  cy.value.fit();
  cy.value.nodes().unselect();
  selectedNode.value = null;
  activeFilters.value = [];
  cy.value.nodes().show();
  cy.value.edges().show();
};

const relayout = () => {
  if (!cy.value) return;
  cy.value
    .layout({
      name: "cose",
      animate: true,
      animationDuration: 500,
    })
    .run();
};

// Watch dark mode changes
watch(isDarkMode, () => {
  if (cy.value) {
    cy.value.style(getCyStyle());
  }
});

onMounted(() => {
  initGraph();
});

onUnmounted(() => {
  if (cy.value) {
    cy.value.destroy();
  }
});
</script>

<template>
  <div class="h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
    <!-- Header -->
    <header
      class="flex-shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700"
    >
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center h-14">
          <div class="flex items-center space-x-4">
            <router-link to="/" class="flex items-center space-x-2">
              <span class="text-xl">🏥</span>
              <span
                class="font-semibold text-gray-800 dark:text-white hidden sm:inline"
                >医疗知识问答</span
              >
            </router-link>
            <span class="text-gray-300 dark:text-gray-600">|</span>
            <span class="text-gray-600 dark:text-gray-300 font-medium"
              >知识图谱</span
            >
          </div>

          <div class="flex items-center space-x-2">
            <router-link to="/chat" class="btn btn-ghost text-sm">
              💬 问答
            </router-link>
            <button @click="toggleDarkMode" class="btn btn-ghost">
              <span v-if="isDarkMode">🌞</span>
              <span v-else>🌙</span>
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Sidebar -->
      <aside
        class="w-64 flex-shrink-0 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 overflow-y-auto"
      >
        <div class="p-4 space-y-6">
          <!-- Search -->
          <div>
            <label
              class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2"
            >
              搜索节点
            </label>
            <div class="relative">
              <input
                v-model="searchQuery"
                type="text"
                placeholder="输入关键词..."
                class="input text-sm pr-10"
                @keyup.enter="handleSearch"
              />
              <button
                @click="handleSearch"
                class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-primary-500"
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
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
              </button>
            </div>
          </div>

          <!-- Node Types Filter -->
          <div>
            <label
              class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2"
            >
              按类型筛选
            </label>
            <div class="space-y-2">
              <button
                v-for="type in nodeTypes"
                :key="type.id"
                @click="filterByType(type.id)"
                class="w-full flex items-center space-x-2 p-2 rounded-lg text-sm transition-colors"
                :class="
                  activeFilters.includes(type.id)
                    ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                    : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
                "
              >
                <span
                  class="w-3 h-3 rounded-full"
                  :style="{ backgroundColor: type.color }"
                ></span>
                <span>{{ type.label }}</span>
                <span
                  v-if="stats?.node_types?.[type.id]"
                  class="ml-auto text-xs text-gray-400"
                >
                  {{ stats.node_types[type.id] }}
                </span>
              </button>
            </div>
          </div>

          <!-- Actions -->
          <div class="space-y-2">
            <button @click="resetView" class="btn btn-secondary w-full text-sm">
              🔄 重置视图
            </button>
            <button @click="relayout" class="btn btn-secondary w-full text-sm">
              📐 重新布局
            </button>
          </div>

          <!-- Node Limit Slider -->
          <div>
            <input
              v-model.number="nodeLimit"
              type="range"
              min="50"
              max="500"
              step="10"
              class="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-primary-500"
              @change="handleLimitChange"
            />
            <div class="flex justify-between text-xs text-gray-400 mt-1">
              <span>50</span>
              <span>275</span>
              <span>500</span>
            </div>
            <!-- 显示当前选中的节点数量上限 -->
            <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">当前节点上限: <span class="font-medium text-gray-700 dark:text-gray-200">{{ nodeLimit }}</span></div>
            <p v-if="isReloading" class="text-xs text-primary-500 mt-2 flex items-center">
              <svg class="animate-spin h-3 w-3 mr-1" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              正在加载...
            </p>
          </div>

          <!-- Current Stats -->
          <div class="space-y-2">
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">
                节点数量
              </label>
              <p class="text-2xl font-bold text-primary-600 dark:text-primary-400">
                {{ currentNodeCount }}
              </p>
            </div>
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">
                关系数量
              </label>
              <p class="text-2xl font-bold text-primary-600 dark:text-primary-400">
                {{ currentEdgeCount }}
              </p>
            </div>
          </div>

          <!-- Stats -->
          <div
            v-if="stats"
            class="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg text-sm"
          >
            <h4 class="font-medium text-gray-700 dark:text-gray-300 mb-2">
              图谱统计
            </h4>
            <div class="space-y-1 text-gray-600 dark:text-gray-400">
              <p>节点: {{ stats.total_nodes }}</p>
              <p>关系: {{ stats.total_relationships }}</p>
            </div>
          </div>
        </div>
      </aside>

      <!-- Graph Container -->
      <div class="flex-1 relative">
        <!-- Loading -->
        <div
          v-if="isLoading"
          class="absolute inset-0 flex items-center justify-center bg-white/80 dark:bg-gray-900/80 z-10"
        >
          <div class="text-center">
            <div class="loading-dots mb-4">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <p class="text-gray-600 dark:text-gray-400">加载知识图谱...</p>
          </div>
        </div>

        <!-- Error -->
        <div
          v-if="error"
          class="absolute inset-0 flex items-center justify-center"
        >
          <div class="text-center">
            <span class="text-4xl block mb-4">❌</span>
            <p class="text-gray-600 dark:text-gray-400">{{ error }}</p>
            <button @click="initGraph" class="btn btn-primary mt-4">
              重试
            </button>
          </div>
        </div>

        <!-- Cytoscape Graph -->
        <div ref="graphContainer" class="w-full h-full"></div>

        <!-- Selected Node Info -->
        <transition name="slide">
          <div
            v-if="selectedNode"
            class="absolute bottom-4 left-4 right-4 max-w-md bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-4"
          >
            <div class="flex items-start justify-between">
              <div>
                <div class="flex items-center space-x-2 mb-2">
                  <span
                    class="w-3 h-3 rounded-full"
                    :style="{
                      backgroundColor:
                        nodeColors[selectedNode.type] || '#6b7280',
                    }"
                  ></span>
                  <span
                    class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
                  >
                    {{ selectedNode.type }}
                  </span>
                </div>
                <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
                  {{ selectedNode.label }}
                </h3>
              </div>
              <button
                @click="selectedNode = null"
                class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
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

            <p
              v-if="selectedNode.properties?.description"
              class="mt-2 text-sm text-gray-600 dark:text-gray-400"
            >
              {{ selectedNode.properties.description }}
            </p>

            <div
              v-if="Object.keys(selectedNode.properties || {}).length > 0"
              class="mt-3 flex flex-wrap gap-2"
            >
              <span
                v-for="(value, key) in selectedNode.properties"
                :key="key"
                v-show="key !== 'description'"
                class="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded text-gray-600 dark:text-gray-400"
              >
                {{ key }}: {{ value }}
              </span>
            </div>
          </div>
        </transition>

        <!-- Legend -->
        <div
          class="absolute top-4 right-4 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-3"
        >
          <h4 class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
            图例
          </h4>
          <div class="space-y-1">
            <div
              v-for="type in nodeTypes"
              :key="type.id"
              class="flex items-center space-x-2 text-xs"
            >
              <span
                class="w-2.5 h-2.5 rounded-full"
                :style="{ backgroundColor: type.color }"
              ></span>
              <span class="text-gray-600 dark:text-gray-400">{{
                type.label
              }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
