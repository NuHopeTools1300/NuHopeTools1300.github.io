(function (global) {
  function readWorkspaceZoom(storageKey, defaultZoom) {
    const fallback = Number(defaultZoom) || 100;
    const stored = Number(global.localStorage.getItem(storageKey) || fallback);
    return stored === 80 ? 100 : stored;
  }

  function applyWorkspaceZoom(options) {
    const config = options || {};
    const min = Number(config.minZoom) || 80;
    const max = Number(config.maxZoom) || 140;
    const baseScale = Number(config.baseScale) || 1;
    const requestedZoom = Number(config.zoom);
    const zoom = Math.max(min, Math.min(max, Number.isFinite(requestedZoom) ? requestedZoom : 100));

    if (config.storageKey) {
      global.localStorage.setItem(config.storageKey, String(zoom));
    }

    if (config.appRoot) {
      const calibratedScale = (zoom / 100) * baseScale;
      config.appRoot.style.setProperty('--workspace-zoom', String(calibratedScale));
    }

    if (config.slider) config.slider.value = String(zoom);
    if (config.readout) config.readout.textContent = `${zoom}%`;
    return zoom;
  }

  function bindTopbarApiControls(options) {
    const config = options || {};
    const apiClient = config.apiClient;
    const apiBaseInput = config.apiBaseInput;
    const apiSaveButton = config.apiSaveButton;
    const adminKeyButton = config.adminKeyButton;
    const adminLocalCheckbox = config.adminLocalCheckbox;

    if (!apiClient || !apiBaseInput || !apiSaveButton || !adminKeyButton || !adminLocalCheckbox) {
      throw new Error('bindTopbarApiControls requires apiClient, apiBaseInput, apiSaveButton, adminKeyButton, and adminLocalCheckbox');
    }

    apiBaseInput.value = config.initialApiBase || apiClient.getApiBase();
    adminLocalCheckbox.checked = !!config.initialAdminLocal;

    apiSaveButton.addEventListener('click', () => {
      const nextBase = apiClient.setApiBase(apiBaseInput.value.trim() || global.NHTApi.DEFAULT_API_BASE);
      if (typeof config.onApiSaved === 'function') config.onApiSaved(nextBase);
    });

    adminKeyButton.addEventListener('click', () => {
      const current = typeof config.getCurrentAdminKey === 'function'
        ? config.getCurrentAdminKey()
        : (apiClient.getAdminKey() || '');
      const promptMessage = config.adminKeyPrompt || 'Admin API key';
      const value = global.prompt(promptMessage, current || '');
      if (value === null) return;
      const nextKey = apiClient.setAdminKey(value);
      if (typeof config.onAdminKeySaved === 'function') config.onAdminKeySaved(nextKey);
    });

    adminLocalCheckbox.addEventListener('change', (event) => {
      const nextValue = apiClient.setAdminLocal(event.target.checked);
      if (typeof config.onAdminLocalChanged === 'function') config.onAdminLocalChanged(nextValue);
    });
  }

  global.NHTUI = {
    readWorkspaceZoom,
    applyWorkspaceZoom,
    bindTopbarApiControls
  };
})(window);
