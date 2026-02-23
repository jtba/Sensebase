// ============================================================
// SenseBase - Sources Page
// ============================================================

import { ref, computed, onMounted } from 'vue';
import { api } from '../api.js';

const SOURCE_META = {
  github: {
    label: 'GitHub',
    color: 'text-gray-100',
    bg: 'bg-gray-100/10 border-gray-100/20',
    iconBg: 'bg-gray-100/10',
    icon: `<svg viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>`,
  },
  gitlab: {
    label: 'GitLab',
    color: 'text-orange-400',
    bg: 'bg-orange-500/10 border-orange-500/20',
    iconBg: 'bg-orange-500/10',
    icon: `<svg viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6"><path d="M22.65 14.39L12 22.13 1.35 14.39a.84.84 0 01-.3-.94l1.22-3.78 2.44-7.51A.42.42 0 014.82 2a.43.43 0 01.58 0 .42.42 0 01.11.18l2.44 7.49h8.1l2.44-7.51A.42.42 0 0118.6 2a.43.43 0 01.58 0 .42.42 0 01.11.18l2.44 7.51L23 13.45a.84.84 0 01-.35.94z"/></svg>`,
  },
  local: {
    label: 'Local Directories',
    color: 'text-accent-teal',
    bg: 'bg-accent-teal/10 border-accent-teal/20',
    iconBg: 'bg-accent-teal/10',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"/></svg>`,
  },
};

const ADD_SOURCE_TYPES = [
  { type: 'github', label: 'GitHub', desc: 'Connect to GitHub repositories via personal access token' },
  { type: 'gitlab', label: 'GitLab', desc: 'Connect to a self-hosted or cloud GitLab instance' },
  { type: 'local', label: 'Local Directories', desc: 'Scan local filesystem directories for repositories' },
];

