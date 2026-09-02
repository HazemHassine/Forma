// Relative requests work in Docker, local Vite development, and deployments
// behind a reverse proxy. Set VITE_API_BASE only for a deliberately separate API.
const API_BASE = (import.meta.env?.VITE_API_BASE || '/api').replace(/\/$/, '');
const AI_PROVIDERS = new Set(['gemini', 'chatgpt']);

function aiProviderPath(provider) {
  if (!AI_PROVIDERS.has(provider)) {
    throw new Error(`Unsupported AI provider: ${provider}`);
  }
  return `/ai/${provider}`;
}

function aiProviderSegment(provider) {
  aiProviderPath(provider);
  return provider;
}

function formatValidationIssue(issue) {
  if (typeof issue === 'string') return issue;
  if (!issue || typeof issue !== 'object') return String(issue || '');

  const message = issue.msg || issue.message;
  const field = Array.isArray(issue.loc)
    ? issue.loc
      .filter(part => part !== 'body')
      .map(part => String(part).replaceAll('_', ' '))
      .join(' → ')
    : '';

  if (message) {
    return field ? `${field}: ${message}` : message;
  }

  return JSON.stringify(issue);
}

export function formatApiError(errorData, status) {
  const detail = errorData?.detail ?? errorData?.message;

  if (Array.isArray(detail)) {
    const message = detail.map(formatValidationIssue).filter(Boolean).join('; ');
    if (message) return message;
  }

  if (typeof detail === 'string' && detail.trim()) return detail;

  if (detail && typeof detail === 'object') {
    const message = formatValidationIssue(detail);
    if (message) return message;
  }

  return `Request failed with status ${status}`;
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
    config.body = JSON.stringify(config.body);
  }

  if (config.body instanceof FormData) {
    delete config.headers['Content-Type'];
  }

  let response;
  try {
    response = await fetch(url, config);
  } catch (error) {
    throw new Error(
      `Cannot reach the Forma backend. Check that it is running and healthy. (${error.message})`,
      { cause: error },
    );
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = formatApiError(errorData, response.status);
    throw new Error(message);
  }

  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }

  return response;
}

// Resume endpoints
export const resumeApi = {
  templates: () => request('/resumes/templates'),
  list: () => request('/resumes'),
  listVersions: () => request('/resumes'),
  get: (id) => request(`/resumes/${id}`),
  create: (data) => request('/resumes', { method: 'POST', body: data }),
  update: (id, data) => request(`/resumes/${id}`, { method: 'PUT', body: data }),
  delete: (id) => request(`/resumes/${id}`, { method: 'DELETE' }),
  duplicate: (id, name) => request(`/resumes/${id}/duplicate`, { method: 'POST', body: { name } }),
  setCurrent: (id) => request(`/resumes/${id}/set-current`, { method: 'POST' }),
  getPreviewUrl: (id) => `${API_BASE}/resumes/${id}/preview`,
  getDownloadUrl: (id) => `${API_BASE}/resumes/${id}/pdf`,
};

// Job endpoints
export const jobApi = {
  list: () => request('/jobs'),
  get: (id) => request(`/jobs/${id}`),
  create: (data) => request('/jobs', { method: 'POST', body: data }),
  update: (id, data) => request(`/jobs/${id}`, { method: 'PUT', body: data }),
  delete: (id) => request(`/jobs/${id}`, { method: 'DELETE' }),
  stats: () => request('/jobs/stats'),
};

// AI endpoints
export const aiApi = {
  suggest: (provider, data) => request(`${aiProviderPath(provider)}/suggest`, {
    method: 'POST',
    body: {
      section_type: data.section_type,
      current_content: data.current_content,
      job_description: data.job_description || null,
      feedback: data.feedback || null,
      include_context: data.include_context !== false,
    },
  }),
  optimize: (provider, resumeVersionId, jobDescription, context = {}) => request(`${aiProviderPath(provider)}/optimize`, {
    method: 'POST',
    body: {
      resume_version_id: resumeVersionId,
      job_description: jobDescription,
      target_role: context.targetRole || null,
      company: context.company || null,
      instructions: context.instructions || null,
      include_context: context.includeContext !== false,
    },
  }),
};

