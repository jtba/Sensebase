// ============================================================
// SenseBase - Crawl Pipeline Page
// ============================================================
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { api } from '../api.js';

const STAGES = [
  { key: 'discover', label: 'Discover' },
  { key: 'clone', label: 'Clone' },
  { key: 'analyze', label: 'Analyze' },
  { key: 'output', label: 'Output' },
  { key: 'reloading', label: 'Reload' },
];

const STAGE_ICONS = {
  discover: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>`,
  clone: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>`,
  analyze: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/></svg>`,
  output: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>`,
  reloading: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>`,
};

export default {
  name: 'Crawl',
  template: `
    <div class="p-6 max-w-5xl mx-auto space-y-8">
      <!-- Header -->
      <div class="text-center py-4">
        <h1 class="text-4xl font-bold mb-2">
          <span class="gradient-text">Knowledge Base Pipeline</span>
        </h1>
        <p class="text-gray-400 text-lg">Discover, clone, analyze, and index your repositories</p>
      </div>

      <!-- Controls -->
      <div class="glass-card p-6">
        <div class="flex flex-col sm:flex-row items-center justify-between gap-4">
          <label class="flex items-center gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              v-model="useLlm"
              :disabled="isRunning"
              class="w-4 h-4 rounded border-gray-600 bg-surface-dark text-accent-blue focus:ring-accent-blue focus:ring-offset-0"
            />
            <span class="text-sm text-gray-300">Use LLM extraction (Claude)</span>
          </label>
          <button
            @click="startCrawl"
            :disabled="isRunning"
            class="px-6 py-2.5 rounded-lg text-sm font-semibold transition-all-200"
            :class="isRunning
              ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
              : 'bg-accent-blue hover:bg-blue-600 text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40'"
          >
            <span v-if="isRunning" class="flex items-center gap-2">
              <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              Running...
            </span>
            <span v-else>Start Pipeline</span>
          </button>
        </div>
      </div>

      <!-- Pipeline Visualization -->
      <div class="glass-card p-6">
        <div class="flex items-center justify-between mb-6">
          <h2 class="text-lg font-semibold flex items-center gap-2">
            <svg class="w-5 h-5 text-accent-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
            Pipeline Stages
          </h2>
          <div class="flex items-center gap-2">
            <span
              class="status-dot"
              :class="{
                'status-dot-yellow pulse-loading': job.status === 'running',
                'status-dot-green': job.status === 'completed',
                'status-dot-red': job.status === 'failed',
              }"
            ></span>
            <span class="text-sm font-medium"
                  :class="{
                    'text-yellow-400': job.status === 'running',
                    'text-green-400': job.status === 'completed',
                    'text-red-400': job.status === 'failed',
                    'text-gray-400': job.status === 'idle',
                  }">
              {{ job.status.charAt(0).toUpperCase() + job.status.slice(1) }}
            </span>
          </div>
        </div>

        <!-- Stage circles -->
        <div class="flex items-center justify-between mb-6 px-4">
          <template v-for="(stage, index) in stages" :key="stage.key">
            <!-- Connector line (before all but first) -->
            <div
              v-if="index > 0"
              class="flex-1 h-0.5 mx-1"
              :class="isStageCompleted(stage.key, index) || isStageActive(stage.key) || isStageCompleted(stages[index - 1].key, index - 1) ? 'bg-accent-blue/60' : 'bg-gray-700'"
            ></div>
            <!-- Stage circle -->
            <div class="flex flex-col items-center gap-2">
              <div
                class="w-10 h-10 rounded-full border-2 flex items-center justify-center transition-all-200"
                :class="stageClass(stage.key, index)"
              >
                <!-- Active: spinner -->
                <template v-if="isStageActive(stage.key)">
                  <svg class="w-5 h-5 animate-spin text-accent-blue" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                </template>
                <!-- Completed: checkmark -->
                <template v-else-if="isStageCompleted(stage.key, index)">
                  <svg class="w-5 h-5 text-accent-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                  </svg>
                </template>
                <!-- Pending: icon -->
                <template v-else>
                  <span v-html="stageIcons[stage.key]" class="text-gray-500"></span>
                </template>
              </div>
              <span class="text-xs font-medium"
                    :class="isStageActive(stage.key) ? 'text-accent-blue' : isStageCompleted(stage.key, index) ? 'text-blue-300' : 'text-gray-500'">
                {{ stage.label }}
              </span>
            </div>
          </template>
        </div>

        <!-- Stage detail -->
        <div v-if="job.stage_detail" class="text-center text-sm text-gray-400 mb-4">
          {{ job.stage_detail }}
        </div>

        <!-- Progress bar -->
        <div class="score-bar mb-4">
          <div class="score-bar-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>

        <!-- Started time -->
        <div v-if="job.started_at" class="text-xs text-gray-500 text-center">
          Started: {{ new Date(job.started_at).toLocaleString() }}
        </div>
      </div>

      <!-- Error panel -->
      <div v-if="job.error" class="glass-card p-5 border-red-500/50" style="border-color: rgba(239, 68, 68, 0.5);">
        <div class="flex items-start gap-3">
          <svg class="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/>
          </svg>
          <div>
            <h3 class="text-sm font-semibold text-red-400 mb-1">Pipeline Error</h3>
            <p class="text-sm text-red-300/80">{{ job.error }}</p>
          </div>
        </div>
      </div>

      <!-- Log panel -->
      <div class="glass-card p-5">
        <h2 class="text-lg font-semibold mb-4 flex items-center gap-2">
          <svg class="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
          </svg>
          Pipeline Log
        </h2>
        <div ref="logContainer" class="code-block max-h-80 overflow-y-auto">
          <div v-if="job.log.length === 0" class="text-gray-500 text-sm">No log output yet</div>
          <div v-for="(entry, i) in job.log" :key="i" class="text-xs leading-relaxed">{{ entry }}</div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const job = ref({
      status: 'idle',
      current_stage: null,
      stage_index: 0,
      total_stages: STAGES.length,
      stage_detail: '',
      started_at: null,
      error: null,
      log: [],
    });

    const useLlm = ref(false);
    const logContainer = ref(null);
    let eventSource = null;

    const stages = STAGES;
    const stageIcons = STAGE_ICONS;

    // ---- Pipeline State ----
    const isRunning = computed(() => job.value.status === 'running');

    const progressPercent = computed(() => {
      if (job.value.status === 'completed') return 100;
      if (job.value.total_stages === 0) return 0;
      return Math.round((job.value.stage_index / job.value.total_stages) * 100);
    });

    function isStageActive(key) {
      return job.value.status === 'running' && job.value.current_stage === key;
    }

    function isStageCompleted(key, index) {
      if (job.value.status === 'completed') return true;
      if (job.value.status !== 'running') return false;
      return index < job.value.stage_index;
    }

    function stageClass(key, index) {
      if (isStageActive(key)) {
        return 'border-accent-blue bg-accent-blue/10';
      }
      if (isStageCompleted(key, index)) {
        return 'border-accent-blue bg-accent-blue/20';
      }
      return 'border-gray-600 bg-transparent';
    }

    function autoScrollLog() {
      nextTick(() => {
        if (logContainer.value) {
          logContainer.value.scrollTop = logContainer.value.scrollHeight;
        }
      });
    }

    function connectSSE() {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }

      eventSource = api.crawlStream();

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          job.value = {
            status: data.status || job.value.status,
            current_stage: data.current_stage || null,
            stage_index: data.stage_index ?? job.value.stage_index,
            total_stages: data.total_stages ?? job.value.total_stages,
            stage_detail: data.stage_detail || '',
            started_at: data.started_at || job.value.started_at,
            error: data.error || null,
            log: data.log || job.value.log,
          };
          autoScrollLog();

          if (data.status === 'completed' || data.status === 'failed') {
            eventSource.close();
            eventSource = null;
          }
        } catch (e) {
          console.error('SSE parse error:', e);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        eventSource = null;
      };
    }

    async function startCrawl() {
      try {
        const data = await api.crawlStart(useLlm.value);
        job.value = {
          status: data.status || 'running',
          current_stage: data.current_stage || null,
          stage_index: data.stage_index ?? 0,
          total_stages: data.total_stages ?? STAGES.length,
          stage_detail: data.stage_detail || '',
          started_at: data.started_at || new Date().toISOString(),
          error: null,
          log: data.log || [],
        };
        connectSSE();
      } catch (err) {
        job.value.error = err.message;
        job.value.status = 'failed';
      }
    }

    async function loadCurrentStatus() {
      try {
        const data = await api.crawlStatus();
        job.value = {
          status: data.status || 'idle',
          current_stage: data.current_stage || null,
          stage_index: data.stage_index ?? 0,
          total_stages: data.total_stages ?? STAGES.length,
          stage_detail: data.stage_detail || '',
          started_at: data.started_at || null,
          error: data.error || null,
          log: data.log || [],
        };
        autoScrollLog();
        if (data.status === 'running') {
          connectSSE();
        }
      } catch (err) {
        // Server might not have crawl status yet, that's fine
        console.warn('Could not load crawl status:', err.message);
      }
    }

    onMounted(() => {
      loadCurrentStatus();
    });

    onUnmounted(() => {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
    });

    return {
      job, useLlm, logContainer, stages, stageIcons,
      isRunning, progressPercent,
      isStageActive, isStageCompleted, stageClass,
      startCrawl,
    };
  },
};
