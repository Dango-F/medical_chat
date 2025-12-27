<script setup>
import { ref, computed, watch, nextTick, inject, onUnmounted } from "vue";
import cytoscape from "cytoscape";

const props = defineProps({
  evidence: {
    type: Array,
    default: () => [],
  },
  kgPaths: {
    type: Array,
    default: () => [],
  },
  confidence: {
    type: Number,
    default: null,
  },
});

const emit = defineEmits(["close"]);
const { isDarkMode } = inject("darkMode");

const activeTab = ref("kg");
const viewMode = ref("list"); // 'list' or 'graph'
const graphContainer = ref(null);
const cy = ref(null);
const selectedNode = ref(null);

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
      "font-size": "10px",
      width: 40,
      height: 40,
      "border-width": 2,
      "border-color": isDarkMode.value ? "#374151" : "#e5e7eb",
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 3,
      "border-color": "#3b82f6",
      width: 50,
      height: 50,
    },
  },
  {
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": isDarkMode.value ? "#4b5563" : "#d1d5db",
      "target-arrow-color": isDarkMode.value ? "#4b5563" : "#d1d5db",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      label: "data(label)",
      "font-size": "8px",
      "text-rotation": "autorotate",
      "text-margin-y": -5,
      color: isDarkMode.value ? "#9ca3af" : "#6b7280",
    },
  },
];

