// ============================================================
// SenseBase - System Configuration Page
// ============================================================

import { ref, computed, onMounted } from 'vue';
import { api } from '../api.js';

const PROVIDER_META = {
  anthropic: {
    label: 'Anthropic',
    color: 'text-orange-300',
    bg: 'bg-orange-500/10 border-orange-500/20',
    icon: `<svg viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6"><path d="M13.827 3.52h3.603L24 20.48h-3.603l-6.57-16.96zm-7.258 0h3.767L16.906 20.48h-3.674l-1.343-3.461H5.017l-1.344 3.46H0l6.57-16.96zm2.327 5.14L6.77 14.16h4.252L8.896 8.66z"/></svg>`,
    models: ['claude-opus-4-6-20250918', 'claude-sonnet-4-6-20250918', 'claude-sonnet-4-5-20250929', 'claude-opus-4-5-20251101', 'claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-haiku-4-5-20251001'],
    keyPlaceholder: 'sk-ant-...',
  },
  openai: {
    label: 'OpenAI',
    color: 'text-green-400',
    bg: 'bg-green-500/10 border-green-500/20',
    icon: `<svg viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6"><path d="M22.282 9.821a5.985 5.985 0 00-.516-4.91 6.046 6.046 0 00-6.51-2.9A6.065 6.065 0 0011.708.421a6.004 6.004 0 00-5.7 4.211 6.04 6.04 0 00-4.042 2.927A6.054 6.054 0 002.7 13.77a5.98 5.98 0 00.516 4.911 6.04 6.04 0 006.51 2.9A6.07 6.07 0 0014.293 23.6a6.004 6.004 0 005.7-4.211 6.04 6.04 0 004.042-2.927 6.042 6.042 0 00-.733-6.241zM14.293 21.95a4.51 4.51 0 01-2.9-1.054l.144-.08 4.834-2.79a.778.778 0 00.395-.675v-6.813l2.043 1.18a.072.072 0 01.04.055v5.64a4.518 4.518 0 01-4.556 4.537zm-9.73-4.16a4.5 4.5 0 01-.54-3.032l.144.084 4.834 2.79a.78.78 0 00.788 0l5.905-3.41v2.36a.074.074 0 01-.028.06l-4.887 2.823a4.52 4.52 0 01-6.216-1.675zm-1.268-10.5a4.504 4.504 0 012.36-1.98v5.747a.774.774 0 00.395.675l5.905 3.41-2.043 1.18a.072.072 0 01-.069.006l-4.888-2.823a4.524 4.524 0 01-1.66-6.215zM18.665 12.1l-5.906-3.41 2.044-1.18a.072.072 0 01.069-.006l4.887 2.824a4.515 4.515 0 01-.7 8.145v-5.698a.788.788 0 00-.394-.675zm2.034-3.045l-.144-.084-4.834-2.79a.778.778 0 00-.788 0l-5.905 3.41v-2.36a.072.072 0 01.028-.06l4.887-2.823a4.516 4.516 0 016.756 4.707zM8.07 13.723l-2.044-1.18a.072.072 0 01-.04-.056v-5.64a4.516 4.516 0 017.456-3.432l-.144.08-4.834 2.79a.778.778 0 00-.395.676l-.003 6.762zm1.11-2.393l2.63-1.518 2.63 1.518v3.036l-2.63 1.518-2.63-1.518v-3.036z"/></svg>`,
    models: ['gpt-4o', 'gpt-4o-mini', 'o3-mini'],
    keyPlaceholder: 'sk-...',
  },
  bedrock: {
    label: 'AWS Bedrock',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10 border-amber-500/20',
    icon: `<svg viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6"><path d="M12 2L2 7v10l10 5 10-5V7L12 2zm0 2.18l6.75 3.38L12 10.93 5.25 7.56 12 4.18zM4 8.81l7 3.5v7.88l-7-3.5V8.81zm16 7.88l-7 3.5v-7.88l7-3.5v7.88z"/></svg>`,
    models: [
      'anthropic.claude-opus-4-6-v1',
      'anthropic.claude-sonnet-4-6',
      'anthropic.claude-sonnet-4-5-20250929-v1:0',
      'anthropic.claude-haiku-4-5-20251001-v1:0',
      'amazon.nova-premier-v1:0',
      'amazon.nova-pro-v1:0',
      'amazon.nova-lite-v1:0',
      'amazon.nova-micro-v1:0',
      'meta.llama4-maverick-17b-instruct-v1:0',
      'meta.llama4-scout-17b-instruct-v1:0',
      'deepseek.r1-v1:0',
      'deepseek.v3.2',
      'mistral.mistral-large-3-675b-instruct',
    ],
    keyPlaceholder: 'AKIA...',
  },
};

