// ============================================================
// SenseBase - Schema Explorer Page
// ============================================================

import { ref, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { api } from '../api.js';

export default {
  name: 'SchemasPage',
  template: `
    <div class="p-6 max-w-7xl mx-auto">

      <!-- Detail view -->
      <div v-if="selectedName">

        <!-- Back button -->
        <button @click="goBack" class="flex items-center gap-2 text-gray-400 hover:text-gray-200 transition-colors mb-6 group">
          <svg class="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
          </svg>
          <span class="text-sm">Back to Schemas</span>
        </button>

        <!-- Loading detail -->
        <div v-if="detailLoading" class="space-y-4">
          <div class="skeleton h-10 w-64"></div>
          <div class="skeleton h-6 w-40"></div>
          <div class="skeleton h-48 w-full mt-6"></div>
        </div>

        <!-- Detail error -->
        <div v-else-if="detailError" class="glass-card p-6 text-center">
          <p class="text-red-400">{{ detailError }}</p>
          <button @click="fetchDetail" class="mt-3 px-4 py-2 bg-accent-blue/20 text-accent-blue rounded-lg hover:bg-accent-blue/30 text-sm">Retry</button>
        </div>

        <!-- Detail content -->
        <div v-else-if="detailData">
          <!-- Header -->
          <div class="mb-8">
            <div class="flex items-start gap-3 flex-wrap">
              <h1 class="text-2xl font-bold text-gray-100">{{ detailData.name }}</h1>
              <span class="badge badge-schema">{{ detailData.type || 'schema' }}</span>
            </div>
            <div class="flex items-center gap-4 mt-2 text-sm text-gray-500">
              <span v-if="detailData.repo" class="flex items-center gap-1">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>
                {{ detailData.repo }}
              </span>
              <span v-if="detailData.source_file" class="font-mono text-xs text-gray-600">{{ detailData.source_file }}</span>
            </div>
            <button
              @click="router.push({ path: '/graph', query: { focus: 'schema:' + detailData.name } })"
              class="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-accent-blue/10 text-accent-blue rounded-lg hover:bg-accent-blue/20 transition-colors"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
              View in Graph
            </button>
          </div>

          <!-- Business Meaning -->
          <div v-if="detailData.description || detailData.business_context" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3">Business Meaning</h2>
            <p v-if="detailData.description" class="text-gray-300 leading-relaxed text-sm">{{ detailData.description }}</p>
            <p v-if="detailData.business_context" class="text-gray-400 mt-2 text-sm leading-relaxed">{{ detailData.business_context }}</p>
          </div>

          <!-- Query Recipes -->
          <div v-if="detailData.query_recipes && detailData.query_recipes.length > 0" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3">How to Query This Data</h2>
            <div v-for="(recipe, i) in detailData.query_recipes" :key="i" class="mb-4 last:mb-0 p-3 rounded-lg bg-surface/50 border border-border/50">
              <p class="text-sm text-accent-blue font-medium mb-2">{{ recipe.question }}</p>
              <div v-for="(step, j) in recipe.steps" :key="j" class="text-xs text-gray-400 ml-3 mb-1">
                <span class="font-mono text-accent-teal">{{ step.action }}</span>
                <span v-if="step.purpose" class="text-gray-500"> &mdash; {{ step.purpose }}</span>
              </div>
              <p v-if="recipe.answer_format" class="text-xs text-gray-500 mt-2 italic">{{ recipe.answer_format }}</p>
            </div>
          </div>

          <!-- Fields table -->
          <div v-if="detailData.fields && detailData.fields.length > 0" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Fields ({{ detailData.fields.length }})</h2>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-left text-gray-500 border-b border-border">
                    <th class="pb-2 pr-4 font-medium">Name</th>
                    <th class="pb-2 pr-4 font-medium">Type</th>
                    <th class="pb-2 pr-4 font-medium">Constraints</th>
                    <th class="pb-2 font-medium">Description</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(field, i) in detailData.fields" :key="i" class="border-b border-border/50 hover:bg-surface/30">
                    <td class="py-2 pr-4 font-mono text-accent-blue text-xs">{{ field.name || field }}</td>
                    <td class="py-2 pr-4 font-mono text-gray-400 text-xs">{{ field.type || '-' }}</td>
                    <td class="py-2 pr-4 text-gray-500 text-xs">
                      <span v-if="field.constraints" class="inline-flex flex-wrap gap-1">
                        <span v-for="c in normalizeConstraints(field.constraints)" :key="c" class="px-1.5 py-0.5 bg-surface rounded text-xs text-gray-400">{{ c }}</span>
                      </span>
                      <span v-else-if="field.nullable === false" class="px-1.5 py-0.5 bg-surface rounded text-xs text-gray-400">NOT NULL</span>
                      <span v-else class="text-gray-600">-</span>
                    </td>
                    <td class="py-2 text-gray-500 text-xs">{{ field.description || '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Relationships -->
          <div v-if="relationships && relationships.references_to && relationships.references_to.length > 0" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">References To</h2>
            <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              <button
                v-for="rel in relationships.references_to"
                :key="rel.target || rel.name"
                @click="navigateToSchema(rel.target || rel.name)"
                class="text-left p-3 rounded-lg bg-surface/50 hover:bg-surface border border-border/50 hover:border-accent-blue/30 transition-all group"
              >
                <span class="text-sm text-gray-200 group-hover:text-accent-blue font-medium">{{ rel.target || rel.name }}</span>
                <span v-if="rel.type" class="block text-xs text-gray-500 mt-0.5">{{ rel.type }}</span>
                <span v-if="rel.description" class="block text-xs text-gray-600 mt-0.5">{{ rel.description }}</span>
              </button>
            </div>
          </div>

          <!-- Referenced By -->
          <div v-if="relationships && relationships.referenced_by && relationships.referenced_by.length > 0" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Referenced By</h2>
            <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              <button
                v-for="ref in relationships.referenced_by"
                :key="ref.source || ref.name"
                @click="navigateToSchema(ref.source || ref.name)"
                class="text-left p-3 rounded-lg bg-surface/50 hover:bg-surface border border-border/50 hover:border-accent-purple/30 transition-all group"
              >
                <span class="text-sm text-gray-200 group-hover:text-accent-purple font-medium">{{ ref.source || ref.name }}</span>
                <span v-if="ref.type" class="block text-xs text-gray-500 mt-0.5">{{ ref.type }}</span>
              </button>
            </div>
          </div>

          <!-- Raw relationships from schema -->
          <div v-if="detailData.relationships && detailData.relationships.length > 0 && (!relationships || (!relationships.references_to.length && !relationships.referenced_by.length))" class="glass-card p-5 mb-6">
            <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Relationships</h2>
            <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              <div v-for="(rel, i) in detailData.relationships" :key="i"
                class="p-3 rounded-lg bg-surface/50 border border-border/50"
              >
                <span class="text-sm text-gray-200 font-medium">{{ typeof rel === 'string' ? rel : (rel.target || rel.name || JSON.stringify(rel)) }}</span>
                <span v-if="rel.type" class="block text-xs text-gray-500 mt-0.5">{{ rel.type }}</span>
              </div>
            </div>
          </div>

          <!-- Raw definition (collapsible) -->
          <div class="glass-card p-5 mb-6">
            <button @click="showRaw = !showRaw" class="flex items-center gap-2 text-sm font-semibold text-gray-300 uppercase tracking-wider w-full">
              <svg class="w-4 h-4 transition-transform" :class="{ 'rotate-90': showRaw }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
              </svg>
              Raw Definition
            </button>
            <div v-if="showRaw" class="mt-3">
              <pre class="code-block text-xs overflow-x-auto">{{ JSON.stringify(detailData, null, 2) }}</pre>
            </div>
          </div>
        </div>
      </div>

      <!-- List view -->
      <div v-else>
        <!-- Header -->
        <div class="mb-6">
          <h1 class="text-2xl font-bold gradient-text mb-1">Schema Explorer</h1>
          <p class="text-gray-500 text-sm">Browse and explore data schemas across repositories</p>
        </div>

        <!-- Search & Filters -->
        <div class="flex flex-col sm:flex-row gap-3 mb-6">
          <div class="flex-1">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search schemas by name..."
              class="search-input w-full px-4 py-2.5 text-sm"
            />
          </div>
          <div class="flex gap-2 flex-wrap">
            <button
              v-for="t in schemaTypes"
              :key="t"
              @click="toggleTypeFilter(t)"
              class="filter-chip"
              :class="{ 'filter-chip-active': activeTypeFilter === t }"
            >
              {{ t }}
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
            :class="sortBy === s.key ? 'bg-accent-blue/15 text-accent-blue' : 'hover:text-gray-300'"
          >
            {{ s.label }}
          </button>
          <span class="ml-auto text-gray-600">{{ filteredSchemas.length }} schemas</span>
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
        <div v-else-if="listError" class="glass-card p-6 text-center">
          <p class="text-red-400">{{ listError }}</p>
          <button @click="fetchList" class="mt-3 px-4 py-2 bg-accent-blue/20 text-accent-blue rounded-lg hover:bg-accent-blue/30 text-sm">Retry</button>
        </div>

        <!-- Empty -->
        <div v-else-if="filteredSchemas.length === 0 && !loading" class="glass-card p-8 text-center">
          <svg class="w-12 h-12 text-gray-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/>
          </svg>
          <p class="text-gray-400">No schemas found{{ searchQuery ? ' matching "' + searchQuery + '"' : '' }}</p>
        </div>

        <!-- Schema Grid -->
        <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <button
            v-for="schema in filteredSchemas"
            :key="schema.name + (schema.repo || '')"
            @click="navigateToSchema(schema.name)"
            class="glass-card glass-card-interactive p-5 text-left transition-all"
          >
            <div class="flex items-start justify-between gap-2 mb-2">
              <h3 class="text-sm font-semibold text-gray-200 truncate">{{ schema.name }}</h3>
              <span class="badge badge-schema flex-shrink-0">{{ schema.type || 'schema' }}</span>
            </div>
            <div v-if="schema.repo" class="text-xs text-gray-500 truncate">{{ schema.repo }}</div>
            <p v-if="schema.description" class="text-xs text-gray-400 mt-1 mb-2 line-clamp-2" style="-webkit-line-clamp:2; display:-webkit-box; -webkit-box-orient:vertical; overflow:hidden;">{{ schema.description }}</p>
            <div v-else class="mb-3"></div>
            <div class="flex gap-4 text-xs text-gray-500">
              <span>
                <span class="text-gray-300 font-medium">{{ (schema.fields || []).length }}</span> fields
              </span>
              <span>
                <span class="text-gray-300 font-medium">{{ (schema.relationships || []).length }}</span> relationships
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
    const schemas = ref([]);
    const searchQuery = ref('');
    const activeTypeFilter = ref(null);
    const sortBy = ref('name');

    const detailLoading = ref(false);
    const detailError = ref(null);
    const detailData = ref(null);
    const relationships = ref(null);
    const showRaw = ref(false);

    const selectedName = computed(() => route.params.name || null);

    const sortOptions = [
      { key: 'name', label: 'Name' },
      { key: 'fields', label: 'Fields' },
      { key: 'relationships', label: 'Relationships' },
    ];

    const schemaTypes = computed(() => {
      const types = new Set();
      for (const s of schemas.value) {
        if (s.type) types.add(s.type);
      }
      return Array.from(types).sort();
    });

    const filteredSchemas = computed(() => {
      let result = schemas.value;

      if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase();
        result = result.filter(s => s.name.toLowerCase().includes(q));
      }

      if (activeTypeFilter.value) {
        result = result.filter(s => s.type === activeTypeFilter.value);
      }

      // Sort
      result = [...result].sort((a, b) => {
        switch (sortBy.value) {
          case 'fields':
            return (b.fields || []).length - (a.fields || []).length;
          case 'relationships':
            return (b.relationships || []).length - (a.relationships || []).length;
          default:
            return a.name.localeCompare(b.name);
        }
      });

      return result;
    });

    function toggleTypeFilter(type) {
      activeTypeFilter.value = activeTypeFilter.value === type ? null : type;
    }

    function navigateToSchema(name) {
      router.push(`/schemas/${encodeURIComponent(name)}`);
    }

    function goBack() {
      router.push('/schemas');
    }

    function normalizeConstraints(constraints) {
      if (Array.isArray(constraints)) return constraints;
      if (typeof constraints === 'string') return [constraints];
      if (typeof constraints === 'object') return Object.entries(constraints).map(([k, v]) => `${k}: ${v}`);
      return [];
    }

    async function fetchList() {
      loading.value = true;
      listError.value = null;
      try {
        schemas.value = await api.schemas();
      } catch (e) {
        listError.value = e.message || 'Failed to load schemas';
      } finally {
        loading.value = false;
      }
    }

    async function fetchDetail() {
      if (!selectedName.value) return;
      detailLoading.value = true;
      detailError.value = null;
      detailData.value = null;
      relationships.value = null;
      showRaw.value = false;

      try {
        const results = await api.schema(selectedName.value);
        detailData.value = Array.isArray(results) ? results[0] : results;
      } catch (e) {
        detailError.value = e.message || 'Failed to load schema';
      } finally {
        detailLoading.value = false;
      }

      // Fetch relationships separately (may 404)
      try {
        relationships.value = await api.schemaRelationships(selectedName.value);
      } catch (e) {
        // Relationships may not exist, that is fine
        relationships.value = null;
      }
    }

    // Watch route changes
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
      schemas,
      searchQuery,
      activeTypeFilter,
      sortBy,
      sortOptions,
      schemaTypes,
      filteredSchemas,
      selectedName,
      detailLoading,
      detailError,
      detailData,
      relationships,
      showRaw,
      router,
      toggleTypeFilter,
      navigateToSchema,
      goBack,
      normalizeConstraints,
      fetchList,
      fetchDetail,
    };
  },
};
