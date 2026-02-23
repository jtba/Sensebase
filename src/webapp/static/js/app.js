// ============================================================
// SenseBase - Main Application
// ============================================================
import { createApp, ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { createRouter, createWebHashHistory, useRouter, useRoute } from 'vue-router';
import { api } from './api.js';

// Import page components
import Dashboard from './pages/dashboard.js';
import Search from './pages/search.js';
import GraphPage from './pages/graph.js';
import Schemas from './pages/schemas.js';
import Services from './pages/services.js';
import Apis from './pages/apis.js';
import Dependencies from './pages/dependencies.js';
import DataFlows from './pages/dataflows.js';
import Crawl from './pages/crawl.js';
import Contexts from './pages/contexts.js';
import Relationships from './pages/relationships.js';
import Settings from './pages/settings.js';
import Sources from './pages/sources.js';

// ---- Router ----
const routes = [
  { path: '/', component: Dashboard, meta: { title: 'Dashboard' } },
  { path: '/search', component: Search, meta: { title: 'Search' } },
  { path: '/graph', component: GraphPage, meta: { title: 'Knowledge Graph' } },
  { path: '/schemas', component: Schemas, meta: { title: 'Schema Explorer' } },
  { path: '/schemas/:name', component: Schemas, meta: { title: 'Schema Detail' } },
  { path: '/services', component: Services, meta: { title: 'Service Catalog' } },
  { path: '/services/:name', component: Services, meta: { title: 'Service Detail' } },
  { path: '/apis', component: Apis, meta: { title: 'API Explorer' } },
  { path: '/dependencies', component: Dependencies, meta: { title: 'Dependencies' } },
  { path: '/data-flows', component: DataFlows, meta: { title: 'Data Flows' } },
  { path: '/contexts', component: Contexts, meta: { title: 'Service Contexts' } },
  { path: '/contexts/:name', component: Contexts, meta: { title: 'Context Detail' } },
  { path: '/relationships', component: Relationships, meta: { title: 'Relationships' } },
  { path: '/crawl', component: Crawl, meta: { title: 'Pipeline' } },
  { path: '/settings', component: Settings, meta: { title: 'System Configuration' } },
  { path: '/sources', component: Sources, meta: { title: 'Sources' } },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

// ---- SVG Icons (inline) ----
const icons = {
  brain: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="w-6 h-6">
    <circle cx="12" cy="8" r="2.5" stroke-width="1.5"/>
    <circle cx="7" cy="16" r="2.5" stroke-width="1.5"/>
    <circle cx="17" cy="16" r="2.5" stroke-width="1.5"/>
    <line x1="12" y1="8" x2="7" y2="16" stroke-width="1.2" opacity="0.6"/>
    <line x1="12" y1="8" x2="17" y2="16" stroke-width="1.2" opacity="0.6"/>
    <line x1="7" y1="16" x2="17" y2="16" stroke-width="1.2" opacity="0.6"/>
  </svg>`,
  home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>`,
  search: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>`,
  graph: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><line x1="6" y1="8" x2="6" y2="16"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="18" y1="8" x2="18" y2="16"/><line x1="8" y1="18" x2="16" y2="18"/><line x1="7.5" y1="7.5" x2="16.5" y2="16.5" opacity="0.4"/></svg>`,
  database: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"/></svg>`,
  cube: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>`,
  bolt: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>`,
  package: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>`,
  flow: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"/></svg>`,
  sun: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>`,
  moon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>`,
  menu: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>`,
  close: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>`,
};

// ---- Root App Component ----
const App = {
  name: 'App',
  template: `
    <div class="min-h-screen dot-grid-bg">
      <!-- Mobile menu toggle -->
      <button
        @click="sidebarOpen = !sidebarOpen"
        class="sidebar-mobile-toggle fixed top-4 left-4 z-50 p-2 rounded-lg glass-card"
      >
        <span v-html="sidebarOpen ? icons.close : icons.menu"></span>
      </button>

      <!-- Sidebar overlay (mobile) -->
      <div
        v-if="sidebarOpen"
        class="sidebar-overlay fixed inset-0 bg-black/50 z-40"
        @click="sidebarOpen = false"
      ></div>

      <!-- Sidebar -->
      <aside
        class="sidebar-desktop fixed top-0 left-0 bottom-0 w-60 z-40 flex flex-col glass-card rounded-none border-r border-border"
        :class="{ 'sidebar-open': sidebarOpen }"
      >
        <!-- Brand -->
        <div class="px-5 py-5 border-b border-border/50">
          <router-link to="/" class="flex items-center gap-3 group" @click="sidebarOpen = false">
            <div class="text-accent-blue group-hover:text-accent-purple transition-colors" v-html="icons.brain"></div>
            <span class="text-lg font-bold gradient-text-blue-purple">SenseBase</span>
          </router-link>
        </div>

        <!-- Navigation -->
        <nav class="flex-1 py-3 px-3 overflow-y-auto">
          <div v-for="(section, si) in navSections" :key="section.label" :class="si > 0 ? 'mt-5' : ''">
            <div class="px-3 mb-2 flex items-center gap-2">
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-500/70">{{ section.label }}</span>
              <span class="flex-1 h-px bg-gradient-to-r from-border/40 to-transparent"></span>
            </div>
            <div class="space-y-0.5">
              <router-link
                v-for="item in section.items"
                :key="item.path"
                :to="item.path"
                class="nav-link flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-400"
                :class="{ 'nav-link-active': isActiveRoute(item.path) }"
                @click="sidebarOpen = false"
              >
                <span v-html="item.icon" class="flex-shrink-0 opacity-75"></span>
                <span>{{ item.label }}</span>
              </router-link>
            </div>
          </div>
        </nav>

        <!-- Bottom: Theme toggle + version -->
        <div class="px-4 py-4 border-t border-border/50 space-y-3">
          <button
            @click="toggleDarkMode"
            class="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 hover:bg-surface-light/30 transition-all-200"
          >
            <span v-html="darkMode ? icons.sun : icons.moon" class="opacity-75"></span>
            <span>{{ darkMode ? 'Light Mode' : 'Dark Mode' }}</span>
          </button>
          <div class="px-3 text-xs text-gray-600">
            SenseBase v1.0
          </div>
        </div>
      </aside>

      <!-- Main Content -->
      <main class="main-content ml-0 md:ml-60 min-h-screen">
        <!-- Top Bar -->
        <header class="sticky top-0 z-30 backdrop-blur-xl bg-surface-dark/80 border-b border-border/50">
          <div class="flex items-center justify-between px-6 py-3">
            <!-- Page title -->
            <h1 class="text-lg font-semibold text-gray-200 hidden md:block">
              {{ currentPageTitle }}
            </h1>
            <div class="md:hidden w-8"></div>

            <!-- Right: Global search + health -->
            <div class="flex items-center gap-4">
              <!-- Global search -->
              <div class="relative">
                <div class="absolute inset-y-0 left-3 flex items-center pointer-events-none">
                  <svg class="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                  </svg>
                </div>
                <input
                  ref="globalSearchInput"
                  v-model="globalSearch"
                  @keydown.enter="doGlobalSearch"
                  @keydown.escape="blurGlobalSearch"
                  type="text"
                  placeholder="Search... (Ctrl+K)"
                  class="search-input pl-9 pr-3 py-1.5 text-sm w-48 lg:w-64"
                />
              </div>

              <!-- Crawl status indicator -->
              <router-link v-if="crawlStatus.status === 'running'" to="/crawl" class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent-blue/10 border border-accent-blue/30 text-accent-blue text-xs font-medium hover:bg-accent-blue/20 transition-all-200">
                <svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                {{ crawlStatus.current_stage }}
              </router-link>
              <router-link v-else-if="crawlStatus.status === 'completed'" to="/crawl" class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 text-xs font-medium hover:bg-green-500/20 transition-all-200">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
                Complete
              </router-link>
              <router-link v-else-if="crawlStatus.status === 'failed'" to="/crawl" class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-medium hover:bg-red-500/20 transition-all-200">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
                Failed
              </router-link>

              <!-- Health indicator -->
              <div class="flex items-center gap-2">
                <span
                  class="status-dot"
                  :class="healthOk ? 'status-dot-green' : 'status-dot-yellow'"
                  :title="healthOk ? 'System healthy' : 'Checking health...'"
                ></span>
                <span class="text-xs text-gray-500 hidden lg:inline">{{ healthOk ? 'Healthy' : 'Checking...' }}</span>
              </div>
            </div>
          </div>
        </header>

        <!-- Page content -->
        <router-view></router-view>
      </main>
    </div>
  `,
  setup() {
    const routerInstance = useRouter();
    const route = useRoute();

    // ---- Dark Mode ----
    const darkMode = ref(true);

    // Restore from localStorage
    const stored = localStorage.getItem('sensebase-dark-mode');
    if (stored !== null) {
      darkMode.value = stored === 'true';
    }

    function applyDarkMode(isDark) {
      if (isDark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }

    function toggleDarkMode() {
      darkMode.value = !darkMode.value;
      localStorage.setItem('sensebase-dark-mode', String(darkMode.value));
      applyDarkMode(darkMode.value);
    }

    // Apply on mount
    applyDarkMode(darkMode.value);

    watch(darkMode, (val) => applyDarkMode(val));

    // ---- Sidebar ----
    const sidebarOpen = ref(false);

    const navSections = [
      {
        label: 'Overview',
        items: [
          { path: '/', label: 'Dashboard', icon: icons.home },
        ],
      },
      {
        label: 'Explore & Discover',
        items: [
          { path: '/search', label: 'Search', icon: icons.search },
          { path: '/graph', label: 'Graph Explorer', icon: icons.graph },
          { path: '/apis', label: 'API Console', icon: icons.bolt },
          { path: '/contexts', label: 'Contexts', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/></svg>` },
          { path: '/relationships', label: 'Relationships', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"/></svg>` },
        ],
      },
      {
        label: 'Modeling',
        items: [
          { path: '/schemas', label: 'Schemas', icon: icons.database },
          { path: '/services', label: 'Service Catalog', icon: icons.cube },
          { path: '/dependencies', label: 'Dependency Map', icon: icons.package },
          { path: '/data-flows', label: 'Data Flows', icon: icons.flow },
        ],
      },
      {
        label: 'Administration',
        items: [
          { path: '/sources', label: 'Sources', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"/></svg>` },
          { path: '/crawl', label: 'Pipelines', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>` },
          { path: '/settings', label: 'System Configuration', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>` },
        ],
      },
    ];

    function isActiveRoute(path) {
      if (path === '/') return route.path === '/';
      return route.path.startsWith(path);
    }

    // ---- Page title ----
    const currentPageTitle = computed(() => {
      return route.meta?.title || 'SenseBase';
    });

    // ---- Global Search ----
    const globalSearchInput = ref(null);
    const globalSearch = ref('');

    function doGlobalSearch() {
      if (globalSearch.value.trim()) {
        routerInstance.push({ path: '/search', query: { q: globalSearch.value.trim() } });
        globalSearch.value = '';
        globalSearchInput.value?.blur();
      }
    }

    function blurGlobalSearch() {
      globalSearchInput.value?.blur();
    }

    // Keyboard shortcut: Ctrl/Cmd + K
    function handleGlobalKeydown(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        globalSearchInput.value?.focus();
      }
      if (e.key === 'Escape' && document.activeElement === globalSearchInput.value) {
        globalSearchInput.value?.blur();
      }
    }

    // ---- Health ----
    const healthOk = ref(false);

    async function checkHealth() {
      try {
        const data = await api.health();
        healthOk.value = data && (data.status === 'healthy' || data.keyword_search);
      } catch {
        healthOk.value = false;
      }
    }

    // ---- Crawl Status ----
    const crawlStatus = ref({ status: 'idle' });

    async function checkCrawlStatus() {
      try {
        const data = await api.crawlStatus();
        crawlStatus.value = data;
      } catch {
        // silently ignore
      }
    }

    // ---- Lifecycle ----
    let healthInterval = null;
    let crawlInterval = null;

    onMounted(() => {
      checkHealth();
      healthInterval = setInterval(checkHealth, 30000);
      checkCrawlStatus();
      crawlInterval = setInterval(checkCrawlStatus, 3000);
      window.addEventListener('keydown', handleGlobalKeydown);
    });

    onUnmounted(() => {
      if (healthInterval) clearInterval(healthInterval);
      if (crawlInterval) clearInterval(crawlInterval);
      window.removeEventListener('keydown', handleGlobalKeydown);
    });

    return {
      darkMode, toggleDarkMode,
      sidebarOpen, navSections, isActiveRoute,
      currentPageTitle,
      globalSearchInput, globalSearch, doGlobalSearch, blurGlobalSearch,
      healthOk,
      crawlStatus,
      icons,
    };
  }
};

// ---- Create & Mount ----
const app = createApp(App);
app.use(router);
app.mount('#app');
