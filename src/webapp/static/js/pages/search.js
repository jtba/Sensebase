// ============================================================
// SenseBase - Search Page
// ============================================================
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { api } from '../api.js';

export default {
  name: 'SearchPage',
  template: `
    <div class="p-6 max-w-7xl mx-auto space-y-6">
      <!-- Search Header -->
      <div class="space-y-4">
        <div class="relative">
          <div class="absolute inset-y-0 left-4 flex items-center pointer-events-none">
            <svg class="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
          <input
            ref="searchInput"
            v-model="query"
            @keydown.enter="doSearch"
            @keydown.escape="clearSearch"
            type="text"
            placeholder="Search schemas, services, APIs, dependencies..."
            class="search-input w-full pl-12 pr-32 py-4 text-lg"
          />
          <div class="absolute inset-y-0 right-3 flex items-center gap-2">
            <button v-if="query" @click="clearSearch"
                    class="text-gray-500 hover:text-gray-300 p-1 transition-colors">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
            <button @click="doSearch"
                    class="bg-accent-blue hover:bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium transition-colors">
              Search
            </button>
          </div>
        </div>

        <!-- Mode Tabs -->
        <div class="flex items-center gap-1 bg-surface/50 rounded-xl p-1 w-fit">
          <button v-for="m in modes" :key="m.key"
                  @click="mode = m.key"
                  class="px-4 py-2 rounded-lg text-sm font-medium transition-all-200"
                  :class="mode === m.key
                    ? 'bg-accent-blue/15 text-accent-blue border border-accent-blue/30'
                    : 'text-gray-400 hover:text-gray-200 border border-transparent'">
            {{ m.label }}
          </button>
        </div>

        <!-- Filters -->
        <div class="flex flex-wrap items-center gap-3">
          <div class="flex flex-wrap gap-2">
            <button v-for="f in typeFilters" :key="f.value"
                    @click="typeFilter = f.value"
                    class="filter-chip"
                    :class="typeFilter === f.value ? 'filter-chip-active' : ''">
              {{ f.label }}
            </button>
          </div>
          <div class="h-6 w-px bg-border mx-1"></div>
          <select v-model="repoFilter"
                  class="search-input text-sm py-1.5 px-3 rounded-lg min-w-[140px]">
            <option value="">All Repos</option>
            <option v-for="r in availableRepos" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>
      </div>

      <!-- Results Meta -->
      <div v-if="hasSearched && !loading" class="flex items-center justify-between text-sm text-gray-500">
        <span>
          <span v-if="results.length > 0">
            {{ results.length }} result{{ results.length !== 1 ? 's' : '' }}
            <span v-if="searchTime"> in {{ searchTime }}ms</span>
          </span>
          <span v-else>No results found</span>
        </span>
        <span v-if="query" class="text-xs">
          Mode: <span class="text-gray-400 font-medium">{{ currentModeLabel }}</span>
        </span>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="space-y-4">
        <div v-for="n in 5" :key="n" class="glass-card p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="skeleton h-6 w-16 rounded-full"></div>
            <div class="skeleton h-5 w-48"></div>
          </div>
          <div class="skeleton h-4 w-full mb-2"></div>
          <div class="skeleton h-4 w-3/4"></div>
        </div>
      </div>

      <!-- Ask Mode Results -->
      <div v-else-if="mode === 'ask' && askResult" class="space-y-4">
        <div class="glass-card p-6">
          <div class="flex items-start gap-3 mb-4">
            <div class="w-8 h-8 rounded-lg bg-accent-purple/10 flex items-center justify-center flex-shrink-0 mt-0.5">
              <svg class="w-4 h-4 text-accent-purple" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div>
              <h3 class="font-semibold text-lg mb-1">{{ query }}</h3>
              <p class="text-sm text-gray-400">Answered using knowledge base context</p>
            </div>
          </div>

          <!-- Context -->
          <div v-if="askResult.context" class="mb-4">
            <h4 class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2">Context</h4>
            <div class="code-block whitespace-pre-wrap text-sm">{{ askResult.context }}</div>
          </div>

          <!-- Sources -->
          <div v-if="askResult.sources && askResult.sources.length > 0">
            <h4 class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2">Sources</h4>
            <div class="space-y-2">
              <router-link v-for="(src, idx) in askResult.sources" :key="idx"
                           :to="getSourceRoute(src)"
                           class="flex items-center gap-2 p-2 rounded-lg hover:bg-surface-light/30 transition-all-200 group">
                <span class="badge" :class="'badge-' + (src.type || 'schema')">{{ src.type || 'result' }}</span>
                <span class="font-medium group-hover:text-accent-blue transition-colors">{{ src.name || src.source || 'Unknown' }}</span>
                <span v-if="src.repo" class="text-xs text-gray-500 font-mono">{{ src.repo }}</span>
              </router-link>
            </div>
          </div>
        </div>
      </div>

      <!-- Search Results -->
      <div v-else-if="results.length > 0" class="space-y-3">
        <div v-for="(result, idx) in results" :key="idx"
             class="glass-card glass-card-interactive p-5 cursor-pointer"
             @click="navigateToResult(result)"
             @keydown.enter="navigateToResult(result)"
             :tabindex="0"
             :class="{ 'ring-1 ring-accent-blue/30': selectedIndex === idx }">
          <div class="flex items-start justify-between mb-2">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="badge" :class="'badge-' + (result.type || 'schema')">{{ result.type || 'result' }}</span>
              <span class="font-semibold text-lg" v-html="highlightMatch(result.name || result.title || 'Unnamed', query)"></span>
            </div>
            <div v-if="result.score != null" class="flex items-center gap-2 flex-shrink-0 ml-4">
              <div class="score-bar w-16">
                <div class="score-bar-fill" :style="{ width: Math.round(result.score * 100) + '%' }"></div>
              </div>
              <span class="text-xs text-gray-500 font-mono">{{ (result.score * 100).toFixed(0) }}%</span>
            </div>
          </div>

          <!-- Result Details -->
          <div v-if="result.description || result.preview" class="text-sm text-gray-400 mb-2"
               v-html="highlightMatch(result.description || result.preview || '', query)">
          </div>

          <div class="flex items-center gap-3 text-xs text-gray-500">
            <span v-if="result.repo" class="flex items-center gap-1">
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
              </svg>
              {{ result.repo }}
            </span>
            <span v-if="result.source_file || result.file" class="font-mono flex items-center gap-1">
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
              </svg>
              {{ result.source_file || result.file }}
            </span>
            <span v-if="result.method" class="font-mono font-bold" :class="'http-' + result.method.toLowerCase()">
              {{ result.method }}
            </span>
            <span v-if="result.path" class="font-mono">{{ result.path }}</span>
          </div>
        </div>
      </div>

      <!-- No Results -->
      <div v-else-if="hasSearched && !loading" class="text-center py-16">
        <svg class="w-16 h-16 text-gray-600 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <h3 class="text-xl font-semibold text-gray-400 mb-2">No results found</h3>
        <p class="text-gray-500 mb-4">Try adjusting your search terms or filters</p>
        <div class="flex flex-wrap justify-center gap-2">
          <button v-for="suggestion in suggestions" :key="suggestion"
                  @click="query = suggestion; doSearch()"
                  class="filter-chip hover:filter-chip-active">
            {{ suggestion }}
          </button>
        </div>
      </div>

      <!-- Initial State -->
      <div v-else-if="!hasSearched" class="text-center py-16">
        <svg class="w-16 h-16 text-gray-600 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <h3 class="text-xl font-semibold text-gray-400 mb-2">Search your knowledge base</h3>
        <p class="text-gray-500">Find schemas, services, APIs, and more across all analyzed repositories</p>
      </div>

      <!-- Error -->
      <div v-if="error" class="glass-card p-5 border-red-500/30">
        <div class="flex items-center gap-2 text-red-400">
          <svg class="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          <span class="text-sm">{{ error }}</span>
        </div>
      </div>
    </div>
  `,
  setup() {
    const router = useRouter();
    const route = useRoute();

    const searchInput = ref(null);
    const query = ref('');
    const mode = ref('keyword');
    const typeFilter = ref('');
    const repoFilter = ref('');
    const results = ref([]);
    const askResult = ref(null);
    const loading = ref(false);
    const error = ref(null);
    const hasSearched = ref(false);
    const searchTime = ref(null);
    const selectedIndex = ref(-1);
    const availableRepos = ref([]);

    const modes = [
      { key: 'keyword', label: 'Keyword' },
      { key: 'semantic', label: 'Semantic' },
      { key: 'ask', label: 'Ask' },
    ];

    const typeFilters = [
      { value: '', label: 'All' },
      { value: 'schema', label: 'Schema' },
      { value: 'api', label: 'API' },
      { value: 'service', label: 'Service' },
      { value: 'dependency', label: 'Dependency' },
    ];

    const suggestions = ['user schema', 'authentication', 'REST API', 'database', 'payment'];

    const currentModeLabel = computed(() => {
      return modes.find(m => m.key === mode.value)?.label || '';
    });

    async function doSearch() {
      const q = query.value.trim();
      if (!q) return;

      loading.value = true;
      error.value = null;
      hasSearched.value = true;
      results.value = [];
      askResult.value = null;
      selectedIndex.value = -1;

      const startTime = performance.now();

      try {
        const opts = {
          limit: mode.value === 'ask' ? 5 : 20,
          type: typeFilter.value,
          repo: repoFilter.value,
        };

        if (mode.value === 'keyword') {
          const data = await api.search(q, opts);
          results.value = Array.isArray(data) ? data : (data.results || []);
        } else if (mode.value === 'semantic') {
          const data = await api.semanticSearch(q, opts);
          const raw = Array.isArray(data) ? data : (data.results || []);
          // Normalize: lift metadata fields to top level so the UI template can read them
          results.value = raw.map(r => ({
            ...r,
            type: r.type || (r.metadata && r.metadata.type) || '',
            name: r.name || (r.metadata && r.metadata.name) || '',
            repo: r.repo || (r.metadata && r.metadata.repo) || '',
            source_file: r.source_file || (r.metadata && r.metadata.path) || '',
            method: r.method || (r.metadata && r.metadata.method) || '',
            preview: r.text ? r.text.substring(0, 200) : '',
          }));
        } else if (mode.value === 'ask') {
          askResult.value = await api.ask(q, opts.limit);
        }

        searchTime.value = Math.round(performance.now() - startTime);
      } catch (err) {
        error.value = err.message;
        console.error('Search error:', err);
      } finally {
        loading.value = false;
      }

      // Update URL
      router.replace({ query: { q, mode: mode.value !== 'keyword' ? mode.value : undefined } });
    }

    function clearSearch() {
      query.value = '';
      results.value = [];
      askResult.value = null;
      hasSearched.value = false;
      error.value = null;
      nextTick(() => searchInput.value?.focus());
    }

    function highlightMatch(text, term) {
      if (!term || !text) return text;
      const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`(${escaped})`, 'gi');
      return String(text).replace(regex, '<span class="search-highlight">$1</span>');
    }

    function navigateToResult(result) {
      const type = result.type || '';
      const name = result.name || '';
      if (type === 'schema' && name) {
        router.push(`/schemas/${encodeURIComponent(name)}`);
      } else if (type === 'service' && name) {
        router.push(`/services/${encodeURIComponent(name)}`);
      } else if (type === 'api') {
        router.push('/apis');
      } else if (type === 'dependency') {
        router.push('/dependencies');
      } else {
        // fallback: search for this specific name
        query.value = name || result.title || '';
        doSearch();
      }
    }

    function getSourceRoute(src) {
      const type = src.type || '';
      const name = src.name || '';
      if (type === 'schema' && name) return `/schemas/${encodeURIComponent(name)}`;
      if (type === 'service' && name) return `/services/${encodeURIComponent(name)}`;
      if (type === 'api') return '/apis';
      return '/search';
    }

    // Load repos for filter dropdown
    async function loadRepos() {
      try {
        const data = await api.repos();
        availableRepos.value = (Array.isArray(data) ? data : []).map(r => r.name || r);
      } catch (e) {
        // Silently fail - repos filter is optional
      }
    }

    // Watch for route query changes
    watch(() => route.query, (newQuery) => {
      if (newQuery.q && newQuery.q !== query.value) {
        query.value = newQuery.q;
        if (newQuery.mode) mode.value = newQuery.mode;
        doSearch();
      }
    }, { immediate: false });

    // Keyboard navigation for results
    function handleKeydown(e) {
      if (e.key === 'ArrowDown' && results.value.length > 0) {
        e.preventDefault();
        selectedIndex.value = Math.min(selectedIndex.value + 1, results.value.length - 1);
      } else if (e.key === 'ArrowUp' && results.value.length > 0) {
        e.preventDefault();
        selectedIndex.value = Math.max(selectedIndex.value - 1, 0);
      } else if (e.key === 'Enter' && selectedIndex.value >= 0) {
        e.preventDefault();
        navigateToResult(results.value[selectedIndex.value]);
      }
    }

    onMounted(async () => {
      loadRepos();

      // Auto-search from query params
      if (route.query.q) {
        query.value = route.query.q;
        if (route.query.mode) mode.value = route.query.mode;
        await doSearch();
      }

      // Focus search input
      nextTick(() => searchInput.value?.focus());

      // Add keyboard listener
      window.addEventListener('keydown', handleKeydown);
    });

    return {
      searchInput, query, mode, typeFilter, repoFilter,
      results, askResult, loading, error, hasSearched,
      searchTime, selectedIndex, availableRepos,
      modes, typeFilters, suggestions, currentModeLabel,
      doSearch, clearSearch, highlightMatch,
      navigateToResult, getSourceRoute,
    };
  }
};
