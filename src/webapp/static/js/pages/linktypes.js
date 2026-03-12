// ============================================================
// SenseBase - Link Types Page
// ============================================================

import { ref, computed, onMounted } from 'vue';
import { api } from '../api.js';

export default {
  name: 'LinkTypesPage',
  template: `
    <div class="p-6 max-w-7xl mx-auto">

      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold gradient-text mb-1">Link Types</h1>
        <p class="text-gray-500 text-sm">First-class bidirectional relationships between entities with cardinality and properties</p>
      </div>

      <!-- Summary stats -->
      <div v-if="!loading && !error && linkTypes.length > 0" class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div class="glass-card p-4 stat-card-blue">
          <div class="text-2xl font-bold text-gray-100">{{ linkTypes.length }}</div>
          <div class="text-xs text-gray-500">Total Link Types</div>
        </div>
        <div class="glass-card p-4 stat-card-purple">
          <div class="text-2xl font-bold text-gray-100">{{ bidirectionalCount }}</div>
          <div class="text-xs text-gray-500">Bidirectional</div>
        </div>
        <div class="glass-card p-4 stat-card-teal">
          <div class="text-2xl font-bold text-gray-100">{{ Object.keys(cardinalityCounts).length }}</div>
          <div class="text-xs text-gray-500">Cardinality Types</div>
        </div>
        <div class="glass-card p-4 stat-card-amber">
          <div class="text-2xl font-bold text-gray-100">{{ uniqueEntities }}</div>
          <div class="text-xs text-gray-500">Connected Entities</div>
        </div>
      </div>

      <!-- Cardinality breakdown -->
      <div v-if="Object.keys(cardinalityCounts).length > 0 && !loading" class="glass-card p-4 mb-6">
        <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Cardinality Breakdown</h3>
        <div class="flex flex-wrap gap-3">
          <button
            @click="activeCardinality = null"
            class="filter-chip"
            :class="{ 'filter-chip-active': !activeCardinality }"
          >All</button>
          <button
            v-for="(count, card) in cardinalityCounts"
            :key="card"
            @click="activeCardinality = activeCardinality === card ? null : card"
            class="filter-chip"
            :class="{ 'filter-chip-active': activeCardinality === card }"
          >
            {{ card }} ({{ count }})
          </button>
        </div>
      </div>

      <!-- Search -->
      <div class="mb-4">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search link types by name, source, or target..."
          class="search-input w-full px-4 py-2.5 text-sm"
        />
      </div>

      <div class="flex items-center mb-4 text-xs text-gray-500">
        <span class="ml-auto">{{ filtered.length }} link types</span>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="grid gap-4 sm:grid-cols-2">
        <div v-for="i in 4" :key="i" class="glass-card p-5">
          <div class="skeleton h-5 w-40 mb-3"></div>
          <div class="skeleton h-4 w-24 mb-2"></div>
          <div class="skeleton h-3 w-32"></div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="glass-card p-6 text-center">
        <p class="text-red-400">{{ error }}</p>
        <button @click="fetchData" class="mt-3 px-4 py-2 bg-accent-blue/20 text-accent-blue rounded-lg hover:bg-accent-blue/30 text-sm">Retry</button>
      </div>

      <!-- Empty -->
      <div v-else-if="filtered.length === 0" class="glass-card p-8 text-center">
        <p class="text-gray-400">No link types found{{ searchQuery ? ' matching "' + searchQuery + '"' : '' }}</p>
      </div>

      <!-- Link Type Grid -->
      <div v-else class="grid gap-4 sm:grid-cols-2">
        <div
          v-for="lt in filtered"
          :key="lt.name"
          class="glass-card glass-card-interactive p-5"
        >
          <div class="flex items-start justify-between gap-2 mb-3">
            <h3 class="text-sm font-semibold text-gray-200 font-mono">{{ lt.name }}</h3>
            <span
              v-if="lt.status && lt.status !== 'active'"
              class="badge text-xs"
              :class="statusClass(lt.status)"
            >{{ lt.status }}</span>
          </div>

          <!-- Source -> Target with cardinality -->
          <div class="flex items-center gap-2 mb-3 text-sm">
            <span class="px-2 py-0.5 bg-accent-blue/15 text-accent-blue rounded text-xs font-mono">{{ lt.source_type }}</span>
            <span class="text-gray-500">&#8594;</span>
            <span class="px-2 py-0.5 bg-accent-purple/15 text-accent-purple rounded text-xs font-mono">{{ lt.target_type }}</span>
          </div>

          <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500">
            <span class="px-1.5 py-0.5 bg-surface rounded">{{ lt.cardinality || 'unknown' }}</span>
            <span v-if="lt.bidirectional" class="px-1.5 py-0.5 bg-green-500/10 text-green-400 rounded border border-green-500/20">bidirectional</span>
            <span v-if="lt.inverse_name" class="text-gray-600">inv: {{ lt.inverse_name }}</span>
          </div>

          <p v-if="lt.description" class="mt-2 text-xs text-gray-400">{{ lt.description }}</p>

          <!-- Properties -->
          <div v-if="lt.properties && lt.properties.length > 0" class="mt-3 border-t border-border/50 pt-2">
            <h4 class="text-xs font-semibold text-gray-500 uppercase mb-1">Properties</h4>
            <div v-for="prop in lt.properties" :key="prop.name" class="text-xs text-gray-400">
              <span class="font-mono text-gray-300">{{ prop.name }}</span>: {{ prop.type }}
              <span v-if="prop.description" class="text-gray-500"> &mdash; {{ prop.description }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const loading = ref(false);
    const error = ref(null);
    const linkTypes = ref([]);
    const searchQuery = ref('');
    const activeCardinality = ref(null);

    const bidirectionalCount = computed(() =>
      linkTypes.value.filter(lt => lt.bidirectional).length
    );

    const uniqueEntities = computed(() => {
      const entities = new Set();
      for (const lt of linkTypes.value) {
        if (lt.source_type) entities.add(lt.source_type);
        if (lt.target_type) entities.add(lt.target_type);
      }
      return entities.size;
    });

    const cardinalityCounts = computed(() => {
      const counts = {};
      for (const lt of linkTypes.value) {
        const c = lt.cardinality || 'unknown';
        counts[c] = (counts[c] || 0) + 1;
      }
      return counts;
    });

    const filtered = computed(() => {
      let result = linkTypes.value;
      if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase();
        result = result.filter(lt =>
          (lt.name || '').toLowerCase().includes(q) ||
          (lt.source_type || '').toLowerCase().includes(q) ||
          (lt.target_type || '').toLowerCase().includes(q)
        );
      }
      if (activeCardinality.value) {
        result = result.filter(lt => lt.cardinality === activeCardinality.value);
      }
      return result;
    });

    function statusClass(status) {
      const map = {
        deprecated: 'bg-red-500/10 text-red-400 border border-red-500/20',
        experimental: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
        draft: 'bg-gray-500/10 text-gray-400 border border-gray-500/20',
      };
      return map[status] || '';
    }

    async function fetchData() {
      loading.value = true;
      error.value = null;
      try {
        const data = await api.linkTypes();
        linkTypes.value = data.link_types || [];
      } catch (e) {
        error.value = e.message || 'Failed to load link types';
      } finally {
        loading.value = false;
      }
    }

    onMounted(fetchData);

    return {
      loading, error, linkTypes, searchQuery, activeCardinality,
      bidirectionalCount, uniqueEntities, cardinalityCounts, filtered,
      statusClass, fetchData,
    };
  },
};