export default {
  name: 'SettingsPage',
  template: `
    <div class="p-6 max-w-4xl mx-auto space-y-8">

      <!-- Header -->
      <div>
        <h1 class="text-2xl font-bold gradient-text mb-1">System Configuration</h1>
        <p class="text-gray-500 text-sm">Search capabilities, knowledge base stats, and system health</p>
      </div>

      <!-- System Health -->
      <div class="glass-card p-6">
        <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">System Health</h2>
        <div v-if="healthLoading" class="space-y-3">
          <div class="skeleton h-5 w-48"></div>
          <div class="skeleton h-5 w-36"></div>
        </div>
        <div v-else class="grid gap-4 sm:grid-cols-3">
          <div class="flex items-center gap-3 p-3 rounded-lg bg-surface/40 border border-border/30">
            <span class="status-dot" :class="health.status === 'healthy' ? 'status-dot-green' : 'status-dot-yellow'"></span>
            <div>
              <div class="text-sm font-medium text-gray-200">API Server</div>
              <div class="text-xs text-gray-500">{{ health.status || 'unknown' }}</div>
            </div>
          </div>
          <div class="flex items-center gap-3 p-3 rounded-lg bg-surface/40 border border-border/30">
            <span class="status-dot" :class="health.keyword_search ? 'status-dot-green' : 'status-dot-yellow'"></span>
            <div>
              <div class="text-sm font-medium text-gray-200">Keyword Search</div>
              <div class="text-xs text-gray-500">{{ health.keyword_search ? 'Available' : 'Not indexed' }}</div>
            </div>
          </div>
          <div class="flex items-center gap-3 p-3 rounded-lg bg-surface/40 border border-border/30">
            <span class="status-dot" :class="health.semantic_search ? 'status-dot-green' : 'status-dot-yellow'"></span>
            <div>
              <div class="text-sm font-medium text-gray-200">Semantic Search</div>
              <div class="text-xs text-gray-500">{{ health.semantic_search ? 'Available' : 'Not configured' }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Knowledge Base Stats -->
      <div class="glass-card p-6">
        <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Knowledge Base</h2>
        <div v-if="statsLoading" class="space-y-3">
          <div class="skeleton h-5 w-48"></div>
          <div class="skeleton h-5 w-36"></div>
        </div>
        <div v-else-if="stats" class="grid gap-4 sm:grid-cols-5">
          <div class="p-3 rounded-lg bg-surface/40 border border-border/30 text-center">
            <div class="text-xl font-bold text-accent-blue">{{ stats.repos || 0 }}</div>
            <div class="text-xs text-gray-500 mt-1">Repositories</div>
          </div>
          <div class="p-3 rounded-lg bg-surface/40 border border-border/30 text-center">
            <div class="text-xl font-bold text-accent-purple">{{ stats.schemas || 0 }}</div>
            <div class="text-xs text-gray-500 mt-1">Schemas</div>
          </div>
          <div class="p-3 rounded-lg bg-surface/40 border border-border/30 text-center">
            <div class="text-xl font-bold text-accent-teal">{{ stats.apis || 0 }}</div>
            <div class="text-xs text-gray-500 mt-1">APIs</div>
          </div>
          <div class="p-3 rounded-lg bg-surface/40 border border-border/30 text-center">
            <div class="text-xl font-bold text-yellow-400">{{ stats.services || 0 }}</div>
            <div class="text-xs text-gray-500 mt-1">Services</div>
          </div>
          <div class="p-3 rounded-lg bg-surface/40 border border-border/30 text-center">
            <div class="text-xl font-bold text-pink-400">{{ stats.dependencies || 0 }}</div>
            <div class="text-xs text-gray-500 mt-1">Dependencies</div>
          </div>
        </div>
        <div v-else class="text-sm text-gray-500">No knowledge base loaded</div>
      </div>

      <!-- LLM Provider -->
      <div class="glass-card p-6">
        <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">LLM Provider</h2>

        <!-- Loading -->
        <div v-if="llmLoading" class="space-y-3">
          <div class="skeleton h-5 w-48"></div>
          <div class="skeleton h-5 w-36"></div>
        </div>

        <!-- Display mode -->
        <div v-else-if="!llmEditing">
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-4 min-w-0">
              <!-- Provider icon -->
              <div v-if="llmConfig.provider && providerMeta[llmConfig.provider]"
                class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center"
                :class="providerMeta[llmConfig.provider].bg"
              >
                <div :class="providerMeta[llmConfig.provider].color" v-html="providerMeta[llmConfig.provider].icon"></div>
              </div>
              <div v-else class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-gray-500/10 border border-gray-500/20">
                <svg class="w-6 h-6 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714a2.25 2.25 0 00.659 1.591L19 14.5M14.25 3.104c.251.023.501.05.75.082M19 14.5l-2.47 2.47a2.25 2.25 0 01-1.591.659H9.061a2.25 2.25 0 01-1.591-.659L5 14.5m14 0V17a2.25 2.25 0 01-2.25 2.25H7.25A2.25 2.25 0 015 17v-2.5"/></svg>
              </div>

              <div class="min-w-0">
                <h3 class="text-base font-semibold text-gray-200">
                  {{ llmConfig.provider && providerMeta[llmConfig.provider] ? providerMeta[llmConfig.provider].label : 'Not configured' }}
                </h3>
                <div class="mt-2 space-y-1.5">
                  <!-- Model -->
                  <div v-if="llmConfig.model" class="flex items-center gap-2 text-sm text-gray-400">
                    <svg class="w-3.5 h-3.5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714a2.25 2.25 0 00.659 1.591L19 14.5"/></svg>
                    <span class="font-mono text-xs">{{ llmConfig.model }}</span>
                  </div>
                  <!-- API key status -->
                  <div class="flex items-center gap-2 text-sm text-gray-400">
                    <span class="status-dot" :class="llmConfig.api_key_set ? 'status-dot-green' : 'status-dot-yellow'"></span>
                    <span v-if="llmConfig.api_key_set">API key configured (from {{ llmConfig.api_key_source }})</span>
                    <span v-else>No API key set</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Configure button -->
            <button
              @click="startLlmEdit"
              class="flex-shrink-0 px-4 py-2 text-sm font-medium bg-accent-purple/15 text-accent-purple rounded-lg hover:bg-accent-purple/25 transition-colors"
            >
              Configure
            </button>
          </div>
        </div>

        <!-- Edit mode -->
        <div v-else class="space-y-5">
          <!-- Provider selector -->
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-2">Provider</label>
            <div class="grid gap-3 sm:grid-cols-3">
              <button
                v-for="(meta, key) in providerMeta"
                :key="key"
                @click="llmForm.provider = key"
                class="p-4 rounded-lg border text-left transition-all group"
                :class="llmForm.provider === key
                  ? meta.bg + ' ring-1 ring-current ' + meta.color
                  : 'border-border/50 hover:border-gray-500/40 bg-surface/40 hover:bg-surface/70'"
              >
                <div class="flex items-center gap-3">
                  <div class="flex-shrink-0" :class="llmForm.provider === key ? meta.color : 'text-gray-500'" v-html="meta.icon"></div>
                  <span class="text-sm font-semibold" :class="llmForm.provider === key ? 'text-gray-100' : 'text-gray-400 group-hover:text-gray-200'">{{ meta.label }}</span>
                </div>
              </button>
            </div>
          </div>

          <!-- API Key -->
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-1.5">API Key</label>
            <input
              v-model="llmForm.api_key"
              type="password"
              :placeholder="llmConfig.api_key_set ? 'Enter new key to update' : (selectedProviderMeta ? selectedProviderMeta.keyPlaceholder : 'Enter API key')"
              class="search-input w-full px-3 py-2 text-sm font-mono"
            />
            <p v-if="llmConfig.api_key_set" class="text-xs text-gray-600 mt-1">Leave blank to keep existing key</p>
          </div>

          <!-- Model -->
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-1.5">Model</label>
            <select
              v-model="llmForm.model"
              class="search-input w-full px-3 py-2 text-sm bg-transparent"
            >
              <option v-for="m in currentModels" :key="m" :value="m">{{ m }}</option>
            </select>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-3 pt-4 border-t border-border/30">
            <button
              @click="saveLlmConfig"
              :disabled="llmSaving || !llmForm.provider"
              class="px-4 py-2 text-sm font-medium bg-accent-purple/20 text-accent-purple rounded-lg hover:bg-accent-purple/30 transition-colors disabled:opacity-50"
            >
              {{ llmSaving ? 'Saving...' : 'Save' }}
            </button>
            <button @click="cancelLlmEdit" class="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors">
              Cancel
            </button>
            <span v-if="llmError" class="text-xs text-red-400 ml-2">{{ llmError }}</span>
          </div>
        </div>
      </div>

    </div>
  `,
  setup() {
    const healthLoading = ref(true);
    const health = ref({});
    const statsLoading = ref(true);
    const stats = ref(null);

    // LLM config state
    const providerMeta = PROVIDER_META;
    const llmLoading = ref(true);
    const llmConfig = ref({});
    const llmEditing = ref(false);
    const llmForm = ref({ provider: 'anthropic', api_key: '', model: '' });
    const llmSaving = ref(false);
    const llmError = ref('');

    const selectedProviderMeta = computed(() => providerMeta[llmForm.value.provider] || null);

    const currentModels = computed(() => {
      const meta = providerMeta[llmForm.value.provider];
      return meta ? meta.models : [];
    });

    async function fetchHealth() {
      healthLoading.value = true;
      try {
        health.value = await api.health();
      } catch {
        health.value = { status: 'unreachable' };
      } finally {
        healthLoading.value = false;
      }
    }

    async function fetchStats() {
      statsLoading.value = true;
      try {
        stats.value = await api.stats();
      } catch {
        stats.value = null;
      } finally {
        statsLoading.value = false;
      }
    }

    async function fetchLlmConfig() {
      llmLoading.value = true;
      try {
        llmConfig.value = await api.llmConfig();
      } catch {
        llmConfig.value = {};
      } finally {
        llmLoading.value = false;
      }
    }

    function startLlmEdit() {
      llmEditing.value = true;
      llmError.value = '';
      const cfg = llmConfig.value;
      const provider = cfg.provider || 'anthropic';
      const meta = providerMeta[provider];
      llmForm.value = {
        provider,
        api_key: '',
        model: cfg.model || (meta ? meta.models[0] : ''),
      };
    }

    function cancelLlmEdit() {
      llmEditing.value = false;
      llmError.value = '';
    }

    async function saveLlmConfig() {
      llmError.value = '';
      if (!llmForm.value.provider) {
        llmError.value = 'Provider is required';
        return;
      }

      const payload = {
        provider: llmForm.value.provider,
        model: llmForm.value.model || null,
      };
      // Only include api_key if user entered something
      if (llmForm.value.api_key.trim()) {
        payload.api_key = llmForm.value.api_key.trim();
      }

      llmSaving.value = true;
      try {
        llmConfig.value = await api.updateLlmConfig(payload);
        llmEditing.value = false;
      } catch (e) {
        llmError.value = e.message || 'Failed to save';
      } finally {
        llmSaving.value = false;
      }
    }

    onMounted(() => {
      fetchHealth();
      fetchStats();
      fetchLlmConfig();
    });

    return {
      healthLoading, health,
      statsLoading, stats,
      providerMeta, llmLoading, llmConfig,
      llmEditing, llmForm, llmSaving, llmError,
      selectedProviderMeta, currentModels,
      startLlmEdit, cancelLlmEdit, saveLlmConfig,
    };
  },
};
