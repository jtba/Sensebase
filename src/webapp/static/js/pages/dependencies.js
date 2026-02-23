// ============================================================
// SenseBase - Dependencies Page
// ============================================================

import { ref, computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { api } from '../api.js';

export default {
  name: 'DependenciesPage',
  template: `
    <div class="p-6 max-w-7xl mx-auto">

      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold gradient-text mb-1">Dependencies</h1>
        <p class="text-gray-500 text-sm">External dependencies and libraries used across repositories</p>
      </div>

      <!-- Summary stats -->
      <div v-if="!loading && !error && dependencies.length > 0" class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div class="glass-card p-4 stat-card-amber">
          <div class="text-2xl font-bold text-gray-100">{{ totalDeps }}</div>
          <div class="text-xs text-gray-500">Total Dependencies</div>
        </div>
        <div class="glass-card p-4 stat-card-blue">
          <div class="text-2xl font-bold text-gray-100">{{ uniqueDeps }}</div>
          <div class="text-xs text-gray-500">Unique Packages</div>
        </div>
        <div class="glass-card p-4 stat-card-teal">
          <div class="text-2xl font-bold text-gray-100">{{ Object.keys(ecosystemCounts).length }}</div>
          <div class="text-xs text-gray-500">Ecosystems</div>
        </div>
        <div class="glass-card p-4 stat-card-purple">
          <div class="text-2xl font-bold text-gray-100">{{ repoCount }}</div>
          <div class="text-xs text-gray-500">Repositories</div>
        </div>
      </div>

      <!-- Ecosystem breakdown -->
      <div v-if="Object.keys(ecosystemCounts).length > 0 && !loading" class="glass-card p-4 mb-6">
        <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Ecosystem Breakdown</h3>
        <div class="flex flex-wrap gap-3">
          <div v-for="(count, eco) in ecosystemCounts" :key="eco" class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-full" :style="{ background: ecosystemColor(eco) }"></span>
            <span class="text-sm text-gray-300">{{ eco }}</span>
            <span class="text-xs text-gray-500">({{ count }})</span>
          </div>
        </div>
      </div>

      <!-- Filters -->
      <div class="flex flex-col sm:flex-row gap-3 mb-4">
        <div class="flex-1">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search dependencies by name..."
            class="search-input w-full px-4 py-2.5 text-sm"
          />
        </div>
        <div class="flex gap-2 flex-wrap items-center">
          <button
            @click="activeEcosystem = null"
            class="filter-chip"
            :class="{ 'filter-chip-active': !activeEcosystem }"
          >
            All
          </button>
          <button
            v-for="eco in ecosystems"
            :key="eco"
            @click="activeEcosystem = activeEcosystem === eco ? null : eco"
            class="filter-chip"
            :class="{ 'filter-chip-active': activeEcosystem === eco }"
          >
            {{ eco }}
          </button>
        </div>
      </div>

      <!-- Sort -->
      <div class="flex items-center gap-2 mb-4 text-xs text-gray-500">
        <span>Sort by:</span>
        <button
          v-for="s in sortOptions"
          :key="s.key"
          @click="sortBy = s.key"
          class="px-2 py-1 rounded"
          :class="sortBy === s.key ? 'bg-accent-amber/15 text-accent-amber' : 'hover:text-gray-300'"
        >
          {{ s.label }}
        </button>
        <span class="ml-auto text-gray-600">{{ filteredDeps.length }} dependencies</span>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="i in 6" :key="i" class="glass-card p-5">
          <div class="skeleton h-5 w-32 mb-3"></div>
          <div class="skeleton h-4 w-20 mb-2"></div>
          <div class="skeleton h-3 w-24"></div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="glass-card p-6 text-center">
        <p class="text-red-400">{{ error }}</p>
        <button @click="fetchDeps" class="mt-3 px-4 py-2 bg-accent-amber/20 text-accent-amber rounded-lg hover:bg-accent-amber/30 text-sm">Retry</button>
      </div>

      <!-- Empty -->
      <div v-else-if="filteredDeps.length === 0 && !loading" class="glass-card p-8 text-center">
        <svg class="w-12 h-12 text-gray-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
        </svg>
        <p class="text-gray-400">No dependencies found{{ searchQuery ? ' matching "' + searchQuery + '"' : '' }}</p>
      </div>

      <!-- Dependency Grid -->
      <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="dep in filteredDeps"
          :key="dep.name"
          class="glass-card glass-card-interactive overflow-hidden"
        >
          <!-- Card content -->
          <button
            @click="toggleExpand(dep.name)"
            class="w-full text-left p-5 transition-all"
          >
            <div class="flex items-start justify-between gap-2 mb-2">
              <h3 class="text-sm font-semibold text-gray-200 truncate font-mono">{{ dep.name }}</h3>
              <span
                class="badge flex-shrink-0"
                :style="{ background: ecosystemColor(dep.ecosystem) + '20', color: ecosystemColor(dep.ecosystem), borderColor: ecosystemColor(dep.ecosystem) + '40' }"
              >
                {{ dep.ecosystem || 'unknown' }}
              </span>
            </div>
            <div class="flex items-center gap-3 text-xs text-gray-500">
              <span v-if="dep.version" class="font-mono">v{{ dep.version }}</span>
              <span v-if="dep.type" class="px-1.5 py-0.5 bg-surface rounded">{{ dep.type }}</span>
            </div>
            <div class="mt-2 text-xs text-gray-500">
              <span v-if="dep.repo">
                Used in <span class="text-gray-300">{{ dep.repo }}</span>
              </span>
            </div>
          </button>

          <!-- Expanded usage details -->
          <div v-if="expandedDep === dep.name" class="border-t border-border/50 bg-surface/20 p-4">
            <div v-if="usageLoading" class="flex items-center gap-2 text-sm text-gray-500">
              <div class="w-4 h-4 border-2 border-accent-amber border-t-transparent rounded-full animate-spin"></div>
              Loading usage...
            </div>
            <div v-else-if="usageData">
              <h4 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Used in {{ usageData.usage_count }} locations</h4>
              <div class="space-y-1.5 max-h-48 overflow-y-auto">
                <div v-for="(usage, i) in usageData.usages" :key="i" class="text-xs">
                  <span v-if="usage.repo" class="text-gray-300">{{ usage.repo }}</span>
                  <span v-if="usage.source_file" class="font-mono text-gray-500 ml-1">{{ usage.source_file }}</span>
                  <span v-if="!usage.repo && !usage.source_file" class="text-gray-400">{{ typeof usage === 'string' ? usage : JSON.stringify(usage) }}</span>
                </div>
              </div>
            </div>
            <div v-else class="text-xs text-gray-500">No additional usage data available.</div>
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
    const dependencies = ref([]);
    const searchQuery = ref('');
    const activeEcosystem = ref(null);
    const sortBy = ref('name');
    const expandedDep = ref(null);
    const usageLoading = ref(false);
    const usageData = ref(null);

    const sortOptions = [
      { key: 'name', label: 'Name' },
      { key: 'ecosystem', label: 'Ecosystem' },
    ];

    const ecosystems = computed(() => {
      const ecos = new Set();
      for (const dep of dependencies.value) {
        if (dep.ecosystem) ecos.add(dep.ecosystem);
      }
      return Array.from(ecos).sort();
    });

    const ecosystemCounts = computed(() => {
      const counts = {};
      for (const dep of dependencies.value) {
        const eco = dep.ecosystem || 'unknown';
        counts[eco] = (counts[eco] || 0) + 1;
      }
      return counts;
    });

    const totalDeps = computed(() => dependencies.value.length);
    const uniqueDeps = computed(() => {
      const names = new Set(dependencies.value.map(d => d.name));
      return names.size;
    });
    const repoCount = computed(() => {
      const repos = new Set();
      for (const dep of dependencies.value) {
        if (dep.repo) repos.add(dep.repo);
      }
      return repos.size;
    });

    const filteredDeps = computed(() => {
      let result = dependencies.value;

      if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase();
        result = result.filter(d => d.name.toLowerCase().includes(q));
      }

      if (activeEcosystem.value) {
        result = result.filter(d => d.ecosystem === activeEcosystem.value);
      }

      result = [...result].sort((a, b) => {
        switch (sortBy.value) {
          case 'ecosystem':
            return (a.ecosystem || '').localeCompare(b.ecosystem || '') || a.name.localeCompare(b.name);
          default:
            return a.name.localeCompare(b.name);
        }
      });

      return result;
    });

    function ecosystemColor(ecosystem) {
      const colors = {
        pip: '#f59e0b',
        pypi: '#f59e0b',
        python: '#f59e0b',
        npm: '#ef4444',
        yarn: '#ef4444',
        node: '#ef4444',
        maven: '#3b82f6',
        gradle: '#3b82f6',
        java: '#3b82f6',
        go: '#06b6d4',
        golang: '#06b6d4',
        nuget: '#8b5cf6',
        cargo: '#f97316',
        rust: '#f97316',
        gem: '#ec4899',
        ruby: '#ec4899',
        composer: '#6366f1',
        php: '#6366f1',
      };
      return colors[(ecosystem || '').toLowerCase()] || '#6b7280';
    }

    async function toggleExpand(name) {
      if (expandedDep.value === name) {
        expandedDep.value = null;
        usageData.value = null;
        return;
      }

      expandedDep.value = name;
      usageLoading.value = true;
      usageData.value = null;

      try {
        usageData.value = await api.dependencyUsage(name);
      } catch (e) {
        usageData.value = null;
      } finally {
        usageLoading.value = false;
      }
    }

    async function fetchDeps() {
      loading.value = true;
      error.value = null;
      try {
        dependencies.value = await api.dependencies();
      } catch (e) {
        error.value = e.message || 'Failed to load dependencies';
      } finally {
        loading.value = false;
      }
    }

    onMounted(() => {
      fetchDeps();
    });

    return {
      loading,
      error,
      dependencies,
      searchQuery,
      activeEcosystem,
      sortBy,
      sortOptions,
      ecosystems,
      ecosystemCounts,
      totalDeps,
      uniqueDeps,
      repoCount,
      filteredDeps,
      expandedDep,
      usageLoading,
      usageData,
      ecosystemColor,
      toggleExpand,
      fetchDeps,
      router,
    };
  },
};
