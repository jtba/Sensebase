// ============================================================
// SenseBase - API Client
// ============================================================

const BASE = '';  // Same origin

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

async function postJSON(url, body = {}) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

async function putJSON(url, body = {}) {
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

async function deleteJSON(url) {
  const res = await fetch(url, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  health: () => fetchJSON(`${BASE}/health`),

  stats: () => fetchJSON(`${BASE}/stats`),

  search: (q, { limit = 20, type = '', repo = '' } = {}) =>
    fetchJSON(`${BASE}/search?q=${encodeURIComponent(q)}&limit=${limit}${type ? `&type=${type}` : ''}${repo ? `&repo=${repo}` : ''}`),

  semanticSearch: (q, { limit = 10, type = '', repo = '' } = {}) =>
    fetchJSON(`${BASE}/semantic/search?q=${encodeURIComponent(q)}&limit=${limit}${type ? `&type=${type}` : ''}${repo ? `&repo=${repo}` : ''}`),

  ask: (q, limit = 5) =>
    fetchJSON(`${BASE}/ask?q=${encodeURIComponent(q)}&limit=${limit}`),

  schemas: (params = {}) =>
    fetchJSON(`${BASE}/schemas?${new URLSearchParams(params)}`),

  schema: (name) =>
    fetchJSON(`${BASE}/schemas/${encodeURIComponent(name)}`),

  schemaRelationships: (name) =>
    fetchJSON(`${BASE}/schemas/${encodeURIComponent(name)}/relationships`),

  services: (params = {}) =>
    fetchJSON(`${BASE}/services?${new URLSearchParams(params)}`),

  service: (name) =>
    fetchJSON(`${BASE}/services/${encodeURIComponent(name)}`),

  serviceDependencies: (name) =>
    fetchJSON(`${BASE}/services/${encodeURIComponent(name)}/dependencies`),

  apis: (params = {}) =>
    fetchJSON(`${BASE}/apis?${new URLSearchParams(params)}`),

  dependencies: (params = {}) =>
    fetchJSON(`${BASE}/dependencies?${new URLSearchParams(params)}`),

  dependencyUsage: (name) =>
    fetchJSON(`${BASE}/dependencies/${encodeURIComponent(name)}/usage`),

  graph: () => fetchJSON(`${BASE}/graph/data`),

  repos: () => fetchJSON(`${BASE}/repos`),

  dataFlows: () => fetchJSON(`${BASE}/data-flows`),

  semanticStats: () => fetchJSON(`${BASE}/semantic/stats`),

  crawlStart: (useLlm = false) => postJSON(`${BASE}/crawl/start`, { use_llm: useLlm }),
  crawlStatus: () => fetchJSON(`${BASE}/crawl/status`),
  crawlStream: () => new EventSource(`${BASE}/crawl/stream`),

  localDirs: () => fetchJSON(`${BASE}/config/local-dirs`),
  updateLocalDirs: (dirs) => putJSON(`${BASE}/config/local-dirs`, { dirs }),

  llmConfig: () => fetchJSON(`${BASE}/config/llm`),
  updateLlmConfig: (data) => putJSON(`${BASE}/config/llm`, data),

  sources: () => fetchJSON(`${BASE}/config/sources`),
  addSource: (source) => postJSON(`${BASE}/config/sources`, { source }),
  removeSource: (type) => deleteJSON(`${BASE}/config/sources/${encodeURIComponent(type)}`),

  repoContext: (name) =>
    fetchJSON(`${BASE}/repos/${encodeURIComponent(name)}/context`),

  contexts: () => fetchJSON(`${BASE}/contexts`),

  relationships: () => fetchJSON(`${BASE}/relationships`),

  semanticGlossary: () => fetchJSON(`${BASE}/semantic/glossary`),
  queryRecipes: (params = {}) => fetchJSON(`${BASE}/semantic/recipes?${new URLSearchParams(params)}`),
  repoSemantic: (name) => fetchJSON(`${BASE}/repos/${encodeURIComponent(name)}/semantic`),
};
