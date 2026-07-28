const API_BASE = 'http://localhost:8000/api';

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

  const response = await fetch(url, config);

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
  list: () => request('/resumes'),
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
  suggest: (data) => request('/ai/suggest', { method: 'POST', body: data }),
  optimize: (resumeVersionId, jobDescription, context = {}) => request('/ai/optimize', {
    method: 'POST',
    body: {
      resume_version_id: resumeVersionId,
      job_description: jobDescription,
      target_role: context.targetRole || null,
      company: context.company || null,
      instructions: context.instructions || null,
    },
  }),
};

export const coverLetterApi = {
  list: () => request('/cover-letters'),
  get: (id) => request(`/cover-letters/${id}`),
  analyze: (data) => request('/cover-letters/analyze', { method: 'POST', body: data }),
  research: (data) => request('/cover-letters/research', { method: 'POST', body: data }),
  generate: (data) => request('/cover-letters/generate', { method: 'POST', body: data }),
  update: (id, data) => request(`/cover-letters/${id}`, { method: 'PUT', body: data }),
  delete: (id) => request(`/cover-letters/${id}`, { method: 'DELETE' }),
  getPreviewUrl: (id, cacheKey = 0) => `${API_BASE}/cover-letters/${id}/pdf?t=${cacheKey}`,
  getDownloadUrl: (id) => `${API_BASE}/cover-letters/${id}/pdf?download=true`,
};

export const companyResearchApi = {
  list: () => request('/company-research'),
  get: (id) => request(`/company-research/${id}`),
  research: (data) => request('/company-research/research', { method: 'POST', body: data }),
  delete: (id) => request(`/company-research/${id}`, { method: 'DELETE' }),
};

// Photo endpoints
export const photoApi = {
  upload: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return request('/photos/upload', { method: 'POST', body: formData });
  },
  getCurrentUrl: () => `${API_BASE}/photos/current`,
};