export default {
  name: 'SourcesPage',
  template: `
    <div class="p-6 max-w-4xl mx-auto space-y-8">

      <!-- Header -->
      <div class="flex items-end justify-between">
        <div>
          <h1 class="text-2xl font-bold gradient-text mb-1">Sources</h1>
          <p class="text-gray-500 text-sm">Manage where SenseBase discovers and crawls repositories</p>
        </div>
        <button
          v-if="!addingType"
          @click="showAddPicker = !showAddPicker"
          class="relative flex items-center gap-2 px-4 py-2 text-sm font-medium bg-accent-purple/15 text-accent-purple rounded-lg hover:bg-accent-purple/25 transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
          Add Source
        </button>
      </div>

      <!-- Add source picker dropdown -->
      <div v-if="showAddPicker && !addingType" class="glass-card p-4 border border-accent-purple/20">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">Choose a source type</h3>
        <div class="grid gap-3 sm:grid-cols-3">
          <button
            v-for="opt in addableTypes"
            :key="opt.type"
            @click="startAdd(opt.type)"
            class="p-4 rounded-lg border border-border/50 hover:border-accent-purple/40 bg-surface/40 hover:bg-surface/70 text-left transition-all group"
          >
            <div class="flex items-center gap-3 mb-2">
              <div class="flex-shrink-0" :class="meta[opt.type].color" v-html="meta[opt.type].icon"></div>
              <span class="text-sm font-semibold text-gray-200 group-hover:text-gray-100">{{ opt.label }}</span>
            </div>
            <p class="text-xs text-gray-500">{{ opt.desc }}</p>
          </button>
        </div>
        <div v-if="addableTypes.length === 0" class="text-sm text-gray-500 text-center py-2">
          All source types are already configured.
        </div>
        <button @click="showAddPicker = false" class="mt-3 text-xs text-gray-500 hover:text-gray-300 transition-colors">Cancel</button>
      </div>

      <!-- Add/Edit form -->
      <div v-if="addingType" class="glass-card p-6 border border-accent-purple/20">
        <div class="flex items-center gap-3 mb-5">
          <div :class="meta[addingType].color" v-html="meta[addingType].icon"></div>
          <h2 class="text-lg font-semibold text-gray-200">{{ editingExisting ? 'Edit' : 'Add' }} {{ meta[addingType].label }}</h2>
        </div>

        <!-- GitHub form -->
        <div v-if="addingType === 'github'" class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-1.5">Personal Access Token</label>
            <input
              v-model="form.token"
              type="password"
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
              class="search-input w-full px-3 py-2 text-sm font-mono"
            />
            <p class="text-xs text-gray-600 mt-1">Create at Settings > Developer settings > Personal access tokens (needs repo scope)</p>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-1.5">Organizations <span class="text-gray-600">(optional, one per line)</span></label>
            <textarea
              v-model="form.orgsText"
              placeholder="my-org&#10;another-org"
              rows="3"
              class="search-input w-full px-3 py-2 text-sm font-mono resize-y"
            ></textarea>
            <p class="text-xs text-gray-600 mt-1">Leave empty to crawl all accessible repositories</p>
          </div>
        </div>

        <!-- GitLab form -->
        <div v-if="addingType === 'gitlab'" class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-1.5">GitLab URL</label>
            <input
              v-model="form.url"
              type="text"
              placeholder="https://gitlab.yourcompany.com"
              class="search-input w-full px-3 py-2 text-sm font-mono"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-1.5">Personal Access Token</label>
            <input
              v-model="form.token"
              type="password"
              placeholder="glpat-xxxxxxxxxxxxxxxxxxxx"
              class="search-input w-full px-3 py-2 text-sm font-mono"
            />
            <p class="text-xs text-gray-600 mt-1">Create at Settings > Access Tokens (needs api scope)</p>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-1.5">Namespaces <span class="text-gray-600">(optional, one per line)</span></label>
            <textarea
              v-model="form.namespacesText"
              placeholder="group-name&#10;group/subgroup"
              rows="3"
              class="search-input w-full px-3 py-2 text-sm font-mono resize-y"
            ></textarea>
            <p class="text-xs text-gray-600 mt-1">Leave empty to crawl all accessible repositories</p>
          </div>
        </div>

        <!-- Local form -->
        <div v-if="addingType === 'local'" class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-1.5">Directories <span class="text-gray-600">(one per line)</span></label>
            <textarea
              v-model="form.dirsText"
              placeholder="/path/to/repos&#10;/another/path"
              rows="4"
              class="search-input w-full px-3 py-2 text-sm font-mono resize-y"
            ></textarea>
            <p class="text-xs text-gray-600 mt-1">Each subdirectory containing a .git folder or source files will be analyzed</p>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-3 mt-6 pt-4 border-t border-border/30">
          <button
            @click="saveSource"
            :disabled="saving"
            class="px-4 py-2 text-sm font-medium bg-accent-purple/20 text-accent-purple rounded-lg hover:bg-accent-purple/30 transition-colors disabled:opacity-50"
          >
            {{ saving ? 'Saving...' : (editingExisting ? 'Update Source' : 'Add Source') }}
          </button>
          <button @click="cancelAdd" class="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors">
            Cancel
          </button>
          <span v-if="formError" class="text-xs text-red-400 ml-2">{{ formError }}</span>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="space-y-4">
        <div v-for="i in 2" :key="i" class="glass-card p-6">
          <div class="skeleton h-6 w-40 mb-3"></div>
          <div class="skeleton h-4 w-64 mb-2"></div>
          <div class="skeleton h-4 w-48"></div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="loadError" class="glass-card p-6 text-center">
        <p class="text-red-400 text-sm">{{ loadError }}</p>
        <button @click="fetchSources" class="mt-3 px-4 py-2 bg-accent-purple/20 text-accent-purple rounded-lg hover:bg-accent-purple/30 text-sm">Retry</button>
      </div>

      <!-- Empty state -->
      <div v-else-if="sources.length === 0 && !addingType" class="glass-card p-10 text-center">
        <svg class="w-14 h-14 text-gray-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <h3 class="text-gray-300 font-semibold mb-1">No sources configured</h3>
        <p class="text-gray-500 text-sm mb-4">Add a GitHub, GitLab, or local directory source to get started.</p>
        <button
          @click="showAddPicker = true"
          class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-accent-purple/15 text-accent-purple rounded-lg hover:bg-accent-purple/25 transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
          Add Source
        </button>
      </div>

      <!-- Source cards -->
      <div v-else class="space-y-4">
        <div
          v-for="src in sources"
          :key="src.type"
          class="glass-card p-6 border transition-all"
          :class="meta[src.type]?.bg || 'border-border/30'"
        >
          <div class="flex items-start justify-between gap-4">
            <!-- Left: Icon + info -->
            <div class="flex items-start gap-4 min-w-0">
              <div class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center" :class="meta[src.type]?.iconBg">
                <div :class="meta[src.type]?.color" v-html="meta[src.type]?.icon"></div>
              </div>
              <div class="min-w-0">
                <h3 class="text-base font-semibold text-gray-200">{{ meta[src.type]?.label || src.type }}</h3>

                <!-- GitHub details -->
                <div v-if="src.type === 'github'" class="mt-2 space-y-1.5">
                  <div class="flex items-center gap-2 text-sm text-gray-400">
                    <svg class="w-3.5 h-3.5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/></svg>
                    <span class="font-mono text-xs">{{ maskToken(src.token) }}</span>
                  </div>
                  <div v-if="src.orgs && src.orgs.length > 0" class="flex items-center gap-2 text-sm text-gray-400">
                    <svg class="w-3.5 h-3.5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>
                    <span>{{ src.orgs.join(', ') }}</span>
                  </div>
                  <div v-else class="text-xs text-gray-500">All accessible repositories</div>
                </div>

                <!-- GitLab details -->
                <div v-if="src.type === 'gitlab'" class="mt-2 space-y-1.5">
                  <div v-if="src.url" class="flex items-center gap-2 text-sm text-gray-400">
                    <svg class="w-3.5 h-3.5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9"/></svg>
                    <span class="font-mono text-xs">{{ src.url }}</span>
                  </div>
                  <div class="flex items-center gap-2 text-sm text-gray-400">
                    <svg class="w-3.5 h-3.5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/></svg>
                    <span class="font-mono text-xs">{{ maskToken(src.token) }}</span>
                  </div>
                  <div v-if="src.namespaces && src.namespaces.length > 0" class="flex items-center gap-2 text-sm text-gray-400">
                    <svg class="w-3.5 h-3.5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>
                    <span>{{ src.namespaces.join(', ') }}</span>
                  </div>
                  <div v-else class="text-xs text-gray-500">All accessible repositories</div>
                </div>

                <!-- Local details -->
                <div v-if="src.type === 'local'" class="mt-2 space-y-1">
                  <div v-for="dir in (src.dirs || [])" :key="dir" class="flex items-center gap-2 text-sm text-gray-400">
                    <svg class="w-3.5 h-3.5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>
                    <span class="font-mono text-xs truncate">{{ dir }}</span>
                  </div>
                  <div class="text-xs text-gray-500 mt-1">{{ (src.dirs || []).length }} director{{ (src.dirs || []).length === 1 ? 'y' : 'ies' }}</div>
                </div>
              </div>
            </div>

            <!-- Right: actions -->
            <div class="flex items-center gap-1 flex-shrink-0">
              <button
                @click="editSource(src)"
                class="p-2 rounded-lg text-gray-500 hover:text-accent-purple hover:bg-accent-purple/10 transition-all"
                title="Edit source"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
              </button>
              <button
                @click="confirmRemove(src.type)"
                class="p-2 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                title="Remove source"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
              </button>
            </div>
          </div>

          <!-- Confirm remove -->
          <div v-if="removingType === src.type" class="mt-4 pt-4 border-t border-border/30 flex items-center gap-3">
            <span class="text-sm text-gray-400">Remove this source?</span>
            <button
              @click="removeSource(src.type)"
              :disabled="removing"
              class="px-3 py-1.5 text-xs font-medium bg-red-500/15 text-red-400 rounded-lg hover:bg-red-500/25 transition-colors disabled:opacity-50"
            >
              {{ removing ? 'Removing...' : 'Confirm Remove' }}
            </button>
            <button @click="removingType = null" class="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors">Cancel</button>
          </div>
        </div>
      </div>

    </div>
  `,
  setup() {
    const meta = SOURCE_META;
    const loading = ref(false);
    const loadError = ref(null);
    const sources = ref([]);

    // Add/Edit state
    const showAddPicker = ref(false);
    const addingType = ref(null);
    const editingExisting = ref(false);
    const form = ref({});
    const formError = ref('');
    const saving = ref(false);

    // Remove state
    const removingType = ref(null);
    const removing = ref(false);

    const addableTypes = computed(() => {
      const existing = new Set(sources.value.map(s => s.type));
      return ADD_SOURCE_TYPES.filter(t => !existing.has(t.type));
    });

    function maskToken(token) {
      if (!token) return '(not set)';
      if (token.length <= 8) return '****';
      return token.substring(0, 4) + '****' + token.substring(token.length - 4);
    }

    async function fetchSources() {
      loading.value = true;
      loadError.value = null;
      try {
        const data = await api.sources();
        sources.value = data.sources || [];
      } catch (e) {
        loadError.value = e.message || 'Failed to load sources';
      } finally {
        loading.value = false;
      }
    }

    function startAdd(type) {
      showAddPicker.value = false;
      addingType.value = type;
      editingExisting.value = false;
      formError.value = '';
      form.value = { token: '', url: '', orgsText: '', namespacesText: '', dirsText: '' };
    }

    function editSource(src) {
      addingType.value = src.type;
      editingExisting.value = true;
      showAddPicker.value = false;
      formError.value = '';

      if (src.type === 'github') {
        form.value = {
          token: src.token || '',
          orgsText: (src.orgs || []).join('\n'),
        };
      } else if (src.type === 'gitlab') {
        form.value = {
          url: src.url || '',
          token: src.token || '',
          namespacesText: (src.namespaces || []).join('\n'),
        };
      } else if (src.type === 'local') {
        form.value = {
          dirsText: (src.dirs || []).join('\n'),
        };
      }
    }

    function cancelAdd() {
      addingType.value = null;
      editingExisting.value = false;
      formError.value = '';
    }

    async function saveSource() {
      formError.value = '';
      const type = addingType.value;

      let source = { type };
      if (type === 'github') {
        if (!form.value.token?.trim()) {
          formError.value = 'Token is required';
          return;
        }
        source.token = form.value.token.trim();
        const orgs = (form.value.orgsText || '').split('\n').map(s => s.trim()).filter(Boolean);
        source.orgs = orgs.length > 0 ? orgs : null;
      } else if (type === 'gitlab') {
        if (!form.value.url?.trim()) {
          formError.value = 'GitLab URL is required';
          return;
        }
        if (!form.value.token?.trim()) {
          formError.value = 'Token is required';
          return;
        }
        source.url = form.value.url.trim();
        source.token = form.value.token.trim();
        const ns = (form.value.namespacesText || '').split('\n').map(s => s.trim()).filter(Boolean);
        source.namespaces = ns.length > 0 ? ns : null;
      } else if (type === 'local') {
        const dirs = (form.value.dirsText || '').split('\n').map(s => s.trim()).filter(Boolean);
        if (dirs.length === 0) {
          formError.value = 'At least one directory is required';
          return;
        }
        source.dirs = dirs;
      }

      saving.value = true;
      try {
        const data = await api.addSource(source);
        sources.value = data.sources || [];
        addingType.value = null;
        editingExisting.value = false;
      } catch (e) {
        formError.value = e.message || 'Failed to save';
      } finally {
        saving.value = false;
      }
    }

    function confirmRemove(type) {
      removingType.value = type;
    }

    async function removeSource(type) {
      removing.value = true;
      try {
        const data = await api.removeSource(type);
        sources.value = data.sources || [];
        removingType.value = null;
      } catch (e) {
        formError.value = e.message || 'Failed to remove';
      } finally {
        removing.value = false;
      }
    }

    onMounted(() => {
      fetchSources();
    });

    return {
      meta, sources, loading, loadError,
      showAddPicker, addingType, editingExisting, addableTypes,
      form, formError, saving,
      removingType, removing,
      maskToken, fetchSources,
      startAdd, editSource, cancelAdd, saveSource,
      confirmRemove, removeSource,
    };
  },
};
