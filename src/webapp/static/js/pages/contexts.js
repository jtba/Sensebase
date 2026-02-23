// ============================================================
// SenseBase - Contexts Page
// ============================================================
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '../api.js';

export default {
  name: 'Contexts',
  template: `
    <div class="p-6 max-w-7xl mx-auto space-y-8">
      <!-- Header -->
      <div class="text-center py-4">
        <h1 class="text-4xl font-bold mb-2">
          <span class="gradient-text">Service Contexts</span>
        </h1>
        <p class="text-gray-400 text-lg">Holistic understanding of each repository's purpose and business logic</p>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div v-for="n in 6" :key="n" class="glass-card p-6 space-y-3">
          <div class="skeleton h-6 w-3/4"></div>
          <div class="skeleton h-4 w-1/2"></div>
          <div class="skeleton h-4 w-full"></div>
          <div class="skeleton h-4 w-5/6"></div>
        </div>
      </div>

      <!-- Detail View -->
      <div v-else-if="selectedRepo" class="space-y-6">
        <button @click="goBack" class="flex items-center gap-2 text-sm text-gray-400 hover:text-accent-blue transition-colors">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
          </svg>
          Back to all contexts
        </button>

        <div class="glass-card p-8">
          <div class="flex items-start justify-between mb-6">
            <div>
              <h2 class="text-2xl font-bold text-accent-blue">{{ detail.repo_name }}</h2>
              <p v-if="detail.purpose" class="text-gray-400 mt-1">{{ detail.purpose }}</p>
            </div>
            <span v-if="detail.domain" class="badge badge-schema">{{ detail.domain }}</span>
          </div>

          <div v-if="detail.context_markdown" class="prose prose-invert max-w-none context-markdown" v-html="renderMarkdown(detail.context_markdown)"></div>
          <div v-else class="text-gray-500">No context document available.</div>

          <div v-if="detail.generated_at" class="mt-8 pt-4 border-t border-border text-xs text-gray-500">
            Generated: {{ new Date(detail.generated_at).toLocaleString() }}
            <span v-if="detail.model"> | Model: {{ detail.model }}</span>
            <span v-if="detail.file_count"> | {{ detail.file_count }} files analyzed</span>
          </div>
        </div>
      </div>

      <!-- Grid View -->
      <div v-else>
        <div v-if="contexts.length === 0" class="text-center py-16">
          <svg class="w-16 h-16 text-gray-600 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/>
          </svg>
          <p class="text-gray-400 text-lg mb-2">No contexts generated yet</p>
          <p class="text-gray-500 text-sm">Run the pipeline with LLM extraction enabled to generate service contexts.</p>
          <router-link to="/crawl" class="inline-block mt-4 px-4 py-2 rounded-lg bg-accent-blue/10 border border-accent-blue/30 text-accent-blue text-sm hover:bg-accent-blue/20 transition-all">
            Go to Pipeline
          </router-link>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div v-for="ctx in contexts" :key="ctx.repo_name"
               @click="selectRepo(ctx.repo_name)"
               class="glass-card glass-card-interactive p-6 cursor-pointer group">
            <div class="flex items-start justify-between mb-3">
              <h3 class="text-lg font-semibold group-hover:text-accent-blue transition-colors">{{ ctx.repo_name }}</h3>
              <span v-if="ctx.domain" class="badge badge-schema text-xs">{{ ctx.domain }}</span>
            </div>
            <p v-if="ctx.purpose" class="text-sm text-gray-400 mb-4 line-clamp-2">{{ ctx.purpose }}</p>
            <div v-if="ctx.when_to_use && ctx.when_to_use.length > 0" class="space-y-1.5 mb-4">
              <div v-for="(condition, i) in ctx.when_to_use.slice(0, 3)" :key="i"
                   class="flex items-start gap-2 text-xs text-gray-500">
                <svg class="w-3 h-3 text-accent-teal mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
                </svg>
                <span>{{ condition }}</span>
              </div>
              <div v-if="ctx.when_to_use.length > 3" class="text-xs text-gray-600 pl-5">
                +{{ ctx.when_to_use.length - 3 }} more...
              </div>
            </div>
            <div class="flex items-center justify-between text-xs text-gray-600 mt-auto pt-3 border-t border-border/50">
              <span v-if="ctx.file_count">{{ ctx.file_count }} files</span>
              <span class="group-hover:text-accent-blue transition-colors">View context &rarr;</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const route = useRoute();
    const router = useRouter();
    const loading = ref(true);
    const contexts = ref([]);
    const detail = ref({});
    const selectedRepo = computed(() => route.params.name || null);

    function renderMarkdown(md) {
      let html = md
        // Code blocks
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block overflow-x-auto"><code>$2</code></pre>')
        // Inline code
        .replace(/`([^`]+)`/g, '<code class="text-accent-blue bg-surface-dark px-1 py-0.5 rounded text-sm">$1</code>')
        // Headers
        .replace(/^#### (.+)$/gm, '<h4 class="text-base font-semibold mt-6 mb-2 text-gray-200">$1</h4>')
        .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-8 mb-3 text-gray-100">$1</h3>')
        .replace(/^## (.+)$/gm, '<h2 class="text-xl font-bold mt-10 mb-4 text-accent-blue border-b border-border pb-2">$1</h2>')
        .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-8 mb-4 gradient-text">$1</h1>')
        // Bold
        .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-gray-100">$1</strong>')
        // Italic
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        // Unordered lists
        .replace(/^- (.+)$/gm, '<li class="ml-4 text-gray-300 mb-1">$1</li>')
        // Paragraphs
        .replace(/^(?!<[hluop]|<li|<pre|<code|<hr)(.+)$/gm, '<p class="text-gray-300 mb-3 leading-relaxed">$1</p>')
        // Wrap consecutive li elements in ul
        .replace(/(<li[^>]*>.*?<\/li>\n?)+/g, '<ul class="list-disc mb-4">$&</ul>')
        // Horizontal rules
        .replace(/^---$/gm, '<hr class="border-border my-6">');
      return html;
    }

    async function loadContexts() {
      loading.value = true;
      try {
        const data = await api.contexts();
        contexts.value = data.contexts || [];
      } catch (err) {
        console.error('Failed to load contexts:', err);
        contexts.value = [];
      } finally {
        loading.value = false;
      }
    }

    async function loadDetail(name) {
      loading.value = true;
      try {
        detail.value = await api.repoContext(name);
      } catch (err) {
        console.error('Failed to load context detail:', err);
        detail.value = {};
      } finally {
        loading.value = false;
      }
    }

    function selectRepo(name) {
      router.push(`/contexts/${encodeURIComponent(name)}`);
    }

    function goBack() {
      router.push('/contexts');
    }

    watch(() => route.params.name, (name) => {
      if (name) {
        loadDetail(name);
      } else {
        loadContexts();
      }
    });

    onMounted(() => {
      if (selectedRepo.value) {
        loadDetail(selectedRepo.value);
      } else {
        loadContexts();
      }
    });

    return {
      loading, contexts, detail, selectedRepo,
      renderMarkdown, selectRepo, goBack,
    };
  },
};
