// ============================================================
// SenseBase - Dependency Explorer Page
// ============================================================

import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../api.js';

export default {
  name: 'DependenciesPage',
  template: `
    <div class="p-6 max-w-7xl mx-auto">

      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold gradient-text mb-1">Dependency Explorer</h1>
        <p class="text-gray-500 text-sm">Service dependencies, data relationships, and external packages across your system</p>
      </div>

      <!-- Summary stats -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div class="glass-card p-4 stat-card-purple">
          <div class="text-2xl font-bold text-gray-100">{{ svcEdgeCount }}</div>
          <div class="text-xs text-gray-500">Service Links</div>
        </div>
        <div class="glass-card p-4 stat-card-blue">
          <div class="text-2xl font-bold text-gray-100">{{ dataLinkCount }}</div>
          <div class="text-xs text-gray-500">Data Links</div>
        </div>
        <div class="glass-card p-4 stat-card-amber">
          <div class="text-2xl font-bold text-gray-100">{{ pkgCount }}</div>
          <div class="text-xs text-gray-500">External Packages</div>
        </div>
        <div class="glass-card p-4 stat-card-teal">
          <div class="text-2xl font-bold text-gray-100">{{ ecosystemCount }}</div>
          <div class="text-xs text-gray-500">Ecosystems</div>
        </div>
      </div>

      <!-- Tab bar -->
      <div class="flex gap-1 mb-5 bg-surface-dark/50 rounded-lg p-1 w-fit">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          @click="switchTab(tab.key)"
          class="px-4 py-2 rounded-md text-sm font-medium transition-all-200"
          :class="activeTab === tab.key
            ? 'bg-accent-blue/20 text-accent-blue border border-accent-blue/30'
            : 'text-gray-400 hover:text-gray-200'"
        >
          {{ tab.label }}
          <span class="ml-1.5 text-xs opacity-60">{{ tab.count }}</span>
        </button>
      </div>

      <!-- Search -->
      <div class="mb-4">
        <input
          v-model="searchQuery"
          type="text"
          :placeholder="searchPlaceholder"
          class="search-input w-full px-4 py-2.5 text-sm"
        />
      </div>

      <!-- ============ TAB 1: Service Dependencies ============ -->
      <div v-if="activeTab === 'services'">

        <!-- Loading -->
        <div v-if="svcLoading" class="space-y-4">
          <div v-for="i in 4" :key="i" class="glass-card p-5">
            <div class="skeleton h-5 w-48 mb-3"></div>
            <div class="skeleton h-4 w-full mb-2"></div>
            <div class="skeleton h-3 w-32"></div>
          </div>
        </div>

        <!-- Error -->
        <div v-else-if="svcError" class="glass-card p-6 text-center">
          <p class="text-red-400">{{ svcError }}</p>
          <button @click="fetchServiceDeps" class="mt-3 px-4 py-2 bg-accent-purple/20 text-accent-purple rounded-lg hover:bg-accent-purple/30 text-sm">Retry</button>
        </div>

        <!-- Empty -->
        <div v-else-if="filteredSvcDeps.length === 0" class="glass-card p-8 text-center">
          <svg class="w-12 h-12 text-gray-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"/>
          </svg>
          <p class="text-gray-400">No service dependencies found{{ searchQuery ? ' matching "' + searchQuery + '"' : '' }}</p>
          <p class="text-gray-600 text-sm mt-1">Run the pipeline with LLM extraction to discover service-to-service dependencies.</p>
        </div>

        <!-- Service dep cards: grouped by source service -->
        <div v-else class="space-y-4">
          <div
            v-for="group in filteredSvcDeps"
            :key="group.service"
            class="glass-card p-5"
          >
            <div class="flex items-start justify-between gap-3 mb-3">
              <div class="flex items-center gap-2">
                <button
                  @click="router.push('/services/' + encodeURIComponent(group.service))"
                  class="text-base font-semibold text-accent-purple hover:text-accent-blue transition-colors"
                >{{ group.service }}</button>
                <span v-if="group.domain" class="badge badge-schema text-xs">{{ group.domain }}</span>
              </div>
              <span class="text-xs text-gray-500">{{ group.deps.length }} dep{{ group.deps.length !== 1 ? 's' : '' }}</span>
            </div>

            <p v-if="group.purpose" class="text-sm text-gray-400 mb-3">{{ group.purpose }}</p>

            <!-- Dependency edges -->
            <div v-if="group.deps.length > 0" class="space-y-2">
              <div
                v-for="dep in group.deps"
                :key="dep.target"
                class="flex items-center gap-3 px-3 py-2 rounded-lg bg-surface/30 border border-border/30"
              >
                <svg class="w-4 h-4 text-accent-purple flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
                </svg>
                <button
                  @click="router.push('/services/' + encodeURIComponent(dep.target))"
                  class="text-sm font-medium text-gray-200 hover:text-accent-blue transition-colors"
                >{{ dep.target }}</button>
                <span v-if="dep.isService" class="px-1.5 py-0.5 text-xs rounded bg-accent-purple/10 text-accent-purple border border-accent-purple/20">service</span>
                <span v-else class="px-1.5 py-0.5 text-xs rounded bg-gray-500/10 text-gray-500 border border-gray-500/20">external</span>
              </div>
            </div>

            <!-- Data owned -->
            <div v-if="group.dataOwned && group.dataOwned.length > 0" class="mt-3 pt-3 border-t border-border/30">
              <span class="text-xs text-gray-500 uppercase tracking-wider font-semibold">Data Owned: </span>
              <span v-for="(d, i) in group.dataOwned" :key="d" class="text-xs text-accent-teal">{{ d }}<span v-if="i < group.dataOwned.length - 1" class="text-gray-600">, </span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- ============ TAB 2: Data Dependencies ============ -->
      <div v-if="activeTab === 'data'">

        <!-- Cardinality filter chips -->
        <div v-if="!dataLoading && !dataError && Object.keys(cardinalityCounts).length > 0" class="flex flex-wrap gap-2 mb-4">
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
          >{{ card }} ({{ count }})</button>
        </div>

        <!-- Loading -->
        <div v-if="dataLoading" class="grid gap-4 sm:grid-cols-2">
          <div v-for="i in 4" :key="i" class="glass-card p-5">
            <div class="skeleton h-5 w-40 mb-3"></div>
            <div class="skeleton h-4 w-24 mb-2"></div>
            <div class="skeleton h-3 w-32"></div>
          </div>
        </div>

        <!-- Error -->
        <div v-else-if="dataError" class="glass-card p-6 text-center">
          <p class="text-red-400">{{ dataError }}</p>
          <button @click="fetchDataDeps" class="mt-3 px-4 py-2 bg-accent-blue/20 text-accent-blue rounded-lg hover:bg-accent-blue/30 text-sm">Retry</button>
        </div>

        <!-- Empty -->
        <div v-else-if="filteredDataDeps.length === 0 && filteredFlows.length === 0" class="glass-card p-8 text-center">
          <p class="text-gray-400">No data dependencies found{{ searchQuery ? ' matching "' + searchQuery + '"' : '' }}</p>
          <p class="text-gray-600 text-sm mt-1">Link types are created when schemas have relationships to other schemas.</p>
        </div>

        <template v-else>
          <!-- Link Types -->
          <div v-if="filteredDataDeps.length > 0" class="mb-6">
            <div class="flex items-center gap-2 mb-3 text-xs text-gray-500">
              <span class="font-semibold uppercase tracking-wider">Schema Links</span>
              <span class="ml-auto">{{ filteredDataDeps.length }} link types</span>
            </div>
            <div class="grid gap-4 sm:grid-cols-2">
              <div
                v-for="lt in filteredDataDeps"
                :key="lt.name"
                class="glass-card p-4"
              >
                <!-- Source -> Target -->
                <div class="flex items-center gap-2 mb-2">
                  <span class="px-2 py-0.5 bg-accent-blue/15 text-accent-blue rounded text-xs font-mono">{{ lt.source_type }}</span>
                  <svg class="w-4 h-4 text-gray-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
                  </svg>
                  <span class="px-2 py-0.5 bg-accent-purple/15 text-accent-purple rounded text-xs font-mono">{{ lt.target_type }}</span>
                </div>
                <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                  <span class="px-1.5 py-0.5 bg-surface rounded">{{ lt.cardinality || 'unknown' }}</span>
                  <span v-if="lt.bidirectional" class="px-1.5 py-0.5 bg-green-500/10 text-green-400 rounded border border-green-500/20">bidirectional</span>
                </div>
                <p v-if="lt.description" class="mt-2 text-xs text-gray-400">{{ lt.description }}</p>
              </div>
            </div>
          </div>

          <!-- Data Flows -->
          <div v-if="filteredFlows.length > 0">
            <div class="flex items-center gap-2 mb-3 text-xs text-gray-500">
              <span class="font-semibold uppercase tracking-wider">Data Flows</span>
              <span class="ml-auto">{{ filteredFlows.length }} flows</span>
            </div>
            <div class="glass-card overflow-hidden">
              <div class="overflow-x-auto">
                <table class="w-full">
                  <thead>
                    <tr class="border-b border-border">
                      <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-5 py-3">Source</th>
                      <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-5 py-3"></th>
                      <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-5 py-3">Target</th>
                      <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-5 py-3">Type</th>
                      <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-5 py-3">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(flow, i) in filteredFlows" :key="i" class="border-b border-border/50 hover:bg-surface-light/30 transition-colors">
                      <td class="px-5 py-3 text-sm font-mono text-accent-blue">{{ flow.source }}</td>
                      <td class="px-2 py-3 text-gray-500">&#8594;</td>
                      <td class="px-5 py-3 text-sm font-mono text-accent-purple">{{ flow.target }}</td>
                      <td class="px-5 py-3">
                        <span v-if="flow.type" class="px-1.5 py-0.5 text-xs rounded bg-surface border border-border/50">{{ flow.type }}</span>
                      </td>
                      <td class="px-5 py-3 text-xs text-gray-400">{{ flow.description }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- ============ TAB 3: External Packages ============ -->
      <div v-if="activeTab === 'packages'">

        <!-- Ecosystem filter chips -->
        <div v-if="!pkgLoading && !pkgError && ecosystems.length > 0" class="flex flex-wrap gap-2 mb-4">
          <button
            @click="activeEcosystem = null"
            class="filter-chip"
            :class="{ 'filter-chip-active': !activeEcosystem }"
          >All</button>
          <button
            v-for="eco in ecosystems"
            :key="eco"
            @click="activeEcosystem = activeEcosystem === eco ? null : eco"
            class="filter-chip"
            :class="{ 'filter-chip-active': activeEcosystem === eco }"
          >{{ eco }} ({{ ecosystemCounts[eco] }})</button>
        </div>

        <!-- Sort -->
        <div v-if="!pkgLoading && !pkgError" class="flex items-center gap-2 mb-4 text-xs text-gray-500">
          <span>Sort by:</span>
          <button
            v-for="s in pkgSortOptions"
            :key="s.key"
            @click="pkgSortBy = s.key"
            class="px-2 py-1 rounded"
            :class="pkgSortBy === s.key ? 'bg-accent-amber/15 text-accent-amber' : 'hover:text-gray-300'"
          >{{ s.label }}</button>
          <span class="ml-auto text-gray-600">{{ filteredPackages.length }} packages</span>
        </div>

        <!-- Loading -->
        <div v-if="pkgLoading" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div v-for="i in 6" :key="i" class="glass-card p-5">
            <div class="skeleton h-5 w-32 mb-3"></div>
            <div class="skeleton h-4 w-20 mb-2"></div>
            <div class="skeleton h-3 w-24"></div>
          </div>
        </div>

        <!-- Error -->
        <div v-else-if="pkgError" class="glass-card p-6 text-center">
          <p class="text-red-400">{{ pkgError }}</p>
          <button @click="fetchPackages" class="mt-3 px-4 py-2 bg-accent-amber/20 text-accent-amber rounded-lg hover:bg-accent-amber/30 text-sm">Retry</button>
        </div>

        <!-- Empty -->
        <div v-else-if="filteredPackages.length === 0" class="glass-card p-8 text-center">
          <p class="text-gray-400">No packages found{{ searchQuery ? ' matching "' + searchQuery + '"' : '' }}</p>
        </div>

        <!-- Package Grid -->
        <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="dep in filteredPackages"
            :key="dep.name"
            class="glass-card glass-card-interactive overflow-hidden"
          >
            <button
              @click="toggleExpand(dep.name)"
              class="w-full text-left p-5 transition-all"
            >
              <div class="flex items-start justify-between gap-2 mb-2">
                <h3 class="text-sm font-semibold text-gray-200 truncate font-mono">{{ dep.name }}</h3>
                <span
                  class="badge flex-shrink-0"
                  :style="{ background: ecosystemColor(dep.ecosystem) + '20', color: ecosystemColor(dep.ecosystem), borderColor: ecosystemColor(dep.ecosystem) + '40' }"
                >{{ dep.ecosystem || 'unknown' }}</span>
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
            <div v-if="expandedPkg === dep.name" class="border-t border-border/50 bg-surface/20 p-4">
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
    </div>
  `,
  setup() {
    const router = useRouter();

    // ---- Shared state ----
    const activeTab = ref('services');
    const searchQuery = ref('');
    const tabLoaded = ref({ services: false, data: false, packages: false });

    // ---- Tab 1: Service Dependencies ----
    const svcLoading = ref(false);
    const svcError = ref(null);
    const svcServices = ref([]);
    const svcRelationships = ref({});

    // ---- Tab 2: Data Dependencies ----
    const dataLoading = ref(false);
    const dataError = ref(null);
    const dataLinkTypes = ref([]);
    const dataFlows = ref([]);
    const activeCardinality = ref(null);

    // ---- Tab 3: External Packages ----
    const pkgLoading = ref(false);
    const pkgError = ref(null);
    const pkgDependencies = ref([]);
    const activeEcosystem = ref(null);
    const pkgSortBy = ref('name');
    const expandedPkg = ref(null);
    const usageLoading = ref(false);
    const usageData = ref(null);

    const pkgSortOptions = [
      { key: 'name', label: 'Name' },
      { key: 'ecosystem', label: 'Ecosystem' },
    ];

    // ---- Tab switching ----
    function switchTab(key) {
      activeTab.value = key;
      if (!tabLoaded.value[key]) {
        loadTab(key);
      }
    }

    function loadTab(key) {
      switch (key) {
        case 'services': fetchServiceDeps(); break;
        case 'data': fetchDataDeps(); break;
        case 'packages': fetchPackages(); break;
      }
    }

    // ---- Search placeholder ----
    const searchPlaceholder = computed(() => {
      switch (activeTab.value) {
        case 'services': return 'Search services by name, domain, or purpose...';
        case 'data': return 'Search link types by source, target, or description...';
        case 'packages': return 'Search packages by name...';
        default: return 'Search...';
      }
    });

    // ---- Tabs definition ----
    const tabs = computed(() => [
      { key: 'services', label: 'Service Dependencies', count: svcEdgeCount.value },
      { key: 'data', label: 'Data Dependencies', count: dataLinkCount.value },
      { key: 'packages', label: 'External Packages', count: pkgCount.value },
    ]);

    // ---- Header stat counts ----
    const svcEdgeCount = computed(() => {
      let count = 0;
      for (const svc of svcServices.value) {
        count += (svc.dependencies || []).length;
      }
      return count;
    });
    const dataLinkCount = computed(() => dataLinkTypes.value.length);
    const pkgCount = computed(() => pkgDependencies.value.length);
    const ecosystemCount = computed(() => {
      const ecos = new Set();
      for (const d of pkgDependencies.value) {
        if (d.ecosystem) ecos.add(d.ecosystem);
      }
      return ecos.size;
    });

    // ==================================================================
    // TAB 1: Service Dependencies
    // ==================================================================

    const knownServiceNames = computed(() => {
      return new Set(svcServices.value.map(s => s.name));
    });

    const svcServiceMap = computed(() => {
      const map = {};
      for (const entry of (svcRelationships.value.service_map || [])) {
        map[entry.service] = entry;
      }
      return map;
    });

    // Build grouped view: one entry per service that has deps or is depended-upon
    const svcGroups = computed(() => {
      const groups = {};
      for (const svc of svcServices.value) {
        const deps = (svc.dependencies || []).map(target => ({
          target,
          isService: knownServiceNames.value.has(target),
        }));
        if (deps.length === 0) continue;

        const meta = svcServiceMap.value[svc.name] || {};
        groups[svc.name] = {
          service: svc.name,
          repo: svc.repo,
          domain: meta.domain || '',
          purpose: meta.purpose || svc.description || '',
          dataOwned: meta.data_owned || [],
          deps,
        };
      }
      return Object.values(groups).sort((a, b) => b.deps.length - a.deps.length);
    });

    const filteredSvcDeps = computed(() => {
      if (!searchQuery.value) return svcGroups.value;
      const q = searchQuery.value.toLowerCase();
      return svcGroups.value.filter(g =>
        g.service.toLowerCase().includes(q) ||
        g.domain.toLowerCase().includes(q) ||
        g.purpose.toLowerCase().includes(q) ||
        g.deps.some(d => d.target.toLowerCase().includes(q))
      );
    });

    async function fetchServiceDeps() {
      svcLoading.value = true;
      svcError.value = null;
      try {
        const [services, rels] = await Promise.all([
          api.services(),
          api.relationships().catch(() => ({})),
        ]);
        svcServices.value = services;
        svcRelationships.value = rels;
        tabLoaded.value.services = true;
      } catch (e) {
        svcError.value = e.message || 'Failed to load service dependencies';
      } finally {
        svcLoading.value = false;
      }
    }

    // ==================================================================
    // TAB 2: Data Dependencies
    // ==================================================================

    const cardinalityCounts = computed(() => {
      const counts = {};
      for (const lt of dataLinkTypes.value) {
        const c = lt.cardinality || 'unknown';
        counts[c] = (counts[c] || 0) + 1;
      }
      return counts;
    });

    const filteredDataDeps = computed(() => {
      let result = dataLinkTypes.value;
      if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase();
        result = result.filter(lt =>
          (lt.name || '').toLowerCase().includes(q) ||
          (lt.source_type || '').toLowerCase().includes(q) ||
          (lt.target_type || '').toLowerCase().includes(q) ||
          (lt.description || '').toLowerCase().includes(q)
        );
      }
      if (activeCardinality.value) {
        result = result.filter(lt => lt.cardinality === activeCardinality.value);
      }
      return result;
    });

    const filteredFlows = computed(() => {
      if (!searchQuery.value) return dataFlows.value;
      const q = searchQuery.value.toLowerCase();
      return dataFlows.value.filter(f =>
        (f.source || '').toLowerCase().includes(q) ||
        (f.target || '').toLowerCase().includes(q) ||
        (f.description || '').toLowerCase().includes(q)
      );
    });

    async function fetchDataDeps() {
      dataLoading.value = true;
      dataError.value = null;
      try {
        const [ltData, flowData] = await Promise.all([
          api.linkTypes(),
          api.dataFlows().catch(() => ({ flows: [] })),
        ]);
        dataLinkTypes.value = ltData.link_types || [];
        dataFlows.value = (flowData.flows || []);
        tabLoaded.value.data = true;
      } catch (e) {
        dataError.value = e.message || 'Failed to load data dependencies';
      } finally {
        dataLoading.value = false;
      }
    }

    // ==================================================================
    // TAB 3: External Packages
    // ==================================================================

    const ecosystems = computed(() => {
      const ecos = new Set();
      for (const dep of pkgDependencies.value) {
        if (dep.ecosystem) ecos.add(dep.ecosystem);
      }
      return Array.from(ecos).sort();
    });

    const ecosystemCounts = computed(() => {
      const counts = {};
      for (const dep of pkgDependencies.value) {
        const eco = dep.ecosystem || 'unknown';
        counts[eco] = (counts[eco] || 0) + 1;
      }
      return counts;
    });

    const filteredPackages = computed(() => {
      let result = pkgDependencies.value;

      if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase();
        result = result.filter(d => d.name.toLowerCase().includes(q));
      }

      if (activeEcosystem.value) {
        result = result.filter(d => d.ecosystem === activeEcosystem.value);
      }

      result = [...result].sort((a, b) => {
        switch (pkgSortBy.value) {
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
        pip: '#f59e0b', pypi: '#f59e0b', python: '#f59e0b',
        npm: '#ef4444', yarn: '#ef4444', node: '#ef4444',
        maven: '#3b82f6', gradle: '#3b82f6', java: '#3b82f6',
        go: '#06b6d4', golang: '#06b6d4',
        nuget: '#8b5cf6', cargo: '#f97316', rust: '#f97316',
        gem: '#ec4899', ruby: '#ec4899', composer: '#6366f1', php: '#6366f1',
      };
      return colors[(ecosystem || '').toLowerCase()] || '#6b7280';
    }

    async function toggleExpand(name) {
      if (expandedPkg.value === name) {
        expandedPkg.value = null;
        usageData.value = null;
        return;
      }
      expandedPkg.value = name;
      usageLoading.value = true;
      usageData.value = null;
      try {
        usageData.value = await api.dependencyUsage(name);
      } catch {
        usageData.value = null;
      } finally {
        usageLoading.value = false;
      }
    }

    async function fetchPackages() {
      pkgLoading.value = true;
      pkgError.value = null;
      try {
        pkgDependencies.value = await api.dependencies();
        tabLoaded.value.packages = true;
      } catch (e) {
        pkgError.value = e.message || 'Failed to load packages';
      } finally {
        pkgLoading.value = false;
      }
    }

    // ---- Init: load default tab + packages (for stats) ----
    onMounted(() => {
      fetchServiceDeps();
      fetchPackages();
    });

    return {
      router,
      activeTab, searchQuery, searchPlaceholder, tabs, switchTab,
      // Stats
      svcEdgeCount, dataLinkCount, pkgCount, ecosystemCount,
      // Tab 1
      svcLoading, svcError, filteredSvcDeps, fetchServiceDeps,
      // Tab 2
      dataLoading, dataError, dataLinkTypes, dataFlows,
      activeCardinality, cardinalityCounts,
      filteredDataDeps, filteredFlows, fetchDataDeps,
      // Tab 3
      pkgLoading, pkgError, pkgDependencies, pkgSortBy, pkgSortOptions,
      activeEcosystem, ecosystems, ecosystemCounts,
      filteredPackages, expandedPkg, usageLoading, usageData,
      ecosystemColor, toggleExpand, fetchPackages,
    };
  },
};