export const coverLetterApi = {
  list: () => request('/cover-letters'),
  get: (id) => request(`/cover-letters/${id}`),
  analyze: (provider, data) => request(`/cover-letters/${aiProviderSegment(provider)}/analyze`, { method: 'POST', body: data }),
  research: (provider, data) => request(`/cover-letters/${aiProviderSegment(provider)}/research`, { method: 'POST', body: data }),
  generate: (provider, data) => request(`/cover-letters/${aiProviderSegment(provider)}/generate`, { method: 'POST', body: data }),
  update: (id, data) => request(`/cover-letters/${id}`, { method: 'PUT', body: data }),
  delete: (id) => request(`/cover-letters/${id}`, { method: 'DELETE' }),
  getPreviewUrl: (id, cacheKey = 0) => `${API_BASE}/cover-letters/${id}/pdf?t=${cacheKey}`,
  getDownloadUrl: (id) => `${API_BASE}/cover-letters/${id}/pdf?download=true`,
};

export const companyResearchApi = {
  list: () => request('/company-research'),
  get: (id) => request(`/company-research/${id}`),
  research: (provider, data) => request(`/company-research/${aiProviderSegment(provider)}/research`, { method: 'POST', body: data }),
  delete: (id) => request(`/company-research/${id}`, { method: 'DELETE' }),
};

// Photo endpoints
export const photoApi = {
  upload: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return request('/photos/upload', { method: 'POST', body: formData });
  },
  getUrl: (path) => path || '',
};

export const critiqueApi = {
  create: (provider, data) => request(`/cv-critique/${aiProviderSegment(provider)}`, {
    method: 'POST',
    body: {
      resume_version_id: data.resume_version_id,
      target_role: data.target_role || null,
      job_description: data.job_description || null,
      instructions: data.instructions || null,
      include_context: data.include_context !== false,
    },
  }),
  listForVersion: (versionId) => request(`/cv-critique/version/${versionId}`),
  get: (id) => request(`/cv-critique/${id}`),
  delete: (id) => request(`/cv-critique/${id}`, { method: 'DELETE' }),
};

export const contextApi = {
  listSources: (activeOnly = false) => request(`/context/sources?active_only=${activeOnly}`),
  addSource: (data) => request('/context/sources', { method: 'POST', body: data }),
  getSource: (id) => request(`/context/sources/${id}`),
  updateSource: (id, data) => request(`/context/sources/${id}`, { method: 'PUT', body: data }),
  deleteSource: (id) => request(`/context/sources/${id}`, { method: 'DELETE' }),

  listItems: (params = {}) => {
    const search = new URLSearchParams();
    if (params.category && params.category !== 'all') search.set('category', params.category);
    if (params.activeOnly) search.set('active_only', 'true');
    if (params.query) search.set('query', params.query);
    const qs = search.toString();
    return request(`/context/items${qs ? `?${qs}` : ''}`);
  },
  addItem: (data) => request('/context/items', { method: 'POST', body: data }),
  getItem: (id) => request(`/context/items/${id}`),
  updateItem: (id, data) => request(`/context/items/${id}`, { method: 'PUT', body: data }),
  toggleItem: (id) => request(`/context/items/${id}/toggle`, { method: 'POST' }),
  deleteItem: (id) => request(`/context/items/${id}`, { method: 'DELETE' }),

  getProfile: () => request('/context/profile'),
  getStats: () => request('/context/stats'),
  synthesize: (provider, data = {}) => request(`/context/${aiProviderSegment(provider)}/synthesize`, {
    method: 'POST',
    body: data,
  }),
  preview: (params = {}) => {
    const search = new URLSearchParams();
    if (params.targetRole) search.set('target_role', params.targetRole);
    if (params.jobDescription) search.set('job_description', params.jobDescription);
    if (params.company) search.set('company', params.company);
    if (params.maxItems) search.set('max_items', params.maxItems);
    const qs = search.toString();
    return request(`/context/preview${qs ? `?${qs}` : ''}`);
  },
  importResume: (resumeId) => request(`/context/import-resume/${resumeId}`, { method: 'POST' }),
};

export const systemApi = {
  status: () => request('/system/status'),
};
