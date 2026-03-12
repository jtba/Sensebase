// ============================================================
// SenseBase - Interfaces Page
// ============================================================

import { ref, computed, onMounted } from 'vue';
import { api } from '../api.js';

export default {
  name: 'InterfacesPage',
  template: `
    <div class="p-6 max-w-7xl mx-auto">

      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold gradient-text mb-1">Interfaces</h1>
        <p class="text-gray-500 text-sm">Cross-repo type polymorphism: schemas sharing common field signatures grouped under inferred interfaces</p>
      </div>

      <!-- Summary stats -->
      <div v-if="!loading && !error && interfaces.length > 0" class="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
        <div class="glass-card p-4 stat-card-purple">
          <div class="text-2xl font-bold text-gray-100">{{ interfaces.length }}</div>
          <div class="text-xs text-gray-500">Interfaces</div>
        </div>
        <div class="glass-card p-4 stat-card-blue">
          <div class="text-2xl font-bold text-gray-100">{{ totalImplementors }}</div>
          <div class="text-xs text-gray-500">Total Implementors</div>
        </div>
        <div class="glass-card p-4 stat-card-teal">
          <div class="text-2xl font-bold text-gray-100">{{ totalProperties }}</div>
          <div class="text-xs text-gray-500">Shared Properties</div>
        </div>
      </div>

      <!-- Search -->
      <div class="mb-4">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search interfaces by name or implementor..."
          class="search-input w-full px-4 py-2.5 text-sm"
        />
      </div>

      <div class="flex items-center mb-4 text-xs text-gray-500">
        <span class="ml-auto">{{ filtered.length }} interfaces</span>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="grid gap-4">
        <div v-for="i in 3" :key="i" class="glass-card p-5">
          <div class="skeleton h-5 w-40 mb-3"></div>
          <div class="skeleton h-4 w-64 mb-2"></div>
          <div class="skeleton h-3 w-48"></div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="glass-card p-6 text-center">
        <p class="text-red-400">{{ error }}</p>
        <button @click="fetchData" class="mt-3 px-4 py-2 bg-accent-purple/20 text-accent-purple rounded-lg hover:bg-accent-purple/30 text-sm">Retry</button>
      </div>

      <!-- Empty -->
      <div v-else-if="filtered.length === 0" class="glass-card p-8 text-center">
        <p class="text-gray-400">No interfaces found{{ searchQuery ? ' matching "' + searchQuery + '"' : '' }}</p>
        <p class="text-gray-600 text-sm mt-1">Interfaces are inferred when schemas across different repos share common field signatures.</p>
      </div>

      <!-- Interface List -->
      <div v-else class="space-y-4">
        <div
          v-for="iface in filtered"
          :key="iface.name"
          class="glass-card glass-card-interactive p-5"
        >
          <div class="flex items-start justify-between gap-2 mb-3">
            <div>
              <h3 class="text-base font-semibold text-gray-200">{{ iface.name }}</h3>
              <p v-if="iface.description" class="text-sm text-gray-400 mt-0.5">{{ iface.description }}</p>
            </div>
            <div class="flex items-center gap-2">
              <span
                v-if="iface.status && iface.status !== 'active'"
                class="badge text-xs"
                :class="statusClass(iface.status)"
              >{{ iface.status }}</span>
              <span class="badge bg-accent-purple/15 text-accent-purple border-accent-purple/30 text-xs">
                {{ (iface.implementors || []).length }} implementors
              </span>
            </div>
          </div>

          <!-- Properties -->
          <div v-if="iface.properties && iface.properties.length > 0" class="mb-3">
            <h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Shared Properties</h4>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="prop in iface.properties"
                :key="prop.name"
                class="px-2 py-1 bg-surface rounded text-xs font-mono"
              >
                <span class="text-gray-300">{{ prop.name }}</span><span class="text-gray-600">: {{ prop.type }}</span>
              </span>
            </div>
          </div>

          <!-- Implementors -->
          <div v-if="iface.implementors && iface.implementors.length > 0">
            <h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Implemented By</h4>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="impl in iface.implementors"
                :key="impl"
                class="px-2 py-1 bg-accent-blue/10 text-accent-blue rounded text-xs border border-accent-blue/20"
              >{{ impl }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const loading = ref(false);
    const error = ref(null);
    const interfaces = ref([]);
    const searchQuery = ref('');

    const totalImplementors = computed(() => {
      let count = 0;
      for (const iface of interfaces.value) {
        count += (iface.implementors || []).length;
      }
      return count;
    });

    const totalProperties = computed(() => {
      let count = 0;
      for (const iface of interfaces.value) {
        count += (iface.properties || []).length;
      }
      return count;
    });

    const filtered = computed(() => {
      if (!searchQuery.value) return interfaces.value;
      const q = searchQuery.value.toLowerCase();
      return interfaces.value.filter(iface =>
        (iface.name || '').toLowerCase().includes(q) ||
        (iface.implementors || []).some(impl => impl.toLowerCase().includes(q))
      );
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
        const data = await api.interfaces();
        interfaces.value = data.interfaces || [];
      } catch (e) {
        error.value = e.message || 'Failed to load interfaces';
      } finally {
        loading.value = false;
      }
    }

    onMounted(fetchData);

    return {
      loading, error, interfaces, searchQuery,
      totalImplementors, totalProperties, filtered,
      statusClass, fetchData,
    };
  },
};
