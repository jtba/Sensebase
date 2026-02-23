// ============================================================
// SenseBase - Knowledge Graph Page
// ============================================================
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { api } from '../api.js';

export default {
  name: 'GraphPage',
  template: `
    <div class="relative w-full" style="height: calc(100vh - 64px);">
      <!-- Loading overlay -->
      <div v-if="loading" class="absolute inset-0 flex items-center justify-center z-20 bg-surface-dark/80">
        <div class="text-center">
          <div class="w-12 h-12 border-2 border-accent-blue border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p class="text-gray-400">Loading knowledge graph...</p>
        </div>
      </div>

      <!-- Error state -->
      <div v-if="error && !loading" class="absolute inset-0 flex items-center justify-center z-20">
        <div class="glass-card p-8 text-center max-w-md">
          <svg class="w-12 h-12 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/>
          </svg>
          <h3 class="text-lg font-semibold text-gray-200 mb-2">Failed to Load Graph</h3>
          <p class="text-gray-400 text-sm mb-4">{{ error }}</p>
          <button @click="fetchData" class="px-4 py-2 bg-accent-blue/20 text-accent-blue rounded-lg hover:bg-accent-blue/30 transition-colors">
            Retry
          </button>
        </div>
      </div>

      <!-- Empty state -->
      <div v-if="!loading && !error && graphData && graphData.nodes.length === 0" class="absolute inset-0 flex items-center justify-center z-20">
        <div class="glass-card p-8 text-center max-w-md">
          <svg class="w-16 h-16 text-gray-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
          </svg>
          <h3 class="text-lg font-semibold text-gray-200 mb-2">No Data Available</h3>
          <p class="text-gray-400 text-sm">Run the analysis pipeline first to generate knowledge graph data.</p>
          <code class="block mt-4 text-xs font-mono text-accent-blue bg-surface/60 rounded-lg p-3">sensebase --full</code>
        </div>
      </div>

      <!-- SVG Canvas -->
      <div ref="graphContainer" class="w-full h-full overflow-hidden"></div>

      <!-- Control Panel (top-left) -->
      <div class="absolute top-4 left-4 z-10 glass-card p-4 w-64" v-if="!loading && !error && graphData && graphData.nodes.length > 0">
        <h3 class="text-sm font-semibold text-gray-200 mb-3">Filters</h3>

        <!-- Search -->
        <div class="mb-3">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search nodes..."
            class="search-input w-full px-3 py-1.5 text-sm"
          />
        </div>

        <!-- Type filters -->
        <div class="space-y-1.5 mb-4">
          <label v-for="t in nodeTypes" :key="t.key" class="flex items-center gap-2 cursor-pointer text-sm">
            <input type="checkbox" v-model="t.visible" class="rounded border-gray-600 text-accent-blue focus:ring-accent-blue bg-surface" />
            <span class="w-2.5 h-2.5 rounded-full" :style="{ background: typeColors[t.key] }"></span>
            <span class="text-gray-300">{{ t.label }}</span>
            <span class="text-gray-500 text-xs ml-auto">{{ typeCounts[t.key] || 0 }}</span>
          </label>
        </div>

        <!-- Layout controls -->
        <div class="flex gap-2 mb-3">
          <button @click="resetZoom" class="flex-1 px-3 py-1.5 text-xs font-medium bg-surface border border-border rounded-lg text-gray-400 hover:text-gray-200 hover:border-accent-blue/50 transition-colors">
            Reset Zoom
          </button>
          <button @click="centerGraph" class="flex-1 px-3 py-1.5 text-xs font-medium bg-surface border border-border rounded-lg text-gray-400 hover:text-gray-200 hover:border-accent-blue/50 transition-colors">
            Center
          </button>
        </div>

        <!-- Stats -->
        <div class="border-t border-border pt-3">
          <div class="flex justify-between text-xs text-gray-500">
            <span>Nodes: <span class="text-gray-300">{{ visibleNodeCount }}</span></span>
            <span>Edges: <span class="text-gray-300">{{ visibleEdgeCount }}</span></span>
          </div>
        </div>
      </div>

      <!-- Detail Panel (right side, slides in) -->
      <div v-if="selectedNode" class="absolute top-4 right-4 bottom-4 z-10 glass-card p-5 w-80 overflow-y-auto">
        <!-- Close button -->
        <button @click="selectedNode = null; resetHighlight()" class="absolute top-3 right-3 text-gray-500 hover:text-gray-200 transition-colors">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>

        <!-- Node header -->
        <div class="mb-4 pr-6">
          <h3 class="text-lg font-semibold text-gray-100 break-words">{{ selectedNode.label || selectedNode.name || selectedNode.id }}</h3>
          <span class="badge mt-1" :class="'badge-' + selectedNode.type">{{ selectedNode.type }}</span>
          <p v-if="selectedNode.repo" class="text-xs text-gray-500 mt-2 font-mono">{{ selectedNode.repo }}</p>
        </div>

        <!-- Metadata -->
        <div v-if="selectedNode.metadata" class="mb-4 space-y-2">
          <div v-if="selectedNode.metadata.source_file">
            <span class="text-xs text-gray-500">Source File</span>
            <p class="text-sm font-mono text-gray-300 break-all">{{ selectedNode.metadata.source_file }}</p>
          </div>
          <div v-if="selectedNode.metadata.description">
            <span class="text-xs text-gray-500">Description</span>
            <p class="text-sm text-gray-300">{{ selectedNode.metadata.description }}</p>
          </div>
          <div v-if="selectedNode.metadata.type">
            <span class="text-xs text-gray-500">Subtype</span>
            <p class="text-sm text-gray-300">{{ selectedNode.metadata.type }}</p>
          </div>
          <div v-if="selectedNode.metadata.ecosystem">
            <span class="text-xs text-gray-500">Ecosystem</span>
            <p class="text-sm text-gray-300">{{ selectedNode.metadata.ecosystem }}</p>
          </div>
          <div v-if="selectedNode.metadata.version">
            <span class="text-xs text-gray-500">Version</span>
            <p class="text-sm text-gray-300">{{ selectedNode.metadata.version }}</p>
          </div>
        </div>

        <!-- Connections -->
        <div v-if="selectedConnections.outgoing.length > 0" class="mb-4">
          <h4 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Outgoing ({{ selectedConnections.outgoing.length }})</h4>
          <div class="space-y-1">
            <button
              v-for="conn in selectedConnections.outgoing"
              :key="conn.targetId"
              @click="selectNodeById(conn.targetId)"
              class="w-full text-left px-3 py-2 rounded-lg bg-surface/50 hover:bg-surface text-sm transition-colors group"
            >
              <span class="text-gray-300 group-hover:text-gray-100">{{ conn.targetLabel }}</span>
              <span class="text-xs text-gray-600 ml-2">{{ conn.label }}</span>
            </button>
          </div>
        </div>

        <div v-if="selectedConnections.incoming.length > 0" class="mb-4">
          <h4 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Incoming ({{ selectedConnections.incoming.length }})</h4>
          <div class="space-y-1">
            <button
              v-for="conn in selectedConnections.incoming"
              :key="conn.sourceId"
              @click="selectNodeById(conn.sourceId)"
              class="w-full text-left px-3 py-2 rounded-lg bg-surface/50 hover:bg-surface text-sm transition-colors group"
            >
              <span class="text-gray-300 group-hover:text-gray-100">{{ conn.sourceLabel }}</span>
              <span class="text-xs text-gray-600 ml-2">{{ conn.label }}</span>
            </button>
          </div>
        </div>

        <!-- View details link -->
        <button
          v-if="detailRoute"
          @click="router.push(detailRoute)"
          class="w-full mt-2 px-4 py-2 bg-accent-blue/15 text-accent-blue text-sm font-medium rounded-lg hover:bg-accent-blue/25 transition-colors"
        >
          View Details
        </button>
      </div>
    </div>
  `,
  setup() {
    const d3 = window.d3;
    const router = useRouter();
    const route = useRoute();

    const graphContainer = ref(null);
    const loading = ref(true);
    const error = ref(null);
    const graphData = ref(null);
    const selectedNode = ref(null);
    const searchQuery = ref('');
    const currentZoomLevel = ref(1);

    let simulation = null;
    let svg = null;
    let g = null;
    let zoomBehavior = null;
    let nodeElements = null;
    let edgeElements = null;
    let labelElements = null;
    let edgeLabelElements = null;

    const typeColors = {
      schema: '#3b82f6',
      service: '#8b5cf6',
      api: '#14b8a6',
      dependency: '#f59e0b',
    };

    const edgeDashPatterns = {
      depends_on: '0',
      data_access: '6,3',
      handler: '2,2',
      relationship: '0',
      data_flow: '8,4',
    };

    const edgeColors = {
      depends_on: 'rgba(139, 92, 246, 0.4)',
      data_access: 'rgba(59, 130, 246, 0.4)',
      handler: 'rgba(20, 184, 166, 0.4)',
      relationship: 'rgba(59, 130, 246, 0.3)',
      data_flow: 'rgba(236, 72, 153, 0.4)',
    };

    const nodeTypes = ref([
      { key: 'schema', label: 'Schemas', visible: true },
      { key: 'service', label: 'Services', visible: true },
      { key: 'api', label: 'APIs', visible: true },
      { key: 'dependency', label: 'Dependencies', visible: true },
    ]);

    const typeCounts = computed(() => {
      if (!graphData.value) return {};
      const counts = {};
      for (const node of graphData.value.nodes) {
        counts[node.type] = (counts[node.type] || 0) + 1;
      }
      return counts;
    });

    const visibleTypes = computed(() => {
      return new Set(nodeTypes.value.filter(t => t.visible).map(t => t.key));
    });

    const isNodeVisible = (node) => {
      if (!visibleTypes.value.has(node.type)) return false;
      if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase();
        const label = (node.label || node.name || node.id || '').toLowerCase();
        return label.includes(q) || (node.id || '').toLowerCase().includes(q);
      }
      return true;
    };

    const visibleNodeIds = computed(() => {
      if (!graphData.value) return new Set();
      return new Set(graphData.value.nodes.filter(isNodeVisible).map(n => n.id));
    });

    const visibleNodeCount = computed(() => visibleNodeIds.value.size);

    const visibleEdgeCount = computed(() => {
      if (!graphData.value) return 0;
      return graphData.value.edges.filter(e => {
        const srcId = typeof e.source === 'object' ? e.source.id : e.source;
        const tgtId = typeof e.target === 'object' ? e.target.id : e.target;
        return visibleNodeIds.value.has(srcId) && visibleNodeIds.value.has(tgtId);
      }).length;
    });

    const selectedConnections = computed(() => {
      if (!selectedNode.value || !graphData.value) return { incoming: [], outgoing: [] };
      const nodeId = selectedNode.value.id;
      const nodeMap = {};
      for (const n of graphData.value.nodes) {
        nodeMap[n.id] = n;
      }
      const outgoing = [];
      const incoming = [];
      for (const e of graphData.value.edges) {
        const srcId = typeof e.source === 'object' ? e.source.id : e.source;
        const tgtId = typeof e.target === 'object' ? e.target.id : e.target;
        if (srcId === nodeId && nodeMap[tgtId]) {
          outgoing.push({
            targetId: tgtId,
            targetLabel: nodeMap[tgtId].label || nodeMap[tgtId].name || tgtId,
            label: e.label || e.type || '',
          });
        }
        if (tgtId === nodeId && nodeMap[srcId]) {
          incoming.push({
            sourceId: srcId,
            sourceLabel: nodeMap[srcId].label || nodeMap[srcId].name || srcId,
            label: e.label || e.type || '',
          });
        }
      }
      return { incoming, outgoing };
    });

    const detailRoute = computed(() => {
      if (!selectedNode.value) return null;
      const n = selectedNode.value;
      const name = encodeURIComponent(n.label || n.name || n.id);
      switch (n.type) {
        case 'schema': return `/schemas/${name}`;
        case 'service': return `/services/${name}`;
        case 'api': return '/apis';
        case 'dependency': return '/dependencies';
        default: return null;
      }
    });

    function selectNodeById(id) {
      if (!graphData.value) return;
      const node = graphData.value.nodes.find(n => n.id === id);
      if (node) {
        selectedNode.value = node;
        highlightConnected(node);
      }
    }

    async function fetchData() {
      loading.value = true;
      error.value = null;
      try {
        const data = await api.graph();
        // Normalize: ensure nodes have label field
        const nodes = (data.nodes || []).map(n => ({
          ...n,
          label: n.label || n.name || n.id,
        }));
        const edges = (data.links || data.edges || []).map(e => ({ ...e }));
        graphData.value = { nodes, edges };
        await nextTick();
        if (nodes.length > 0) {
          initGraph();
          // Focus on a specific node if requested via query param (e.g. ?focus=schema:User)
          const focusId = route.query.focus;
          if (focusId) {
            // Allow the simulation to settle a bit before zooming
            setTimeout(() => {
              const node = graphData.value.nodes.find(n => n.id === focusId);
              if (node) {
                zoomToNode(node);
              }
            }, 800);
          }
        }
      } catch (e) {
        error.value = e.message || 'Failed to load graph data';
      } finally {
        loading.value = false;
      }
    }

    function initGraph() {
      if (!graphContainer.value || !graphData.value) return;

      // Clear previous
      if (simulation) simulation.stop();
      d3.select(graphContainer.value).selectAll('*').remove();

      const container = graphContainer.value;
      const width = container.clientWidth;
      const height = container.clientHeight;

      // Build node connection count for sizing
      const connectionCount = {};
      for (const e of graphData.value.edges) {
        const src = typeof e.source === 'string' ? e.source : e.source.id;
        const tgt = typeof e.target === 'string' ? e.target : e.target.id;
        connectionCount[src] = (connectionCount[src] || 0) + 1;
        connectionCount[tgt] = (connectionCount[tgt] || 0) + 1;
      }

      const radiusScale = d3.scaleSqrt()
        .domain([0, d3.max(Object.values(connectionCount)) || 1])
        .range([8, 30]);

      // Create node objects with radius
      const nodes = graphData.value.nodes.map(n => ({
        ...n,
        radius: radiusScale(connectionCount[n.id] || 0),
      }));

      // Filter edges to only include those where both source and target exist
      const nodeIdSet = new Set(nodes.map(n => n.id));
      const edges = graphData.value.edges.filter(e => {
        const src = typeof e.source === 'string' ? e.source : e.source.id;
        const tgt = typeof e.target === 'string' ? e.target : e.target.id;
        return nodeIdSet.has(src) && nodeIdSet.has(tgt);
      }).map(e => ({ ...e }));

      // Store processed data back
      graphData.value.nodes = nodes;
      graphData.value.edges = edges;

      // SVG setup
      svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .style('background', 'transparent');

      // Defs for arrow markers
      const defs = svg.append('defs');
      Object.keys(edgeColors).forEach(type => {
        defs.append('marker')
          .attr('id', `arrow-${type}`)
          .attr('viewBox', '0 -5 10 10')
          .attr('refX', 20)
          .attr('refY', 0)
          .attr('markerWidth', 6)
          .attr('markerHeight', 6)
          .attr('orient', 'auto')
          .append('path')
          .attr('d', 'M0,-5L10,0L0,5')
          .attr('fill', edgeColors[type] || 'rgba(100,100,100,0.4)');
      });

      // Zoom behavior
      zoomBehavior = d3.zoom()
        .scaleExtent([0.1, 8])
        .on('zoom', (event) => {
          g.attr('transform', event.transform);
          currentZoomLevel.value = event.transform.k;
          updateLabelVisibility(event.transform.k);
        });

      svg.call(zoomBehavior);

      // Main group
      g = svg.append('g');

      // Edges
      edgeElements = g.append('g')
        .attr('class', 'edges')
        .selectAll('line')
        .data(edges)
        .join('line')
        .attr('stroke', d => edgeColors[d.type] || 'rgba(100,100,100,0.3)')
        .attr('stroke-width', 1.5)
        .attr('stroke-dasharray', d => edgeDashPatterns[d.type] || '0')
        .attr('marker-end', d => `url(#arrow-${d.type})`)
        .style('opacity', 1);

      // Edge labels (hidden by default, shown on hover)
      edgeLabelElements = g.append('g')
        .attr('class', 'edge-labels')
        .selectAll('text')
        .data(edges)
        .join('text')
        .attr('class', 'graph-edge-label')
        .text(d => d.label || d.type || '')
        .attr('text-anchor', 'middle')
        .style('opacity', 0)
        .style('pointer-events', 'none');

      // Nodes
      nodeElements = g.append('g')
        .attr('class', 'nodes')
        .selectAll('circle')
        .data(nodes)
        .join('circle')
        .attr('r', d => d.radius)
        .attr('fill', d => typeColors[d.type] || '#6b7280')
        .attr('stroke', d => {
          const c = d3.color(typeColors[d.type] || '#6b7280');
          return c ? c.brighter(0.5).toString() : '#9ca3af';
        })
        .attr('stroke-width', 1.5)
        .attr('class', 'graph-node')
        .style('opacity', 1)
        .on('click', (event, d) => {
          event.stopPropagation();
          selectedNode.value = d;
          highlightConnected(d);
        })
        .on('dblclick', (event, d) => {
          event.stopPropagation();
          zoomToNode(d);
        })
        .on('mouseenter', (event, d) => {
          if (!selectedNode.value) {
            highlightConnected(d);
          }
          showEdgeLabelsFor(d);
        })
        .on('mouseleave', () => {
          if (!selectedNode.value) {
            resetHighlight();
          }
          hideEdgeLabels();
        })
        .call(d3.drag()
          .on('start', dragStarted)
          .on('drag', dragged)
          .on('end', dragEnded)
        );

      // Labels
      labelElements = g.append('g')
        .attr('class', 'labels')
        .selectAll('text')
        .data(nodes)
        .join('text')
        .attr('class', 'graph-node-label')
        .text(d => d.label || d.name || d.id)
        .attr('dy', d => d.radius + 14)
        .style('opacity', 0)
        .style('pointer-events', 'none');

      // Force simulation
      simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(edges)
          .id(d => d.id)
          .distance(d => {
            const distances = { depends_on: 120, data_access: 100, handler: 80, relationship: 90, data_flow: 110 };
            return distances[d.type] || 100;
          })
        )
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide().radius(d => d.radius + 10))
        .alphaDecay(0.02)
        .on('tick', ticked);

      // Click on background to deselect
      svg.on('click', () => {
        selectedNode.value = null;
        resetHighlight();
      });
    }

    function ticked() {
      edgeElements
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      edgeLabelElements
        .attr('x', d => (d.source.x + d.target.x) / 2)
        .attr('y', d => (d.source.y + d.target.y) / 2);

      nodeElements
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);

      labelElements
        .attr('x', d => d.x)
        .attr('y', d => d.y);
    }

    function updateLabelVisibility(zoomLevel) {
      if (!labelElements) return;
      labelElements.style('opacity', zoomLevel > 1.5 ? 0.9 : 0);
    }

    function highlightConnected(node) {
      if (!graphData.value || !nodeElements || !edgeElements) return;
      const connectedIds = new Set([node.id]);
      for (const e of graphData.value.edges) {
        const srcId = typeof e.source === 'object' ? e.source.id : e.source;
        const tgtId = typeof e.target === 'object' ? e.target.id : e.target;
        if (srcId === node.id) connectedIds.add(tgtId);
        if (tgtId === node.id) connectedIds.add(srcId);
      }

      nodeElements.style('opacity', d => connectedIds.has(d.id) ? 1 : 0.15);
      edgeElements.style('opacity', d => {
        const srcId = typeof d.source === 'object' ? d.source.id : d.source;
        const tgtId = typeof d.target === 'object' ? d.target.id : d.target;
        return (srcId === node.id || tgtId === node.id) ? 0.8 : 0.05;
      });
      labelElements.style('opacity', d => connectedIds.has(d.id) ? 0.9 : 0);
    }

    function resetHighlight() {
      if (!nodeElements || !edgeElements || !labelElements) return;
      nodeElements.style('opacity', d => isNodeVisible(d) ? 1 : 0);
      edgeElements.style('opacity', d => {
        const srcId = typeof d.source === 'object' ? d.source.id : d.source;
        const tgtId = typeof d.target === 'object' ? d.target.id : d.target;
        return visibleNodeIds.value.has(srcId) && visibleNodeIds.value.has(tgtId) ? 1 : 0;
      });
      labelElements.style('opacity', currentZoomLevel.value > 1.5 ? (d => isNodeVisible(d) ? 0.9 : 0) : 0);
    }

    function showEdgeLabelsFor(node) {
      if (!edgeLabelElements) return;
      edgeLabelElements.style('opacity', d => {
        const srcId = typeof d.source === 'object' ? d.source.id : d.source;
        const tgtId = typeof d.target === 'object' ? d.target.id : d.target;
        return (srcId === node.id || tgtId === node.id) ? 0.8 : 0;
      });
    }

    function hideEdgeLabels() {
      if (!edgeLabelElements) return;
      edgeLabelElements.style('opacity', 0);
    }

    function zoomToNode(node) {
      if (!svg || !zoomBehavior) return;
      const container = graphContainer.value;
      const width = container.clientWidth;
      const height = container.clientHeight;
      const scale = 2.5;
      const transform = d3.zoomIdentity
        .translate(width / 2 - node.x * scale, height / 2 - node.y * scale)
        .scale(scale);
      svg.transition().duration(750).call(zoomBehavior.transform, transform);
      selectedNode.value = node;
      highlightConnected(node);
    }

    function resetZoom() {
      if (!svg || !zoomBehavior) return;
      svg.transition().duration(500).call(zoomBehavior.transform, d3.zoomIdentity);
    }

    function centerGraph() {
      if (!svg || !zoomBehavior || !graphData.value) return;
      const container = graphContainer.value;
      const width = container.clientWidth;
      const height = container.clientHeight;
      const nodes = graphData.value.nodes;
      if (nodes.length === 0) return;

      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      for (const n of nodes) {
        if (n.x != null) {
          if (n.x < minX) minX = n.x;
          if (n.x > maxX) maxX = n.x;
        }
        if (n.y != null) {
          if (n.y < minY) minY = n.y;
          if (n.y > maxY) maxY = n.y;
        }
      }
      if (!isFinite(minX)) return;

      const graphWidth = maxX - minX;
      const graphHeight = maxY - minY;
      const midX = (minX + maxX) / 2;
      const midY = (minY + maxY) / 2;
      const scale = Math.min(
        0.9 * width / (graphWidth || 1),
        0.9 * height / (graphHeight || 1),
        2
      );
      const transform = d3.zoomIdentity
        .translate(width / 2 - midX * scale, height / 2 - midY * scale)
        .scale(scale);
      svg.transition().duration(500).call(zoomBehavior.transform, transform);
    }

    function dragStarted(event, d) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event, d) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragEnded(event, d) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }

    // Watch filters and search to update visibility
    watch([visibleTypes, searchQuery], () => {
      if (!nodeElements || !edgeElements || !labelElements) return;
      nodeElements.style('opacity', d => isNodeVisible(d) ? 1 : 0);
      edgeElements.style('opacity', d => {
        const srcId = typeof d.source === 'object' ? d.source.id : d.source;
        const tgtId = typeof d.target === 'object' ? d.target.id : d.target;
        return visibleNodeIds.value.has(srcId) && visibleNodeIds.value.has(tgtId) ? 1 : 0;
      });
      labelElements.style('opacity', d => {
        if (!isNodeVisible(d)) return 0;
        return currentZoomLevel.value > 1.5 ? 0.9 : 0;
      });
    }, { deep: true });

    // Handle resize
    let resizeObserver = null;

    onMounted(() => {
      fetchData();
      resizeObserver = new ResizeObserver(() => {
        if (!svg || !graphContainer.value) return;
        const w = graphContainer.value.clientWidth;
        const h = graphContainer.value.clientHeight;
        svg.attr('width', w).attr('height', h);
      });
      if (graphContainer.value) {
        resizeObserver.observe(graphContainer.value);
      }
    });

    onUnmounted(() => {
      if (simulation) simulation.stop();
      if (resizeObserver) resizeObserver.disconnect();
    });

    return {
      graphContainer,
      loading,
      error,
      graphData,
      selectedNode,
      searchQuery,
      nodeTypes,
      typeColors,
      typeCounts,
      visibleNodeCount,
      visibleEdgeCount,
      selectedConnections,
      detailRoute,
      router,
      fetchData,
      resetZoom,
      centerGraph,
      selectNodeById,
      resetHighlight,
    };
  },
};
