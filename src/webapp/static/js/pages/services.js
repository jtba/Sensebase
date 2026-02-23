// ============================================================
// SenseBase - Service Catalog Page
// ============================================================

import { ref, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { api } from '../api.js';

export default {
  name: 'ServicesPage',
  template: `
    <div class="p-6 max-w-7xl mx-auto">

      <!-- Detail view -->
      <div v-if="selectedName">

        <!-- Back button -->
        <button @click="goBack" class="flex items-center gap-2 text-gray-400 hover:text-gray-200 transition-colors mb-6 group">
          <svg class="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
          </svg>
          <span class="text-sm">Back to Services</span>
        </button>

        <!-- Loading detail -->
        <div v-if="detailLoading" class="space-y-4">
          <div class="skeleton h-10 w-64"></div>
          <div class="skeleton h-6 w-40"></div>
          <div class="skeleton h-32 w-full mt-6"></div>
          <div class="skeleton h-48 w-full mt-4"></div>
        </div>

        <!-- Detail error -->
        <div v-else-if="detailError" class="glass-card p-6 text-center">
          <p class="text-red-400">{{ detailError }}</p>
          <button @click="fetchDetail" class="mt-3 px-4 py-2 bg-accent-purple/20 text-accent-purple rounded-lg hover:bg-accent-purple/30 text-sm">Retry</button>
        </div>

        <!-- Detail content -->
        <div v-else-if="detailData">
          <!-- Header -->
          <div class="mb-8">
            <div class="flex items-start gap-3 flex-wrap">
              <h1 class="text-2xl font-bold text-gray-100">{{ detailData.name }}</h1>
              <span class="badge badge-service">{{ detailData.type || 'service' }}</span>
            </div>
            <div class="flex items-center gap-4 mt-2 text-sm text-gray-500">
              <span v-if="detailData.repo" class="flex items-center gap-1">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>
                {{ detailData.repo }}
              </span>
              <span v-if="detailData.source_file" class="font-mono text-xs text-gray-600">{{ detailData.source_file }}</span>
            </div>
            <button
              @click="router.push('/graph')"
              class="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-accent-purple/10 text-accent-purple rounded-lg hover:bg-accent-purple/20 transition-colors"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
              View in Graph
            </button>
          </div>

          <!-- Description -->
          <div v-if="detailData.description" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3">Description</h2>
            <p class="text-sm text-gray-300 leading-relaxed">{{ detailData.description }}</p>
          </div>

          <!-- Methods table -->
          <div v-if="detailData.methods && detailData.methods.length > 0" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Methods ({{ detailData.methods.length }})</h2>
            <div class="space-y-3">
              <div v-for="(method, i) in detailData.methods" :key="i" class="p-3 rounded-lg bg-surface/40 border border-border/30">
                <div class="flex items-start gap-2 mb-1">
                  <span class="font-mono text-sm text-accent-purple font-medium">{{ method.name || method }}</span>
                  <span v-if="method.returns" class="text-xs text-gray-500 font-mono mt-0.5">-> {{ method.returns }}</span>
                </div>
                <div v-if="method.params && method.params.length > 0" class="text-xs text-gray-500 font-mono mb-1">
                  ({{ formatParams(method.params) }})
                </div>
                <p v-if="method.docstring || method.description" class="text-xs text-gray-500 mt-1">{{ method.docstring || method.description }}</p>
              </div>
            </div>
          </div>

          <!-- Dependencies -->
          <div v-if="depsData && depsData.depends_on && depsData.depends_on.length > 0" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Dependencies ({{ depsData.depends_on.length }})</h2>
            <div class="space-y-2">
              <button
                v-for="dep in depsData.depends_on"
                :key="typeof dep === 'string' ? dep : dep.name"
                @click="navigateToService(typeof dep === 'string' ? dep : dep.name)"
                class="w-full text-left px-4 py-3 rounded-lg bg-surface/50 hover:bg-surface border border-border/50 hover:border-accent-purple/30 transition-all group flex items-center gap-3"
              >
                <svg class="w-4 h-4 text-gray-600 group-hover:text-accent-purple flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
                </svg>
                <span class="text-sm text-gray-300 group-hover:text-gray-100">{{ typeof dep === 'string' ? dep : dep.name }}</span>
              </button>
            </div>
          </div>

          <!-- Also show inline dependencies if no depsData -->
          <div v-else-if="detailData.dependencies && detailData.dependencies.length > 0" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Dependencies ({{ detailData.dependencies.length }})</h2>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="dep in detailData.dependencies"
                :key="dep"
                @click="navigateToService(dep)"
                class="px-3 py-1.5 text-sm rounded-lg bg-surface/50 border border-border/50 hover:border-accent-purple/30 text-gray-300 hover:text-gray-100 transition-all"
              >
                {{ dep }}
              </button>
            </div>
          </div>

          <!-- Depended By -->
          <div v-if="depsData && depsData.depended_by && depsData.depended_by.length > 0" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Depended By ({{ depsData.depended_by.length }})</h2>
            <div class="space-y-2">
              <button
                v-for="dep in depsData.depended_by"
                :key="typeof dep === 'string' ? dep : dep.name"
                @click="navigateToService(typeof dep === 'string' ? dep : dep.name)"
                class="w-full text-left px-4 py-3 rounded-lg bg-surface/50 hover:bg-surface border border-border/50 hover:border-accent-teal/30 transition-all group flex items-center gap-3"
              >
                <svg class="w-4 h-4 text-gray-600 group-hover:text-accent-teal flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 17l-5-5m0 0l5-5m-5 5h12"/>
                </svg>
                <span class="text-sm text-gray-300 group-hover:text-gray-100">{{ typeof dep === 'string' ? dep : dep.name }}</span>
              </button>
            </div>
          </div>

          <!-- Data Accessed -->
          <div v-if="depsData && depsData.data_accessed && depsData.data_accessed.length > 0" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Data Accessed</h2>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="schema in depsData.data_accessed"
                :key="typeof schema === 'string' ? schema : schema.name"
                @click="router.push('/schemas/' + encodeURIComponent(typeof schema === 'string' ? schema : schema.name))"
                class="px-3 py-1.5 text-sm rounded-lg bg-accent-blue/10 border border-accent-blue/20 text-accent-blue hover:bg-accent-blue/20 transition-all"
              >
                {{ typeof schema === 'string' ? schema : schema.name }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- List view -->
      <div v-else>
        <!-- Header -->
        <div class="mb-6">
          <h1 class="text-2xl font-bold gradient-text mb-1">Service Catalog</h1>
          <p class="text-gray-500 text-sm">Browse services, handlers, rules, and workflows</p>
        </div>

        <!-- Search & Filters -->
        <div class="mb-6">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search services by name..."
            class="search-input w-full px-4 py-2.5 text-sm"
          />
        </div>

        <!-- Count -->
        <div class="flex items-center justify-between mb-4 text-xs text-gray-500">
          <span>{{ filteredServices.length }} services</span>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div v-for="i in 6" :key="i" class="glass-card p-5">
            <div class="skeleton h-5 w-32 mb-3"></div>
            <div class="skeleton h-4 w-20 mb-2"></div>
            <div class="skeleton h-3 w-48 mb-2"></div>
            <div class="skeleton h-3 w-24"></div>
          </div>
        </div>

        <!-- Error -->
        <div v-else-if="listError" class="glass-card p-6 text-center">
          <p class="text-red-400">{{ listError }}</p>
          <button @click="fetchList" class="mt-3 px-4 py-2 bg-accent-purple/20 text-accent-purple rounded-lg hover:bg-accent-purple/30 text-sm">Retry</button>
        </div>

        <!-- Empty -->
        <div v-else-if="filteredServices.length === 0 && !loading" class="glass-card p-8 text-center">
          <svg class="w-12 h-12 text-gray-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/>
          </svg>
          <p class="text-gray-400">No services found{{ searchQuery ? ' matching "' + searchQuery + '"' : '' }}</p>
        </div>

        <!-- Service Grid -->
        <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <button
            v-for="service in filteredServices"
            :key="service.name + (service.repo || '')"
            @click="navigateToService(service.name)"
            class="glass-card glass-card-interactive p-5 text-left transition-all"
          >
            <div class="flex items-start justify-between gap-2 mb-2">
              <h3 class="text-sm font-semibold text-gray-200 truncate">{{ service.name }}</h3>
              <span class="badge badge-service flex-shrink-0">{{ service.type || 'service' }}</span>
            </div>
            <div v-if="service.repo" class="text-xs text-gray-500 mb-2 truncate">{{ service.repo }}</div>
            <p v-if="service.description" class="text-xs text-gray-500 mb-3 line-clamp-2">{{ service.description }}</p>
            <div class="flex gap-4 text-xs text-gray-500">
              <span>
                <span class="text-gray-300 font-medium">{{ (service.dependencies || []).length }}</span> deps
              </span>
              <span>
                <span class="text-gray-300 font-medium">{{ (service.methods || []).length }}</span> methods
              </span>
            </div>
          </button>
        </div>
      </div>
    </div>
  `,
  setup() {
    const router = useRouter();
    const route = useRoute();

    const loading = ref(false);
    const listError = ref(null);
    const services = ref([]);
    const searchQuery = ref('');

    const detailLoading = ref(false);
    const detailError = ref(null);
    const detailData = ref(null);
    const depsData = ref(null);

    const selectedName = computed(() => route.params.name || null);

    const filteredServices = computed(() => {
      let result = services.value;
      if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase();
        result = result.filter(s =>
          s.name.toLowerCase().includes(q) ||
          (s.description || '').toLowerCase().includes(q)
        );
      }
      return result.sort((a, b) => a.name.localeCompare(b.name));
    });

    function navigateToService(name) {
      router.push(`/services/${encodeURIComponent(name)}`);
    }

    function goBack() {
      router.push('/services');
    }

    function formatParams(params) {
      if (!params || params.length === 0) return '';
      return params.map(p => {
        if (typeof p === 'string') return p;
        const name = p.name || '';
        const type = p.type ? `: ${p.type}` : '';
        return `${name}${type}`;
      }).join(', ');
    }

    async function fetchList() {
      loading.value = true;
      listError.value = null;
      try {
        services.value = await api.services();
      } catch (e) {
        listError.value = e.message || 'Failed to load services';
      } finally {
        loading.value = false;
      }
    }

    async function fetchDetail() {
      if (!selectedName.value) return;
      detailLoading.value = true;
      detailError.value = null;
      detailData.value = null;
      depsData.value = null;

      try {
        const results = await api.service(selectedName.value);
        detailData.value = Array.isArray(results) ? results[0] : results;
      } catch (e) {
        detailError.value = e.message || 'Failed to load service';
      } finally {
        detailLoading.value = false;
      }

      // Fetch dependency graph separately (may 404)
      try {
        depsData.value = await api.serviceDependencies(selectedName.value);
      } catch (e) {
        depsData.value = null;
      }
    }

    watch(selectedName, (name) => {
      if (name) {
        fetchDetail();
      }
    }, { immediate: true });

    onMounted(() => {
      fetchList();
    });

    return {
      loading,
      listError,
      services,
      searchQuery,
      filteredServices,
      selectedName,
      detailLoading,
      detailError,
      detailData,
      depsData,
      router,
      navigateToService,
      goBack,
      formatParams,
      fetchList,
      fetchDetail,
    };
  },
};
