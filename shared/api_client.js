(function (global) {
  const DEFAULT_API_BASE = 'http://localhost:5000';

  function normalizeApiBase(base) {
    return String(base || DEFAULT_API_BASE).trim().replace(/\/+$/, '') || DEFAULT_API_BASE;
  }

  function readStoredString(primaryKey, legacyKeys) {
    const keys = [primaryKey].concat(legacyKeys || []).filter(Boolean);
    for (const key of keys) {
      const value = global.localStorage.getItem(key);
      if (value !== null && value !== '') return value;
    }
    return '';
  }

  function readStoredFlag(primaryKey, legacyKeys) {
    const keys = [primaryKey].concat(legacyKeys || []).filter(Boolean);
    for (const key of keys) {
      const value = global.localStorage.getItem(key);
      if (value === '1') return true;
      if (value !== null) return false;
    }
    return false;
  }

  function hasHeader(headers, name) {
    const needle = String(name || '').toLowerCase();
    return Object.keys(headers || {}).some((key) => String(key).toLowerCase() === needle);
  }

  function createStoredClient(options) {
    const config = options || {};
    if (!config.apiBaseKey) {
      throw new Error('apiBaseKey is required');
    }

    const apiBaseKey = config.apiBaseKey;
    const adminKeyKey = config.adminKeyKey || 'adminKey';
    const adminModeKey = config.adminModeKey || 'adminMode';
    const legacyAdminKeyKeys = config.legacyAdminKeyKeys || [];
    const legacyAdminModeKeys = config.legacyAdminModeKeys || [];

    let apiBase = normalizeApiBase(readStoredString(apiBaseKey));
    let adminKey = String(readStoredString(adminKeyKey, legacyAdminKeyKeys) || '').trim();
    let adminLocal = readStoredFlag(adminModeKey, legacyAdminModeKeys);

    global.localStorage.setItem(apiBaseKey, apiBase);
    if (adminKey) global.localStorage.setItem(adminKeyKey, adminKey);
    if (adminLocal) global.localStorage.setItem(adminModeKey, '1');

    function origin() {
      return apiBase;
    }

    function resolveUrl(path) {
      if (!path) return origin();
      if (/^https?:/i.test(path)) return path;
      return origin() + (path.startsWith('/') ? path : `/${path}`);
    }

    function authHeaders(extra) {
      const headers = { ...(extra || {}) };
      if (adminKey && !hasHeader(headers, 'X-API-Key')) headers['X-API-Key'] = adminKey;
      if (adminLocal && !hasHeader(headers, 'X-Admin-Local')) headers['X-Admin-Local'] = '1';
      return headers;
    }

    return {
      getApiBase() {
        return apiBase;
      },

      setApiBase(nextBase) {
        apiBase = normalizeApiBase(nextBase);
        global.localStorage.setItem(apiBaseKey, apiBase);
        return apiBase;
      },

      getAdminKey() {
        return adminKey;
      },

      setAdminKey(nextKey) {
        adminKey = String(nextKey || '').trim();
        if (adminKey) global.localStorage.setItem(adminKeyKey, adminKey);
        else global.localStorage.removeItem(adminKeyKey);
        return adminKey;
      },

      getAdminLocal() {
        return adminLocal;
      },

      setAdminLocal(nextValue) {
        adminLocal = !!nextValue;
        if (adminLocal) global.localStorage.setItem(adminModeKey, '1');
        else global.localStorage.removeItem(adminModeKey);
        return adminLocal;
      },

      origin,
      resolveUrl,

      headers(extra) {
        return authHeaders(extra);
      },

      jsonHeaders(extra) {
        const headers = authHeaders(extra);
        if (!hasHeader(headers, 'Content-Type')) headers['Content-Type'] = 'application/json';
        return headers;
      },

      async request(path, options) {
        const init = { ...(options || {}) };
        init.headers = authHeaders(init.headers || {});
        if (init.body !== undefined && init.body !== null && !(init.body instanceof global.FormData) && !hasHeader(init.headers, 'Content-Type')) {
          init.headers['Content-Type'] = 'application/json';
        }
        const response = await global.fetch(resolveUrl(path), init);
        const text = await response.text();
        let payload = null;
        try {
          payload = text ? JSON.parse(text) : null;
        } catch (error) {
          payload = text;
        }
        if (!response.ok || (payload && payload.ok === false)) {
          throw new Error(payload?.error || `Request failed (${response.status})`);
        }
        return payload?.data ?? payload;
      }
    };
  }

  global.NHTApi = {
    DEFAULT_API_BASE,
    normalizeApiBase,
    createStoredClient
  };
})(window);
