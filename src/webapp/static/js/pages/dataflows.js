// ============================================================
// SenseBase - Data Flows Page
// ============================================================

import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { api } from '../api.js';

export default {
  name: 'DataFlowsPage',
  template: `
    <div class="p-6 max-w-7xl mx-auto">

      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold gradient-text mb-1">Data Flows</h1>
        <p class="text-gray-500 text-sm">Visualize how data moves between services and components</p>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="space-y-4">
        <div class="glass-card p-5">
          <div class="skeleton h-64 w-full mb-4"></div>
        </div>
        <div class="glass-card p-5">
          <div class="skeleton h-5 w-40 mb-3"></div>
          <div v-for="i in 4" :key="i" class="skeleton h-10 w-full mb-2"></div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="glass-card p-6 text-center">
        <p class="text-red-400">{{ error }}</p>
        <button @click="fetchFlows" class="mt-3 px-4 py-2 bg-accent-blue/20 text-accent-blue rounded-lg hover:bg-accent-blue/30 text-sm">Retry</button>
      </div>

      <!-- Empty state -->
      <div v-else-if="flows.length === 0 && !loading" class="glass-card p-8 text-center">
        <svg class="w-16 h-16 text-gray-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
        </svg>
        <h3 class="text-lg font-semibold text-gray-200 mb-2">No Data Flows Detected</h3>
        <p class="text-gray-400 text-sm mb-4 max-w-md mx-auto">
          Run the analysis with the <code class="code-inline">--llm</code> flag for better data flow detection,
          or ensure your codebase has detectable data flow patterns.
        </p>
        <code class="block text-xs font-mono text-accent-blue bg-surface/60 rounded-lg p-3 max-w-sm mx-auto">sensebase --analyze --llm</code>
      </div>

      <!-- Content when flows exist -->
      <div v-else>

        <!-- Flow type stats -->
        <div class="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
          <div v-for="(count, type) in flowTypeCounts" :key="type" class="glass-card p-3 text-center">
            <div class="text-lg font-bold" :style="{ color: flowTypeColor(type) }">{{ count }}</div>
            <div class="text-xs text-gray-500 capitalize">{{ type || 'other' }}</div>
          </div>
        </div>

        <!-- Filters -->
        <div class="flex flex-col sm:flex-row gap-3 mb-4">
          <div class="flex-1">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search flows..."
              class="search-input w-full px-4 py-2.5 text-sm"
            />
          </div>
          <div class="flex gap-2 flex-wrap items-center">
            <button
              @click="activeType = null"
              class="filter-chip"
              :class="{ 'filter-chip-active': !activeType }"
            >
              All
            </button>
            <button
              v-for="type in flowTypes"
              :key="type"
              @click="activeType = activeType === type ? null : type"
              class="filter-chip"
              :class="{ 'filter-chip-active': activeType === type }"
              :style="activeType === type ? { borderColor: flowTypeColor(type), color: flowTypeColor(type) } : {}"
            >
              {{ type }}
            </button>
          </div>
        </div>

        <!-- Repo filter -->
        <div v-if="availableRepos.length > 1" class="flex gap-2 flex-wrap mb-4">
          <button
            @click="activeRepo = null"
            class="filter-chip"
            :class="{ 'filter-chip-active': !activeRepo }"
          >
            All Repos
          </button>
          <button
            v-for="repo in availableRepos"
            :key="repo"
            @click="activeRepo = activeRepo === repo ? null : repo"
            class="filter-chip"
            :class="{ 'filter-chip-active': activeRepo === repo }"
          >
            {{ repo }}
          </button>
        </div>

        <!-- D3 Flow Diagram -->
        <div v-if="filteredFlows.length > 0" class="glass-card p-4 mb-6 overflow-hidden">
          <h3 class="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3">Flow Diagram</h3>
          <div ref="flowContainer" class="w-full" style="height: 400px; overflow: hidden;"></div>
        </div>

        <!-- Flow count -->
        <div class="flex items-center justify-between mb-4 text-xs text-gray-500">
          <span>{{ filteredFlows.length }} flows</span>
        </div>

        <!-- Flow Table -->
        <div class="glass-card overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-gray-500 border-b border-border">
                  <th class="px-5 py-3 font-medium text-xs uppercase tracking-wider">Source</th>
                  <th class="px-5 py-3 font-medium text-xs uppercase tracking-wider">Direction</th>
                  <th class="px-5 py-3 font-medium text-xs uppercase tracking-wider">Target</th>
                  <th class="px-5 py-3 font-medium text-xs uppercase tracking-wider">Type</th>
                  <th class="px-5 py-3 font-medium text-xs uppercase tracking-wider hidden lg:table-cell">Description</th>
                  <th class="px-5 py-3 font-medium text-xs uppercase tracking-wider hidden md:table-cell">Repo</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(flow, i) in filteredFlows"
                  :key="i"
                  class="border-b border-border/30 hover:bg-surface/20 transition-colors"
                >
                  <td class="px-5 py-3 font-mono text-xs text-gray-300">{{ flow.source }}</td>
                  <td class="px-5 py-3 text-center">
                    <svg class="w-5 h-5 inline-block" :style="{ color: flowTypeColor(flow.type) }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
                    </svg>
                  </td>
                  <td class="px-5 py-3 font-mono text-xs text-gray-300">{{ flow.target }}</td>
                  <td class="px-5 py-3">
                    <span
                      class="inline-block px-2 py-0.5 rounded text-xs font-medium capitalize"
                      :style="{ background: flowTypeColor(flow.type) + '20', color: flowTypeColor(flow.type) }"
                    >
                      {{ flow.type || 'data' }}
                    </span>
                  </td>
                  <td class="px-5 py-3 text-xs text-gray-500 hidden lg:table-cell max-w-xs truncate">{{ flow.description || '-' }}</td>
                  <td class="px-5 py-3 text-xs text-gray-500 hidden md:table-cell">{{ flow.repo || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const d3 = window.d3;
    const router = useRouter();
    const route = useRoute();

    const loading = ref(false);
    const error = ref(null);
    const flows = ref([]);
    const searchQuery = ref('');
    const activeType = ref(null);
    const activeRepo = ref(null);
    const flowContainer = ref(null);

    let svgElement = null;

    const flowTypes = computed(() => {
      const types = new Set();
      for (const f of flows.value) {
        if (f.type) types.add(f.type);
      }
      return Array.from(types).sort();
    });

    const flowTypeCounts = computed(() => {
      const counts = {};
      for (const f of flows.value) {
        const type = f.type || 'other';
        counts[type] = (counts[type] || 0) + 1;
      }
      return counts;
    });

    const availableRepos = computed(() => {
      const repos = new Set();
      for (const f of flows.value) {
        if (f.repo) repos.add(f.repo);
      }
      return Array.from(repos).sort();
    });

    const filteredFlows = computed(() => {
      let result = flows.value;

      if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase();
        result = result.filter(f =>
          (f.source || '').toLowerCase().includes(q) ||
          (f.target || '').toLowerCase().includes(q) ||
          (f.description || '').toLowerCase().includes(q)
        );
      }

      if (activeType.value) {
        result = result.filter(f => f.type === activeType.value);
      }

      if (activeRepo.value) {
        result = result.filter(f => f.repo === activeRepo.value);
      }

      return result;
    });

    function flowTypeColor(type) {
      const colors = {
        read: '#3b82f6',
        write: '#ef4444',
        transform: '#8b5cf6',
        publish: '#22c55e',
        subscribe: '#f59e0b',
        dependency: '#6b7280',
        data_flow: '#ec4899',
      };
      return colors[(type || '').toLowerCase()] || '#6b7280';
    }

    function renderFlowDiagram() {
      if (!flowContainer.value || !d3 || filteredFlows.value.length === 0) return;

      // Clear previous
      d3.select(flowContainer.value).selectAll('*').remove();

      const container = flowContainer.value;
      const width = container.clientWidth;
      const height = 400;

      // Build nodes and links
      const nodeSet = new Set();
      const links = [];
      const linkCounts = {};

      for (const flow of filteredFlows.value) {
        if (flow.source) nodeSet.add(flow.source);
        if (flow.target) nodeSet.add(flow.target);
        const key = `${flow.source}->${flow.target}`;
        linkCounts[key] = (linkCounts[key] || 0) + 1;
      }

      const nodes = Array.from(nodeSet).map(name => ({ id: name, label: name }));
      const nodeById = {};
      nodes.forEach(n => { nodeById[n.id] = n; });

      // Deduplicate links and count
      const seenLinks = {};
      for (const flow of filteredFlows.value) {
        const key = `${flow.source}->${flow.target}`;
        if (!seenLinks[key]) {
          seenLinks[key] = {
            source: flow.source,
            target: flow.target,
            type: flow.type || 'data',
            count: linkCounts[key],
          };
        }
      }
      const uniqueLinks = Object.values(seenLinks);

      // Create SVG
      const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

      svgElement = svg;

      // Defs for arrows
      const defs = svg.append('defs');
      const arrowTypes = [...new Set(uniqueLinks.map(l => l.type))];
      arrowTypes.forEach(type => {
        defs.append('marker')
          .attr('id', `flow-arrow-${type}`)
          .attr('viewBox', '0 -5 10 10')
          .attr('refX', 25)
          .attr('refY', 0)
          .attr('markerWidth', 8)
          .attr('markerHeight', 8)
          .attr('orient', 'auto')
          .append('path')
          .attr('d', 'M0,-4L8,0L0,4')
          .attr('fill', flowTypeColor(type));
      });

      // Zoom
      const g = svg.append('g');
      svg.call(d3.zoom()
        .scaleExtent([0.3, 4])
        .on('zoom', (event) => {
          g.attr('transform', event.transform);
        })
      );

      // Width scale for edge
      const widthScale = d3.scaleLinear()
        .domain([1, d3.max(uniqueLinks, l => l.count) || 1])
        .range([1.5, 6]);

      // Links
      const linkElements = g.append('g')
        .selectAll('line')
        .data(uniqueLinks)
        .join('line')
        .attr('stroke', d => flowTypeColor(d.type))
        .attr('stroke-width', d => widthScale(d.count))
        .attr('stroke-opacity', 0.5)
        .attr('marker-end', d => `url(#flow-arrow-${d.type})`);

      // Nodes
      const nodeElements = g.append('g')
        .selectAll('g')
        .data(nodes)
        .join('g')
        .attr('class', 'graph-node')
        .call(d3.drag()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
        );

      nodeElements.append('circle')
        .attr('r', 12)
        .attr('fill', '#1a1a2e')
        .attr('stroke', '#3b82f6')
        .attr('stroke-width', 2);

      nodeElements.append('text')
        .text(d => d.label)
        .attr('class', 'graph-node-label')
        .attr('dy', 28)
        .style('opacity', 1);

      // Force simulation
      const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(uniqueLinks)
          .id(d => d.id)
          .distance(120)
        )
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide().radius(40))
        .alphaDecay(0.02)
        .on('tick', () => {
          linkElements
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

          nodeElements
            .attr('transform', d => `translate(${d.x},${d.y})`);
        });
    }

    // Re-render diagram when filters change
    watch(filteredFlows, async () => {
      await nextTick();
      renderFlowDiagram();
    });

    async function fetchFlows() {
      loading.value = true;
      error.value = null;
      try {
        const data = await api.dataFlows();
        flows.value = data.flows || [];
        await nextTick();
        renderFlowDiagram();
      } catch (e) {
        error.value = e.message || 'Failed to load data flows';
      } finally {
        loading.value = false;
      }
    }

    onMounted(() => {
      fetchFlows();
    });

    onUnmounted(() => {
      if (svgElement) {
        svgElement.remove();
      }
    });

    return {
      loading,
      error,
      flows,
      searchQuery,
      activeType,
      activeRepo,
      flowContainer,
      flowTypes,
      flowTypeCounts,
      availableRepos,
      filteredFlows,
      flowTypeColor,
      fetchFlows,
      router,
    };
  },
};
