// ============================================================
// SenseBase - Relationships Page
// ============================================================
import { ref, computed, onMounted } from 'vue';
import { api } from '../api.js';

export default {
  name: 'Relationships',
  template: `
    <div class="p-6 max-w-7xl mx-auto space-y-8">
      <!-- Header -->
      <div class="text-center py-4">
        <h1 class="text-4xl font-bold mb-2">
          <span class="gradient-text">Service Relationships</span>
        </h1>
        <p class="text-gray-400 text-lg">Cross-service dependencies, data routing, and common workflows</p>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="space-y-6">
        <div v-for="n in 3" :key="n" class="glass-card p-6 space-y-3">
          <div class="skeleton h-6 w-1/3"></div>
          <div class="skeleton h-4 w-full"></div>
          <div class="skeleton h-4 w-3/4"></div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else-if="isEmpty" class="text-center py-16">
        <svg class="w-16 h-16 text-gray-600 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"/>
        </svg>
        <p class="text-gray-400 text-lg mb-2">No relationships generated yet</p>
        <p class="text-gray-500 text-sm">Run the pipeline with LLM extraction on multiple repos to generate cross-service relationships.</p>
        <router-link to="/crawl" class="inline-block mt-4 px-4 py-2 rounded-lg bg-accent-blue/10 border border-accent-blue/30 text-accent-blue text-sm hover:bg-accent-blue/20 transition-all">
          Go to Pipeline
        </router-link>
      </div>

      <!-- Tabs -->
      <div v-else>
        <div class="flex gap-1 mb-6 bg-surface-dark/50 rounded-lg p-1 w-fit">
          <button v-for="tab in tabs" :key="tab.key"
                  @click="activeTab = tab.key"
                  class="px-4 py-2 rounded-md text-sm font-medium transition-all-200"
                  :class="activeTab === tab.key
                    ? 'bg-accent-blue/20 text-accent-blue border border-accent-blue/30'
                    : 'text-gray-400 hover:text-gray-200'">
            {{ tab.label }}
            <span class="ml-1.5 text-xs opacity-60">{{ tab.count }}</span>
          </button>
        </div>

        <!-- Service Map Tab -->
        <div v-if="activeTab === 'services'" class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div v-for="svc in serviceMap" :key="svc.service" class="glass-card p-6">
            <div class="flex items-start justify-between mb-3">
              <h3 class="text-lg font-semibold text-accent-blue">{{ svc.service }}</h3>
              <span v-if="svc.domain" class="badge badge-schema text-xs">{{ svc.domain }}</span>
            </div>
            <p class="text-sm text-gray-400 mb-4">{{ svc.purpose }}</p>

            <div v-if="svc.data_owned && svc.data_owned.length" class="mb-4">
              <h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Data Owned</h4>
              <div class="flex flex-wrap gap-1.5">
                <span v-for="d in svc.data_owned" :key="d"
                      class="px-2 py-1 text-xs rounded-md bg-accent-teal/10 text-accent-teal border border-accent-teal/20">
                  {{ d }}
                </span>
              </div>
            </div>

            <div v-if="svc.use_when && svc.use_when.length" class="mb-4">
              <h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Use When</h4>
              <ul class="space-y-1">
                <li v-for="(cond, i) in svc.use_when" :key="i" class="flex items-start gap-2 text-sm text-gray-400">
                  <svg class="w-3 h-3 text-green-400 mt-1 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
                  </svg>
                  {{ cond }}
                </li>
              </ul>
            </div>

            <div v-if="svc.instead_of && svc.instead_of.length">
              <h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Instead Of</h4>
              <div v-for="alt in svc.instead_of" :key="alt.service" class="flex items-start gap-2 text-sm text-gray-400 mb-1">
                <span class="text-accent-amber font-medium">{{ alt.service }}:</span>
                <span>{{ alt.reason }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Data Routing Tab -->
        <div v-if="activeTab === 'data'" class="space-y-4">
          <div class="glass-card overflow-hidden">
            <div class="overflow-x-auto">
              <table class="w-full">
                <thead>
                  <tr class="border-b border-border">
                    <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-3">Entity</th>
                    <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-3">Source of Truth</th>
                    <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-3">Also In</th>
                    <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-3">Query When</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="route in dataRouting" :key="route.entity" class="border-b border-border/50 hover:bg-surface-light/30 transition-colors">
                    <td class="px-6 py-4">
                      <span class="font-medium text-accent-blue">{{ route.entity }}</span>
                    </td>
                    <td class="px-6 py-4">
                      <span class="px-2 py-1 text-xs rounded-md bg-green-500/10 text-green-400 border border-green-500/20">
                        {{ route.source_of_truth }}
                      </span>
                    </td>
                    <td class="px-6 py-4">
                      <div v-if="route.also_available_in && route.also_available_in.length" class="space-y-1">
                        <div v-for="alt in route.also_available_in" :key="alt.service" class="flex items-center gap-2 text-xs">
                          <span class="text-gray-300">{{ alt.service }}</span>
                          <span class="px-1.5 py-0.5 rounded text-xs"
                                :class="alt.freshness === 'real-time' ? 'bg-green-500/10 text-green-400' : alt.freshness === 'cached' ? 'bg-yellow-500/10 text-yellow-400' : 'bg-orange-500/10 text-orange-400'">
                            {{ alt.freshness || 'unknown' }}
                          </span>
                        </div>
                      </div>
                      <span v-else class="text-gray-600 text-xs">&mdash;</span>
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-400">{{ route.query_this_when || '&mdash;' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Service Chains Tab -->
        <div v-if="activeTab === 'chains'" class="space-y-6">
          <div v-for="chain in serviceChains" :key="chain.name" class="glass-card p-6">
            <h3 class="text-lg font-semibold text-accent-purple mb-2">{{ chain.name }}</h3>
            <p class="text-sm text-gray-400 mb-6">{{ chain.description }}</p>

            <div class="space-y-4">
              <div v-for="(step, i) in chain.steps" :key="i" class="flex items-start gap-4">
                <!-- Step number -->
                <div class="flex-shrink-0 w-8 h-8 rounded-full border-2 flex items-center justify-center text-xs font-bold"
                     :class="i === chain.steps.length - 1 ? 'border-green-400 text-green-400 bg-green-400/10' : 'border-accent-blue text-accent-blue bg-accent-blue/10'">
                  {{ i + 1 }}
                </div>
                <!-- Content -->
                <div class="flex-1 pt-1">
                  <div class="flex items-center gap-2 mb-1">
                    <span class="font-medium text-accent-blue">{{ step.service }}</span>
                    <svg v-if="i < chain.steps.length - 1" class="w-4 h-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
                    </svg>
                  </div>
                  <p class="text-sm text-gray-400">{{ step.action }}</p>
                  <p v-if="step.data_passed" class="text-xs text-gray-600 mt-1">
                    Data: <span class="text-gray-500">{{ step.data_passed }}</span>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const loading = ref(true);
    const data = ref({});
    const activeTab = ref('services');

    const serviceMap = computed(() => data.value.service_map || []);
    const dataRouting = computed(() => data.value.data_routing || []);
    const serviceChains = computed(() => data.value.service_chains || []);

    const isEmpty = computed(() =>
      serviceMap.value.length === 0 &&
      dataRouting.value.length === 0 &&
      serviceChains.value.length === 0
    );

    const tabs = computed(() => [
      { key: 'services', label: 'Service Map', count: serviceMap.value.length },
      { key: 'data', label: 'Data Routing', count: dataRouting.value.length },
      { key: 'chains', label: 'Service Chains', count: serviceChains.value.length },
    ]);

    async function loadRelationships() {
      loading.value = true;
      try {
        data.value = await api.relationships();
      } catch (err) {
        console.error('Failed to load relationships:', err);
        data.value = {};
      } finally {
        loading.value = false;
      }
    }

    onMounted(loadRelationships);

    return {
      loading, activeTab, serviceMap, dataRouting, serviceChains,
      isEmpty, tabs,
    };
  },
};
