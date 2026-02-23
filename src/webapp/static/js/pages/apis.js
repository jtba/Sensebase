// ============================================================
// SenseBase - API Explorer Page
// ============================================================

import { ref, computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { api } from '../api.js';

export default {
  name: 'ApisPage',
  template: `
    <div class="p-6 max-w-7xl mx-auto">

      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold gradient-text mb-1">API Explorer</h1>
        <p class="text-gray-500 text-sm">Browse REST API endpoints across repositories</p>
      </div>

      <!-- Filters -->
      <div class="flex flex-col sm:flex-row gap-3 mb-6">
        <div class="flex-1">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search by path or handler..."
            class="search-input w-full px-4 py-2.5 text-sm"
          />
        </div>
        <div class="flex gap-2 flex-wrap items-center">
          <button
            v-for="m in methodFilters"
            :key="m"
            @click="toggleMethodFilter(m)"
            class="filter-chip"
            :class="[
              activeMethod === m ? 'filter-chip-active' : '',
              m !== 'ALL' ? methodChipClass(m) : ''
            ]"
          >
            {{ m }}
          </button>
        </div>
      </div>

      <!-- Repo filter -->
      <div v-if="availableRepos.length > 1" class="flex gap-2 flex-wrap mb-4">
        <button
          @click="activeRepo = null"
          class="filter-chip"
          :class="{ 'filter-chip-active': !activeRepo }"
        >
          All Repos
        </button>
        <button
          v-for="repo in availableRepos"
          :key="repo"
          @click="activeRepo = activeRepo === repo ? null : repo"
          class="filter-chip"
          :class="{ 'filter-chip-active': activeRepo === repo }"
        >
          {{ repo }}
        </button>
      </div>

      <!-- Endpoint count -->
      <div class="flex items-center justify-between mb-4 text-xs text-gray-500">
        <span>{{ totalFilteredCount }} endpoints in {{ Object.keys(groupedEndpoints).length }} groups</span>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="space-y-4">
        <div v-for="i in 3" :key="i" class="glass-card p-5">
          <div class="skeleton h-5 w-32 mb-4"></div>
          <div v-for="j in 3" :key="j" class="skeleton h-12 w-full mb-2"></div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="glass-card p-6 text-center">
        <p class="text-red-400">{{ error }}</p>
        <button @click="fetchApis" class="mt-3 px-4 py-2 bg-accent-teal/20 text-accent-teal rounded-lg hover:bg-accent-teal/30 text-sm">Retry</button>
      </div>

      <!-- Empty -->
      <div v-else-if="totalFilteredCount === 0 && !loading" class="glass-card p-8 text-center">
        <svg class="w-12 h-12 text-gray-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
        </svg>
        <p class="text-gray-400">No API endpoints found{{ searchQuery ? ' matching "' + searchQuery + '"' : '' }}</p>
      </div>

      <!-- Grouped endpoints -->
      <div v-else class="space-y-4">
        <div
          v-for="(endpoints, group) in groupedEndpoints"
          :key="group"
          class="glass-card overflow-hidden"
        >
          <!-- Group header -->
          <button
            @click="toggleGroup(group)"
            class="w-full flex items-center justify-between px-5 py-3 hover:bg-surface/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <svg class="w-4 h-4 text-gray-500 transition-transform" :class="{ 'rotate-90': expandedGroups[group] }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
              </svg>
              <span class="text-sm font-semibold text-accent-teal font-mono">/{{ group }}</span>
            </div>
            <span class="text-xs text-gray-500">{{ endpoints.length }} endpoints</span>
          </button>

          <!-- Endpoint list -->
          <div v-if="expandedGroups[group]" class="border-t border-border/50">
            <div
              v-for="(endpoint, i) in endpoints"
              :key="i"
              class="border-b border-border/30 last:border-0"
            >
              <!-- Endpoint row -->
              <button
                @click="toggleEndpoint(group + '-' + i)"
                class="w-full flex items-center gap-3 px-5 py-3 hover:bg-surface/20 transition-colors text-left"
              >
                <!-- Method badge -->
                <span
                  class="flex-shrink-0 w-16 text-center py-0.5 rounded text-xs font-bold font-mono"
                  :class="methodBadgeClass(endpoint.method)"
                >
                  {{ endpoint.method }}
                </span>

                <!-- Path -->
                <span class="flex-1 font-mono text-sm text-gray-300 truncate" v-html="highlightParams(endpoint.path)"></span>

                <!-- Handler -->
                <span v-if="endpoint.handler" class="text-xs text-gray-500 hidden lg:inline truncate max-w-[200px]">{{ endpoint.handler }}</span>

                <!-- Expand icon -->
                <svg class="w-4 h-4 text-gray-600 flex-shrink-0 transition-transform" :class="{ 'rotate-180': expandedEndpoints[group + '-' + i] }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                </svg>
              </button>

              <!-- Expanded details -->
              <div v-if="expandedEndpoints[group + '-' + i]" class="px-5 pb-4 bg-surface/20">
                <div class="grid gap-3 sm:grid-cols-2 text-sm">
                  <div v-if="endpoint.handler">
                    <span class="text-xs text-gray-500 block mb-0.5">Handler</span>
                    <span class="font-mono text-gray-300 text-xs">{{ endpoint.handler }}</span>
                  </div>
                  <div v-if="endpoint.repo">
                    <span class="text-xs text-gray-500 block mb-0.5">Repository</span>
                    <span class="text-gray-300 text-xs">{{ endpoint.repo }}</span>
                  </div>
                  <div v-if="endpoint.source_file">
                    <span class="text-xs text-gray-500 block mb-0.5">Source File</span>
                    <span class="font-mono text-gray-400 text-xs break-all">{{ endpoint.source_file }}</span>
                  </div>
                  <div v-if="endpoint.description">
                    <span class="text-xs text-gray-500 block mb-0.5">Description</span>
                    <span class="text-gray-300 text-xs">{{ endpoint.description }}</span>
                  </div>
                </div>

                <!-- Params -->
                <div v-if="endpoint.params && endpoint.params.length > 0" class="mt-3">
                  <span class="text-xs text-gray-500 block mb-2">Parameters</span>
                  <div class="overflow-x-auto">
                    <table class="w-full text-xs">
                      <thead>
                        <tr class="text-left text-gray-500 border-b border-border/50">
                          <th class="pb-1 pr-3 font-medium">Name</th>
                          <th class="pb-1 pr-3 font-medium">Type</th>
                          <th class="pb-1 pr-3 font-medium">In</th>
                          <th class="pb-1 font-medium">Required</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(param, pi) in endpoint.params" :key="pi" class="border-b border-border/30">
                          <td class="py-1 pr-3 font-mono text-accent-teal">{{ param.name || param }}</td>
                          <td class="py-1 pr-3 font-mono text-gray-400">{{ param.type || '-' }}</td>
                          <td class="py-1 pr-3 text-gray-500">{{ param.in || param.location || '-' }}</td>
                          <td class="py-1 text-gray-500">{{ param.required ? 'Yes' : 'No' }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const router = useRouter();
    const route = useRoute();

    const loading = ref(false);
    const error = ref(null);
    const endpoints = ref([]);
    const searchQuery = ref('');
    const activeMethod = ref('ALL');
    const activeRepo = ref(null);
    const expandedGroups = ref({});
    const expandedEndpoints = ref({});

    const methodFilters = ['ALL', 'GET', 'POST', 'PUT', 'DELETE', 'PATCH'];

    const availableRepos = computed(() => {
      const repos = new Set();
      for (const e of endpoints.value) {
        if (e.repo) repos.add(e.repo);
      }
      return Array.from(repos).sort();
    });

    const filteredEndpoints = computed(() => {
      let result = endpoints.value;

      if (activeMethod.value !== 'ALL') {
        result = result.filter(e => (e.method || '').toUpperCase() === activeMethod.value);
      }

      if (activeRepo.value) {
        result = result.filter(e => e.repo === activeRepo.value);
      }

      if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase();
        result = result.filter(e =>
          (e.path || '').toLowerCase().includes(q) ||
          (e.handler || '').toLowerCase().includes(q) ||
          (e.description || '').toLowerCase().includes(q)
        );
      }

      return result;
    });

    const groupedEndpoints = computed(() => {
      const groups = {};
      for (const endpoint of filteredEndpoints.value) {
        const group = getGroupKey(endpoint.path);
        if (!groups[group]) groups[group] = [];
        groups[group].push(endpoint);
      }
      // Sort groups
      const sorted = {};
      for (const key of Object.keys(groups).sort()) {
        sorted[key] = groups[key].sort((a, b) => {
          const methodOrder = { GET: 0, POST: 1, PUT: 2, PATCH: 3, DELETE: 4 };
          const ma = methodOrder[(a.method || '').toUpperCase()] ?? 5;
          const mb = methodOrder[(b.method || '').toUpperCase()] ?? 5;
          if (ma !== mb) return ma - mb;
          return (a.path || '').localeCompare(b.path || '');
        });
      }
      return sorted;
    });

    const totalFilteredCount = computed(() => filteredEndpoints.value.length);

    function getGroupKey(path) {
      if (!path) return 'other';
      const parts = path.replace(/^\//, '').split('/');
      // Find first meaningful segment (skip version prefixes like v1, v2, api)
      for (const part of parts) {
        if (part && !/^(v\d+|api|rest)$/i.test(part) && !part.startsWith(':') && !part.startsWith('{')) {
          return part;
        }
      }
      return parts[0] || 'other';
    }

    function toggleMethodFilter(method) {
      activeMethod.value = method;
    }

    function toggleGroup(group) {
      expandedGroups.value[group] = !expandedGroups.value[group];
    }

    function toggleEndpoint(key) {
      expandedEndpoints.value[key] = !expandedEndpoints.value[key];
    }

    function methodBadgeClass(method) {
      const m = (method || '').toUpperCase();
      const classes = {
        GET: 'bg-green-500/15 text-green-400 border border-green-500/25',
        POST: 'bg-blue-500/15 text-blue-400 border border-blue-500/25',
        PUT: 'bg-amber-500/15 text-amber-400 border border-amber-500/25',
        DELETE: 'bg-red-500/15 text-red-400 border border-red-500/25',
        PATCH: 'bg-purple-500/15 text-purple-400 border border-purple-500/25',
      };
      return classes[m] || 'bg-gray-500/15 text-gray-400 border border-gray-500/25';
    }

    function methodChipClass(method) {
      if (method === 'ALL') return '';
      const m = method.toUpperCase();
      const classes = {
        GET: 'text-green-400',
        POST: 'text-blue-400',
        PUT: 'text-amber-400',
        DELETE: 'text-red-400',
        PATCH: 'text-purple-400',
      };
      return classes[m] || '';
    }

    function highlightParams(path) {
      if (!path) return '';
      // Highlight :param and {param} patterns
      return path
        .replace(/(:[a-zA-Z_]+)/g, '<span class="text-accent-amber">$1</span>')
        .replace(/(\{[a-zA-Z_]+\})/g, '<span class="text-accent-amber">$1</span>');
    }

    async function fetchApis() {
      loading.value = true;
      error.value = null;
      try {
        endpoints.value = await api.apis();
        // Auto-expand all groups initially
        for (const group of Object.keys(groupedEndpoints.value)) {
          expandedGroups.value[group] = true;
        }
      } catch (e) {
        error.value = e.message || 'Failed to load APIs';
      } finally {
        loading.value = false;
      }
    }

    onMounted(() => {
      fetchApis();
    });

    return {
      loading,
      error,
      endpoints,
      searchQuery,
      activeMethod,
      activeRepo,
      expandedGroups,
      expandedEndpoints,
      methodFilters,
      availableRepos,
      groupedEndpoints,
      totalFilteredCount,
      toggleMethodFilter,
      toggleGroup,
      toggleEndpoint,
      methodBadgeClass,
      methodChipClass,
      highlightParams,
      fetchApis,
      router,
    };
  },
};
