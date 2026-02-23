// ============================================================
// SenseBase - Dashboard Page
// ============================================================
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../api.js';

export default {
  name: 'Dashboard',
  template: `
    <div class="p-6 max-w-7xl mx-auto space-y-8">
      <!-- Hero / Quick Search -->
      <div class="text-center py-8">
        <h1 class="text-4xl font-bold mb-2">
          <span class="gradient-text">Knowledge Explorer</span>
        </h1>
        <p class="text-gray-400 mb-8 text-lg">Search across schemas, services, APIs, and dependencies</p>
        <div class="max-w-2xl mx-auto relative">
          <div class="absolute inset-y-0 left-4 flex items-center pointer-events-none">
            <svg class="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
          <input
            v-model="searchQuery"
            @keydown.enter="doSearch"
            type="text"
            placeholder="Search your knowledge base... (Ctrl+K)"
            class="search-input w-full pl-12 pr-4 py-4 text-lg"
          />
        </div>
      </div>

      <!-- Stat Cards -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <div v-for="(stat, i) in statCards" :key="stat.label"
             class="glass-card glass-card-interactive p-5"
             :class="stat.borderClass">
          <div class="flex items-center justify-between mb-3">
            <div class="w-10 h-10 rounded-lg flex items-center justify-center"
                 :class="stat.iconBg">
              <div v-html="stat.icon" class="w-5 h-5"></div>
            </div>
          </div>
          <div v-if="loading" class="space-y-2">
            <div class="skeleton h-8 w-16"></div>
            <div class="skeleton h-4 w-24"></div>
          </div>
          <div v-else>
            <div class="text-3xl font-bold count-up" :class="stat.textColor">
              {{ animatedStats[stat.key] ?? 0 }}
            </div>
            <div class="text-sm text-gray-400 mt-1">{{ stat.label }}</div>
          </div>
        </div>
      </div>

      <!-- Health Status -->
      <div class="glass-card p-5">
        <h2 class="text-lg font-semibold mb-4 flex items-center gap-2">
          <svg class="w-5 h-5 text-accent-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          System Health
        </h2>
        <div v-if="loading" class="flex gap-8">
          <div class="skeleton h-6 w-40"></div>
          <div class="skeleton h-6 w-40"></div>
        </div>
        <div v-else class="flex flex-wrap gap-8">
          <div class="flex items-center gap-2">
            <span class="status-dot" :class="health.keyword_search ? 'status-dot-green' : 'status-dot-red'"></span>
            <span class="text-sm">Keyword Search</span>
            <span class="text-xs text-gray-500">{{ health.keyword_search ? 'Available' : 'Unavailable' }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="status-dot" :class="health.semantic_search ? 'status-dot-green' : 'status-dot-red'"></span>
            <span class="text-sm">Semantic Search</span>
            <span class="text-xs text-gray-500">{{ health.semantic_search ? 'Available' : 'Unavailable' }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="status-dot status-dot-green"></span>
            <span class="text-sm">API Server</span>
            <span class="text-xs text-gray-500">Running</span>
          </div>
        </div>
      </div>

      <!-- Two Column: Highlights + Repos -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Highlights -->
        <div class="space-y-6">
          <!-- API Methods Bar Chart -->
          <div class="glass-card p-5">
            <h2 class="text-lg font-semibold mb-4 flex items-center gap-2">
              <svg class="w-5 h-5 text-accent-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
              </svg>
              API Endpoints by Method
            </h2>
            <div v-if="loading" class="space-y-3">
              <div v-for="n in 4" :key="n" class="skeleton h-6 w-full"></div>
            </div>
            <div v-else-if="methodCounts.length > 0" class="space-y-3">
              <div v-for="m in methodCounts" :key="m.method" class="flex items-center gap-3">
                <span class="font-mono text-xs font-bold w-16 text-right"
                      :class="'http-' + m.method.toLowerCase()">
                  {{ m.method }}
                </span>
                <div class="flex-1 bg-surface-dark rounded-full h-5 overflow-hidden">
                  <div class="method-bar h-full rounded-full flex items-center justify-end pr-2"
                       :style="{ width: m.pct + '%', background: m.color }">
                    <span v-if="m.pct > 15" class="text-xs font-semibold text-white/90">{{ m.count }}</span>
                  </div>
                </div>
                <span v-if="m.pct <= 15" class="text-xs text-gray-400 w-8">{{ m.count }}</span>
              </div>
            </div>
            <div v-else class="text-gray-500 text-sm">No API data available</div>
          </div>

          <!-- Top Schemas -->
          <div class="glass-card p-5">
            <h2 class="text-lg font-semibold mb-4 flex items-center gap-2">
              <svg class="w-5 h-5 text-accent-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/>
              </svg>
              Top Schemas
            </h2>
            <div v-if="loading" class="space-y-2">
              <div v-for="n in 5" :key="n" class="skeleton h-8 w-full"></div>
            </div>
            <div v-else-if="topSchemas.length > 0" class="space-y-2">
              <router-link v-for="s in topSchemas" :key="s.name"
                           :to="'/schemas/' + encodeURIComponent(s.name)"
                           class="flex items-center justify-between p-2 rounded-lg hover:bg-surface-light/50 transition-all-200 group">
                <div class="flex items-center gap-2">
                  <span class="badge badge-schema">Schema</span>
                  <span class="font-medium group-hover:text-accent-blue transition-colors">{{ s.name }}</span>
                </div>
                <span class="text-xs text-gray-500">{{ s.field_count || 0 }} fields</span>
              </router-link>
            </div>
            <div v-else class="text-gray-500 text-sm">No schemas discovered yet</div>
          </div>
        </div>

        <!-- Repository Overview -->
        <div class="glass-card p-5">
          <h2 class="text-lg font-semibold mb-4 flex items-center gap-2">
            <svg class="w-5 h-5 text-accent-purple" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
            </svg>
            Repositories
          </h2>
          <div v-if="loading" class="space-y-3">
            <div v-for="n in 6" :key="n" class="skeleton h-16 w-full"></div>
          </div>
          <div v-else-if="repos.length > 0" class="space-y-2 max-h-[500px] overflow-y-auto">
            <div v-for="repo in repos" :key="repo.name"
                 class="p-3 rounded-lg border border-transparent hover:border-border-light hover:bg-surface-light/30 transition-all-200 cursor-pointer"
                 @click="filterByRepo(repo.name)">
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center">
                  <span class="font-medium text-sm">{{ repo.name }}</span>
                  <span v-if="repo.has_context" class="ml-2 px-1.5 py-0.5 text-xs rounded bg-accent-blue/10 text-accent-blue border border-accent-blue/20">context</span>
                </div>
                <svg class="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                </svg>
              </div>
              <p v-if="repo.purpose" class="text-xs text-gray-500 mb-2" style="display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden;">{{ repo.purpose }}</p>
              <div class="flex gap-3 text-xs text-gray-500">
                <span v-if="repo.schemas" class="flex items-center gap-1">
                  <span class="w-2 h-2 rounded-full bg-accent-blue"></span>
                  {{ repo.schemas }} schemas
                </span>
                <span v-if="repo.apis" class="flex items-center gap-1">
                  <span class="w-2 h-2 rounded-full bg-accent-teal"></span>
                  {{ repo.apis }} APIs
                </span>
                <span v-if="repo.services" class="flex items-center gap-1">
                  <span class="w-2 h-2 rounded-full bg-accent-purple"></span>
                  {{ repo.services }} services
                </span>
                <span v-if="repo.dependencies" class="flex items-center gap-1">
                  <span class="w-2 h-2 rounded-full bg-accent-amber"></span>
                  {{ repo.dependencies }} deps
                </span>
              </div>
            </div>
          </div>
          <div v-else class="text-gray-500 text-sm flex flex-col items-center py-8">
            <svg class="w-12 h-12 text-gray-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
            </svg>
            <p>No repositories analyzed yet.</p>
            <p class="text-xs mt-1">
              <router-link to="/crawl" class="text-accent-blue hover:underline">Run the pipeline</router-link> to get started.
            </p>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const router = useRouter();
    const loading = ref(true);
    const error = ref(null);
    const searchQuery = ref('');
    const stats = ref({});
    const animatedStats = ref({});
    const health = ref({ keyword_search: false, semantic_search: false });
    const repos = ref([]);
    const topSchemas = ref([]);
    const methodCounts = ref([]);

    const statCards = [
      {
        key: 'repos', label: 'Repositories', borderClass: 'stat-card-purple',
        iconBg: 'bg-accent-purple/10',
        textColor: 'text-accent-purple',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>'
      },
      {
        key: 'schemas', label: 'Schemas', borderClass: 'stat-card-blue',
        iconBg: 'bg-accent-blue/10',
        textColor: 'text-accent-blue',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/></svg>'
      },
      {
        key: 'apis', label: 'API Endpoints', borderClass: 'stat-card-teal',
        iconBg: 'bg-accent-teal/10',
        textColor: 'text-accent-teal',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="#14b8a6" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>'
      },
      {
        key: 'services', label: 'Services', borderClass: 'stat-card-purple',
        iconBg: 'bg-purple-500/10',
        textColor: 'text-purple-400',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>'
      },
      {
        key: 'dependencies', label: 'Dependencies', borderClass: 'stat-card-amber',
        iconBg: 'bg-accent-amber/10',
        textColor: 'text-accent-amber',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>'
      },
    ];

    function animateCount(key, target) {
      const duration = 600;
      const start = 0;
      const startTime = performance.now();
      function step(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        animatedStats.value[key] = Math.round(start + (target - start) * eased);
        if (progress < 1) {
          requestAnimationFrame(step);
        }
      }
      requestAnimationFrame(step);
    }

    const METHOD_COLORS = {
      GET: '#22c55e',
      POST: '#3b82f6',
      PUT: '#f59e0b',
      DELETE: '#ef4444',
      PATCH: '#8b5cf6',
    };

    async function loadData() {
      loading.value = true;
      try {
        const [statsData, healthData, reposData] = await Promise.allSettled([
          api.stats(),
          api.health(),
          api.repos(),
        ]);

        if (statsData.status === 'fulfilled') {
          stats.value = statsData.value;
          for (const card of statCards) {
            const val = statsData.value[card.key] ?? 0;
            animateCount(card.key, val);
          }
        }

        if (healthData.status === 'fulfilled') {
          health.value = healthData.value;
        }

        if (reposData.status === 'fulfilled') {
          repos.value = reposData.value?.repos || [];
        }

        // Fetch schemas and APIs for highlights
        const [schemasData, apisData] = await Promise.allSettled([
          api.schemas({ limit: 8 }),
          api.apis(),
        ]);

        if (schemasData.status === 'fulfilled') {
          const schemaList = schemasData.value;
          topSchemas.value = (Array.isArray(schemaList) ? schemaList : []).slice(0, 6);
        }

        if (apisData.status === 'fulfilled') {
          const apiList = apisData.value;
          if (Array.isArray(apiList)) {
            const counts = {};
            for (const a of apiList) {
              const method = (a.method || 'GET').toUpperCase();
              counts[method] = (counts[method] || 0) + 1;
            }
            const total = apiList.length || 1;
            methodCounts.value = Object.entries(counts)
              .map(([method, count]) => ({
                method,
                count,
                pct: Math.round((count / total) * 100),
                color: METHOD_COLORS[method] || '#64748b',
              }))
              .sort((a, b) => b.count - a.count);
          }
        }
      } catch (err) {
        error.value = err.message;
        console.error('Dashboard load error:', err);
      } finally {
        loading.value = false;
      }
    }

    function doSearch() {
      if (searchQuery.value.trim()) {
        router.push({ path: '/search', query: { q: searchQuery.value.trim() } });
      }
    }

    function filterByRepo(repoName) {
      router.push({ path: '/search', query: { q: '', repo: repoName } });
    }

    onMounted(loadData);

    return {
      loading, error, searchQuery, stats, animatedStats, health,
      repos, topSchemas, methodCounts, statCards,
      doSearch, filterByRepo,
    };
  }
};