const initGraph = () => {
  if (!graphContainer.value || props.kgPaths.length === 0) return;

  // Clean up existing instance
  if (cy.value) {
    cy.value.destroy();
  }

  // Process data: Extract unique nodes and edges from all paths
  const nodesMap = new Map();
  const edgesMap = new Map();

  props.kgPaths.forEach((path) => {
    // Process nodes
    path.nodes.forEach((node) => {
      if (!nodesMap.has(node.id)) {
        nodesMap.set(node.id, {
          data: {
            id: node.id,
            label: node.label,
            type: node.type,
            color: nodeColors[node.type] || "#6b7280",
            properties: node.properties,
          },
        });
      }
    });

    // Process edges
    path.edges.forEach((edge, idx) => {
      // Create a unique ID for edge based on source-target-type
      const edgeId = `${edge.source}-${edge.target}-${edge.type}`;
      if (!edgesMap.has(edgeId)) {
        edgesMap.set(edgeId, {
          data: {
            id: edgeId,
            source: edge.source,
            target: edge.target,
            label: edge.type,
            properties: edge.properties,
          },
        });
      }
    });
  });

  cy.value = cytoscape({
    container: graphContainer.value,
    elements: [...nodesMap.values(), ...edgesMap.values()],
    style: getCyStyle(),
    layout: {
      name: "cose",
      animate: true,
      animationDuration: 500,
      nodeRepulsion: 4000,
      idealEdgeLength: 60,
      gravity: 0.25,
      padding: 10,
    },
    minZoom: 0.5,
    maxZoom: 2,
    wheelSensitivity: 0.2,
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
};

// Watchers
watch([activeTab, viewMode], async ([newTab, newMode]) => {
  if (newTab === "kg" && newMode === "graph") {
    await nextTick();
    initGraph();
  }
});

watch(
  () => props.kgPaths,
  () => {
    if (activeTab.value === "kg" && viewMode.value === "graph") {
      initGraph();
    }
  }
);

watch(isDarkMode, () => {
  if (cy.value) {
    cy.value.style(getCyStyle());
  }
});

onUnmounted(() => {
  if (cy.value) {
    cy.value.destroy();
  }
});

const sourceTypeLabels = {
  pubmed: { label: "PubMed", class: "evidence-badge-pubmed" },
  guideline: { label: "临床指南", class: "evidence-badge-guideline" },
  drugbank: { label: "DrugBank", class: "evidence-badge-drugbank" },
  knowledge_graph: {
    label: "知识图谱",
    class: "bg-purple-100 text-purple-800",
  },
  other: { label: "其他", class: "bg-gray-100 text-gray-800" },
};

const getSourceTypeInfo = (type) => {
  return sourceTypeLabels[type] || sourceTypeLabels.other;
};

const confidenceLevel = computed(() => {
  const conf = props.confidence;
  if (!conf) return { text: "未知", color: "text-gray-500" };
  if (conf >= 0.9) return { text: "非常高", color: "text-green-600" };
  if (conf >= 0.8) return { text: "高", color: "text-green-500" };
  if (conf >= 0.7) return { text: "中等", color: "text-yellow-600" };
  return { text: "较低", color: "text-orange-500" };
});

const openExternalLink = (url) => {
  if (url) {
    window.open(url, "_blank", "noopener,noreferrer");
  }
};

const getPubMedUrl = (pmid) => {
  return `https://pubmed.ncbi.nlm.nih.gov/${pmid}`;
};
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div
      class="flex-shrink-0 p-4 border-b border-gray-200 dark:border-gray-700"
    >
      <div class="flex items-center justify-between">
        <h3 class="font-semibold text-gray-800 dark:text-white">证据详情</h3>
        <button
          @click="emit('close')"
          class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
        >
          <svg
            class="w-5 h-5 text-gray-500"
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

      <!-- Confidence Overview -->
      <div
        v-if="confidence"
        class="mt-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
      >
        <div class="flex items-center justify-between text-sm">
          <span class="text-gray-600 dark:text-gray-400">整体置信度</span>
          <span class="font-semibold" :class="confidenceLevel.color">
            {{ Math.round(confidence * 100) }}% ({{ confidenceLevel.text }})
          </span>
        </div>
      </div>

      <!-- Tabs -->
      <div
        class="mt-4 flex space-x-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1"
      >
        <button
          @click="activeTab = 'kg'"
          class="flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors"
          :class="
            activeTab === 'kg'
              ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
          "
        >
          知识图谱 ({{ kgPaths.length }})
        </button>
        <button
          @click="activeTab = 'evidence'"
          class="flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors"
          :class="
            activeTab === 'evidence'
              ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
          "
        >
          文献证据 ({{ evidence.length }})
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-4">
      <!-- Evidence Tab -->
      <div v-if="activeTab === 'evidence'" class="space-y-4">
        <div
          v-if="evidence.length === 0"
          class="text-center py-8 text-gray-500 dark:text-gray-400"
        >
          <span class="text-3xl block mb-2">📭</span>
          <p>暂无证据数据</p>
        </div>

        <div
          v-for="(item, index) in evidence"
          :key="index"
          class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-xl space-y-3"
        >
          <!-- Source Header -->
          <div class="flex items-start justify-between">
            <div class="flex items-center space-x-2">
              <span
                class="evidence-badge"
                :class="getSourceTypeInfo(item.source_type).class"
              >
                {{ getSourceTypeInfo(item.source_type).label }}
              </span>
              <span
                class="text-sm font-medium text-gray-700 dark:text-gray-200"
              >
                {{ item.source }}
              </span>
            </div>
            <div class="flex items-center space-x-1">
              <span class="text-xs text-gray-500">置信度:</span>
              <span
                class="text-sm font-semibold"
                :class="
                  item.confidence >= 0.8 ? 'text-green-600' : 'text-yellow-600'
                "
              >
                {{ Math.round(item.confidence * 100) }}%
              </span>
            </div>
          </div>

          <!-- Section/Title -->
          <div
            v-if="item.section"
            class="text-sm font-medium text-gray-800 dark:text-gray-100"
          >
            {{ item.section }}
          </div>

          <!-- Snippet -->
          <p class="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
            {{ item.snippet }}
          </p>

          <!-- Metadata -->
          <div
            class="flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400"
          >
            <span v-if="item.publication_date">
              📅 {{ item.publication_date }}
            </span>
            <span v-if="item.pmid"> PMID: {{ item.pmid }} </span>
            <span v-if="item.doi"> DOI: {{ item.doi }} </span>
          </div>

          <!-- Link -->
          <div class="pt-2 border-t border-gray-200 dark:border-gray-600">
            <button
              v-if="item.url"
              @click="openExternalLink(item.url)"
              class="text-sm text-primary-500 hover:text-primary-600 flex items-center space-x-1"
            >
              <span>查看原文</span>
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
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                />
              </svg>
            </button>
            <button
              v-else-if="item.pmid"
              @click="openExternalLink(getPubMedUrl(item.pmid))"
              class="text-sm text-primary-500 hover:text-primary-600 flex items-center space-x-1"
            >
              <span>在 PubMed 中查看</span>
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
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Knowledge Graph Tab -->
      <div v-if="activeTab === 'kg'" class="space-y-4 h-full flex flex-col">
        <!-- View Toggle Toolbar -->
        <div
          class="flex-shrink-0 flex items-center justify-between mb-2 px-1"
          v-if="kgPaths.length > 0"
        >
          <span
            class="text-xs font-medium text-gray-500 dark:text-gray-400 flex items-center pl-1"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-primary-500 mr-2"></span>
            共 {{ kgPaths.length }} 条推理路径
          </span>

          <div
            class="bg-gray-100 dark:bg-gray-700/50 p-1 rounded-lg flex border border-gray-200 dark:border-gray-600/50"
          >
            <button
              @click="viewMode = 'list'"
              class="flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200"
              :class="
                viewMode === 'list'
                  ? 'bg-white dark:bg-gray-600 text-primary-600 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-200/50 dark:hover:bg-gray-600/50'
              "
            >
              <svg
                class="w-3.5 h-3.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 6h16M4 12h16M4 18h7"
                />
              </svg>
              <span>列表</span>
            </button>
            <button
              @click="viewMode = 'graph'"
              class="flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200"
              :class="
                viewMode === 'graph'
                  ? 'bg-white dark:bg-gray-600 text-primary-600 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-200/50 dark:hover:bg-gray-600/50'
              "
            >
              <svg
                class="w-3.5 h-3.5"
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
              <span>图谱</span>
            </button>
          </div>
        </div>

        <div
          v-if="kgPaths.length === 0"
          class="text-center py-8 text-gray-500 dark:text-gray-400"
        >
          <span class="text-3xl block mb-2">🕸️</span>
          <p>暂无知识图谱路径</p>
        </div>

        <!-- List View -->
        <div v-if="viewMode === 'list'" class="space-y-4 overflow-y-auto pb-4">
          <div
            v-for="(path, pathIndex) in kgPaths"
            :key="pathIndex"
            class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-xl"
          >
            <div class="flex items-center justify-between mb-3">
              <div>
                <span class="text-sm font-medium text-gray-700 dark:text-gray-200">路径 {{ pathIndex + 1 }}</span>
                <div class="text-xs text-gray-500">来源: {{ path.source || '未知' }} · 置信度: {{ Math.round((path.confidence ?? path.relevance_score) * 100) }}%</div>
              </div>
              <span class="text-xs text-gray-500">
                相关性: {{ Math.round(path.relevance_score * 100) }}%
              </span>
            </div>

            <!-- Path Visualization -->
            <div class="flex flex-wrap items-center gap-2">
              <template v-for="(node, nodeIndex) in path.nodes" :key="node.id">
                <!-- Node -->
                <div
                  class="px-3 py-1.5 rounded-full text-sm font-medium"
                  :class="{
                    'bg-disease/10 text-disease border border-disease/30':
                      node.type === 'Disease',
                    'bg-symptom/10 text-symptom border border-symptom/30':
                      node.type === 'Symptom',
                    'bg-drug/10 text-drug border border-drug/30':
                      node.type === 'Drug',
                    'bg-food/10 text-food border border-food/30':
                      node.type === 'Food',
                    'bg-check/10 text-check border border-check/30':
                      node.type === 'Check',
                    'bg-department/10 text-department border border-department/30':
                      node.type === 'Department',
                    'bg-cure/10 text-cure border border-cure/30':
                      node.type === 'Cure',
                    'bg-producer/10 text-producer border border-producer/30':
                      node.type === 'Producer',
                    'bg-guideline/10 text-guideline border border-guideline/30':
                      node.type === 'Guideline',
                    'bg-reference/10 text-reference border border-reference/30':
                      node.type === 'Reference',
                    'bg-warning/10 text-warning border border-warning/30':
                      node.type === 'WarningSign',
                    'bg-gray-100 text-gray-700 dark:bg-gray-600 dark:text-gray-200 border border-gray-300 dark:border-gray-500': ![
                      'Disease',
                      'Symptom',
                      'Drug',
                      'Food',
                      'Check',
                      'Department',
                      'Cure',
                      'Producer',
                      'Guideline',
                      'Reference',
                      'WarningSign',
                    ].includes(node.type),
                  }"
                >
                  {{ node.label }}
                </div>

                <!-- Arrow -->
                <svg
                  v-if="nodeIndex < path.nodes.length - 1"
                  class="w-5 h-5 text-gray-400 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </template>
            </div>

            <!-- Edge Labels -->
            <div
              v-if="path.edges?.length > 0"
              class="mt-3 flex flex-wrap gap-2"
            >
              <span
                v-for="(edge, edgeIndex) in path.edges"
                :key="edgeIndex"
                class="text-xs px-2 py-1 bg-gray-200 dark:bg-gray-600 rounded text-gray-600 dark:text-gray-300"
              >
                {{ edge.type }}
              </span>
            </div>
          </div>

          <!-- Link to full graph -->
          <div class="mt-4 p-4 bg-primary-50 dark:bg-primary-900/20 rounded-xl">
            <router-link
              to="/graph"
              class="flex items-center justify-center space-x-2 text-primary-600 dark:text-primary-400 font-medium"
            >
              <span>查看完整知识图谱</span>
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
                  d="M13 7l5 5m0 0l-5 5m5-5H6"
                />
              </svg>
            </router-link>
          </div>
        </div>

        <!-- Graph View -->
        <div
          v-else
          class="flex-1 relative bg-gray-50 dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden"
          style="min-height: 400px"
        >
          <div ref="graphContainer" class="w-full h-full"></div>

          <!-- Selected Node Info Overlay -->
          <transition name="fade">
            <div
              v-if="selectedNode"
              class="absolute bottom-2 left-2 right-2 bg-white/95 dark:bg-gray-800/95 backdrop-blur-sm rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-3 text-sm z-10"
            >
              <div class="flex items-start justify-between">
                <div>
                  <div class="flex items-center space-x-2 mb-1">
                    <span
                      class="w-2.5 h-2.5 rounded-full"
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
                  <h3 class="font-semibold text-gray-800 dark:text-white">
                    {{ selectedNode.label }}
                  </h3>
                </div>
                <button
                  @click="selectedNode = null"
                  class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
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
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>
            </div>
          </transition>

          <!-- Simple Legend -->
          <div
            class="absolute top-2 right-2 bg-white/90 dark:bg-gray-800/90 rounded p-2 text-[10px] pointer-events-none border border-gray-100 dark:border-gray-700"
          >
            <div class="space-y-1">
              <div
                v-for="(color, type) in nodeColors"
                :key="type"
                class="flex items-center space-x-1"
              >
                <span
                  class="w-2 h-2 rounded-full"
                  :style="{ backgroundColor: color }"
                ></span>
                <span class="text-gray-600 dark:text-gray-400">{{ type }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div
      class="flex-shrink-0 p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50"
    >
      <p class="text-xs text-gray-500 dark:text-gray-400 text-center">
        ⚠️ 以上证据仅供参考，请结合临床实际判断
      </p>
    </div>
  </div>
</template>
