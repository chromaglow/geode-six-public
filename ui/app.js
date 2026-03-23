/**
 * Geode Six — Web UI Application
 * Vanilla JS — handles Assistant, Upload, Browse, Search sections.
 * v2: Dynamic codes, tier toggles, new folder creation, scope filtering.
 */

(() => {
    'use strict';

    // =====================================================================
    // Configuration
    // =====================================================================
    const API_BASE = window.location.origin;

    // =====================================================================
    // DOM References
    // =====================================================================
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // Navigation
    const navBtns = $$('.nav-btn');
    const sections = $$('.section');

    // Header
    const statusDot = $('.status-dot');
    const statusText = $('.status-text');

    // Assistant
    const chatContainer = $('#chat-container');
    const chatForm = $('#chat-form');
    const chatInput = $('#chat-input');
    const chatSubmit = $('#chat-submit');
    const modelSelect = $('#model-select');

    // Upload
    const dropZone = $('#drop-zone');
    const fileInput = $('#file-input');
    const uploadNote = $('#upload-note');
    const readyToShare = $('#ready-to-share');
    const versionHint = $('#version-hint');
    const uploadProgress = $('#upload-progress');
    const uploadFormContainer = $('#upload-form-container');

    // Single Confirmation
    const singleConfirmContainer = $('#single-confirm-container');
    const confirmOriginalName = $('#confirm-original-name');
    const confirmDateWarning = $('#confirm-date-warning');
    const confirmDuplicateWarning = $('#confirm-duplicate-warning');
    const confirmProject = $('#confirm-project');
    const confirmType = $('#confirm-type');
    const confirmDescription = $('#confirm-description');
    const confirmDate = $('#confirm-date');
    const confirmVersion = $('#confirm-version');
    const confirmReadyToShare = $('#confirm-ready-to-share');
    const confirmPreviewName = $('#confirm-preview-name');
    const confirmCancel = $('#confirm-cancel');
    const confirmSubmitBtn = $('#confirm-submit');

    // Single New folder inline form
    const newFolderToggleLink = $('#new-folder-toggle-link');
    const newFolderInline = $('#new-folder-inline');
    const newFolderName = $('#new-folder-name');
    const newFolderCode = $('#new-folder-code');
    const newFolderTier = $('#new-folder-tier');
    const newFolderCancel = $('#new-folder-cancel');
    const newFolderSubmit = $('#new-folder-submit');
    const newFolderMsg = $('#new-folder-msg');

    // Batch Confirmation
    const batchConfirmContainer = $('#batch-confirm-container');
    const batchProgressText = $('#batch-progress-text');
    const confirmCardsWrapper = $('#confirm-cards-wrapper');
    const batchConfirmActions = $('#batch-confirm-actions');
    const batchConfirmCancelBtn = $('#batch-confirm-cancel');
    const batchConfirmSubmitBtn = $('#batch-confirm-submit');
    const confirmCardTemplate = $('#confirm-card-template');

    // Upload success
    const uploadSuccess = $('#upload-success');
    const successFilename = $('#success-filename');
    const successPath = $('#success-path');
    const uploadAnother = $('#upload-another');

    // Browse
    const browseTierToggle = $('#browse-tier-toggle');
    const browseProjectFilter = $('#browse-project-filter');
    const browseTypeFilter = $('#browse-type-filter');
    const browseSort = $('#browse-sort');
    const browseRefresh = $('#browse-refresh');
    const browseFileList = $('#browse-file-list');

    // Search
    const searchScopeToggle = $('#search-scope-toggle');
    const searchForm = $('#search-form');
    const searchInput = $('#search-input');
    const searchSynthesize = $('#search-synthesize');
    const searchSummary = $('#search-summary');
    const searchResults = $('#search-results');

    // State
    let currentTempId = null;
    let currentUploadExt = '';
    let currentUploadTier = 'Projects';
    let currentBatch = [];
    let codesData = null;  // cached codes.json
    let browseTier = 'All';
    let searchScope = 'All';

    // =====================================================================
    // Navigation
    // =====================================================================
    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const section = btn.dataset.section;
            navBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            sections.forEach(s => s.classList.remove('active'));
            $(`#section-${section}`).classList.add('active');

            // Load data when switching tabs
            if (section === 'browse') loadBrowse();
        });
    });

    // =====================================================================
    // Codes Loading (dynamic dropdowns)
    // =====================================================================
    async function loadCodes() {
        try {
            const resp = await fetch(`${API_BASE}/gca/codes`);
            codesData = await resp.json();
            populateProjectDropdown(confirmProject, null);
            populateBrowseProjectDropdown(null);
        } catch {
            // Fallback — leave dropdowns as-is
        }
    }

    function populateProjectDropdown(selectEl, filterTier) {
        if (!codesData) return;
        selectEl.innerHTML = '';

        for (const tier of ['Projects', 'Operations']) {
            if (filterTier && filterTier !== tier) continue;
            const tierCodes = codesData[tier] || {};
            if (Object.keys(tierCodes).length === 0) continue;

            const optgroup = document.createElement('optgroup');
            optgroup.label = tier;
            for (const [code, label] of Object.entries(tierCodes)) {
                const opt = document.createElement('option');
                opt.value = code;
                opt.textContent = `${code} — ${label}`;
                optgroup.appendChild(opt);
            }
            selectEl.appendChild(optgroup);
        }
    }

    function populateBrowseProjectDropdown(filterTier) {
        if (!codesData) return;
        browseProjectFilter.innerHTML = '<option value="">All Codes</option>';

        for (const tier of ['Projects', 'Operations']) {
            if (filterTier && filterTier !== tier) continue;
            const tierCodes = codesData[tier] || {};
            if (Object.keys(tierCodes).length === 0) continue;

            const appendTarget = (filterTier === null) 
                ? document.createElement('optgroup') 
                : browseProjectFilter;
            
            if (filterTier === null) {
                appendTarget.label = tier;
            }

            for (const [code, label] of Object.entries(tierCodes)) {
                const opt = document.createElement('option');
                opt.value = code;
                opt.textContent = `${code} — ${label}`;
                appendTarget.appendChild(opt);
            }

            if (filterTier === null) {
                browseProjectFilter.appendChild(appendTarget);
            }
        }
    }

    // Load codes on init
    loadCodes();

    // =====================================================================
    // Health Check
    // =====================================================================
    async function checkHealth() {
        try {
            const resp = await fetch(`${API_BASE}/health`);
            const data = await resp.json();
            statusDot.classList.add('online');
            statusDot.classList.remove('offline');
            statusText.textContent = `${data.ram_available_mb}MB RAM free`;
        } catch {
            statusDot.classList.add('offline');
            statusDot.classList.remove('online');
            statusText.textContent = 'Offline';
        }
    }

    checkHealth();
    setInterval(checkHealth, 30000);

    // =====================================================================
    // Assistant
    // =====================================================================
    function addChatMessage(text, role, model) {
        // Remove welcome message
        const welcome = chatContainer.querySelector('.chat-welcome');
        if (welcome) welcome.remove();

        const msg = document.createElement('div');
        msg.className = `chat-message ${role}`;

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.textContent = text;

        const meta = document.createElement('div');
        meta.className = 'chat-meta';
        const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        meta.textContent = role === 'assistant' ? `${model || 'AI'} · ${now}` : now;

        msg.appendChild(bubble);
        msg.appendChild(meta);
        chatContainer.appendChild(msg);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return msg;
    }

    function addTypingIndicator() {
        const msg = document.createElement('div');
        msg.className = 'chat-message assistant';
        msg.id = 'typing-indicator';

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble typing-indicator';
        bubble.innerHTML = '<span></span><span></span><span></span>';

        msg.appendChild(bubble);
        chatContainer.appendChild(msg);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function removeTypingIndicator() {
        const el = $('#typing-indicator');
        if (el) el.remove();
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const prompt = chatInput.value.trim();
        if (!prompt) return;

        addChatMessage(prompt, 'user');
        chatInput.value = '';
        chatInput.style.height = 'auto';
        chatSubmit.disabled = true;

        addTypingIndicator();

        try {
            const model = modelSelect.value;
            const sensitive = model === 'geode-dolphin';
            const resp = await fetch(`${API_BASE}/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt, user: 'admin', sensitive }),
            });

            removeTypingIndicator();

            if (resp.ok) {
                const data = await resp.json();
                addChatMessage(data.response, 'assistant', data.model);
            } else {
                const err = await resp.json();
                addChatMessage(err.detail || 'Error occurred.', 'assistant', 'System');
            }
        } catch {
            removeTypingIndicator();
            addChatMessage('Cannot connect to server.', 'assistant', 'System');
        }

        chatSubmit.disabled = false;
    });

    // Auto-resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    });

    // Enter to send (Shift+Enter for newline)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // =====================================================================
    // Upload — Drag & Drop
    // =====================================================================
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length === 1) handleSingleUpload(files[0]);
        else if (files.length > 1) handleBatchUpload(files);
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length === 1) handleSingleUpload(fileInput.files[0]);
        else if (fileInput.files.length > 1) handleBatchUpload(fileInput.files);
    });

    // Version hint toggle
    readyToShare.addEventListener('change', () => {
        versionHint.textContent = readyToShare.checked ? 'Ready (v1.0)' : 'Draft (v0.1)';
    });

    // =====================================================================
    // Upload — Single Process
    // =====================================================================
    async function handleSingleUpload(file) {
        uploadProgress.classList.remove('hidden');
        document.querySelector('#upload-progress .progress-text').textContent = 'Processing file...';

        const formData = new FormData();
        formData.append('file', file);
        if (uploadNote.value.trim()) formData.append('note', uploadNote.value.trim());
        formData.append('ready_to_share', readyToShare.checked);

        try {
            const resp = await fetch(`${API_BASE}/gca/upload`, {
                method: 'POST',
                body: formData,
            });

            uploadProgress.classList.add('hidden');

            if (resp.ok) {
                const data = await resp.json();
                showSingleConfirmation(data);
            } else {
                const err = await resp.json();
                alert(err.detail || 'Upload failed.');
                resetUpload();
            }
        } catch {
            uploadProgress.classList.add('hidden');
            alert('Cannot connect to server.');
            resetUpload();
        }
    }

    function showSingleConfirmation(data) {
        currentTempId = data.temp_id;
        currentUploadExt = data.original_filename.split('.').pop() || '';
        currentUploadTier = data.tier || 'Projects';

        uploadFormContainer.classList.add('hidden');
        singleConfirmContainer.classList.remove('hidden');
        batchConfirmContainer.classList.add('hidden');

        confirmOriginalName.textContent = data.original_filename;
        populateProjectDropdown(confirmProject, null);
        confirmProject.value = data.project || '';
        confirmType.value = data.type || '';
        confirmDescription.value = data.description || '';
        confirmDate.value = data.date || '';
        confirmVersion.value = data.version || '';

        if (data.date_estimated) {
            confirmDateWarning.classList.remove('hidden');
        } else {
            confirmDateWarning.classList.add('hidden');
        }

        if (data.duplicate_warning) {
            confirmDuplicateWarning.textContent = '⚠️ ' + data.duplicate_warning;
            confirmDuplicateWarning.classList.remove('hidden');
        } else {
            confirmDuplicateWarning.classList.add('hidden');
        }

        updateSinglePreview();
    }

    function updateSinglePreview() {
        if (!confirmProject) return;
        const p = confirmProject.value;
        const t = confirmType.value;
        const d = confirmDescription.value.replace(/\s/g, '');
        const dt = confirmDate.value;
        const v = confirmVersion.value;
        const ext = currentUploadExt ? `.${currentUploadExt}` : '';
        confirmPreviewName.textContent = `${p}_${t}_${d}_${dt}_v${v}${ext}`;
    }

    if (confirmProject) {
        [confirmProject, confirmType, confirmDescription, confirmDate, confirmVersion]
            .forEach(el => {
                el.addEventListener('input', updateSinglePreview);
                el.addEventListener('change', updateSinglePreview);
            });
    }

    if (confirmCancel) confirmCancel.addEventListener('click', resetUpload);

    if (confirmSubmitBtn) {
        confirmSubmitBtn.addEventListener('click', async () => {
            confirmSubmitBtn.disabled = true;
            confirmSubmitBtn.textContent = 'Saving...';

            let tier = currentUploadTier;
            if (codesData) {
                if (codesData.Projects && codesData.Projects[confirmProject.value]) tier = 'Projects';
                else if (codesData.Operations && codesData.Operations[confirmProject.value]) tier = 'Operations';
            }

            try {
                const resp = await fetch(`${API_BASE}/gca/confirm`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        temp_id: currentTempId,
                        tier: tier,
                        project: confirmProject.value,
                        type: confirmType.value,
                        description: confirmDescription.value.replace(/\s/g, ''),
                        date: confirmDate.value,
                        version: confirmVersion.value,
                        ready_to_share: confirmReadyToShare.checked,
                    }),
                });

                if (resp.ok) {
                    const data = await resp.json();
                    showUploadSuccess([{ original: data.original_filename, final: data.assigned_filename, path: data.stored_path, ok: true }]);
                } else {
                    const err = await resp.json();
                    alert(err.detail || 'Confirmation failed.');
                }
            } catch {
                alert('Cannot connect to server.');
            }

            confirmSubmitBtn.disabled = false;
            confirmSubmitBtn.textContent = 'Confirm & Save';
        });
    }

    // Single flow: New Folder
    if (newFolderToggleLink) {
        newFolderToggleLink.addEventListener('click', (e) => {
            e.preventDefault();
            newFolderInline.classList.remove('hidden');
            newFolderToggleLink.classList.add('hidden');
            newFolderMsg.classList.add('hidden');
        });

        newFolderCancel.addEventListener('click', (e) => {
            e.preventDefault();
            newFolderInline.classList.add('hidden');
            newFolderToggleLink.classList.remove('hidden');
            newFolderName.value = '';
            newFolderCode.value = '';
            newFolderMsg.classList.add('hidden');
        });

        newFolderCode.addEventListener('input', () => {
            newFolderCode.value = newFolderCode.value.replace(/[^a-zA-Z]/g, '').toUpperCase();
        });

        newFolderSubmit.addEventListener('click', async () => {
            const name = newFolderName.value.trim();
            const code = newFolderCode.value.trim();
            const tier = newFolderTier.value;

            if (!name || !code || code.length < 2) {
                newFolderMsg.textContent = 'Folder name and 2-4 letter code required.';
                newFolderMsg.className = 'new-folder-msg error';
                newFolderMsg.classList.remove('hidden');
                return;
            }

            newFolderSubmit.disabled = true;
            newFolderSubmit.textContent = '...';

            try {
                const resp = await fetch(`${API_BASE}/gca/folder/create`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, code, tier }),
                });

                if (resp.ok) {
                    codesData = await resp.json();
                    populateProjectDropdown(confirmProject, null);
                    populateBrowseProjectDropdown(null);
                    confirmProject.value = code;
                    
                    newFolderName.value = '';
                    newFolderCode.value = '';
                    updateSinglePreview();

                    newFolderMsg.textContent = 'Folder created successfully';
                    newFolderMsg.className = 'new-folder-msg'; 
                    newFolderMsg.classList.remove('hidden');

                    setTimeout(() => {
                        newFolderInline.classList.add('hidden');
                        newFolderToggleLink.classList.remove('hidden');
                        newFolderMsg.classList.add('hidden');
                    }, 3000);
                } else {
                    const err = await resp.json();
                    newFolderMsg.textContent = err.detail || 'Failed to create folder.';
                    newFolderMsg.className = 'new-folder-msg error';
                    newFolderMsg.classList.remove('hidden');
                }
            } catch {
                newFolderMsg.textContent = 'Cannot connect to server.';
                newFolderMsg.className = 'new-folder-msg error';
                newFolderMsg.classList.remove('hidden');
            }

            newFolderSubmit.disabled = false;
            newFolderSubmit.textContent = 'Submit';
        });
    }

    // =====================================================================
    // Upload — Batch Process
    // =====================================================================
    async function handleBatchUpload(files) {
        if (files.length > 5) {
            alert('Please select up to 5 files at a time');
            resetUpload();
            return;
        }

        uploadFormContainer.classList.add('hidden');
        singleConfirmContainer.classList.add('hidden');
        batchConfirmContainer.classList.remove('hidden');
        confirmCardsWrapper.innerHTML = '';
        batchConfirmActions.classList.add('hidden');
        
        batchProgressText.classList.remove('hidden');

        currentBatch = [];
        let localBatchCount = 0;

        // Process sequentially
        for (let i = 0; i < files.length; i++) {
            batchProgressText.textContent = `Processing file ${i + 1} of ${files.length}...`;
            
            const formData = new FormData();
            formData.append('file', files[i]);
            if (uploadNote.value.trim()) formData.append('note', uploadNote.value.trim());
            formData.append('ready_to_share', readyToShare.checked);

            try {
                const resp = await fetch(`${API_BASE}/gca/upload`, { method: 'POST', body: formData });
                if (resp.ok) {
                    const data = await resp.json();
                    currentBatch.push(data);
                    renderBatchCard(data, localBatchCount);
                    localBatchCount++;
                } else {
                    const err = await resp.json();
                    renderBatchErrorCard(files[i].name, err.detail || 'Upload failed');
                }
            } catch {
                renderBatchErrorCard(files[i].name, 'Cannot connect to server');
            }
        }
        
        batchProgressText.classList.add('hidden');
        
        if (localBatchCount > 0) {
            batchConfirmActions.classList.remove('hidden');
            batchConfirmCancelBtn.textContent = 'Cancel All';
            batchConfirmSubmitBtn.classList.remove('hidden');
        } else {
            // All failed — provide a reset button
            batchConfirmActions.classList.remove('hidden');
            batchConfirmCancelBtn.textContent = 'Reset';
            batchConfirmSubmitBtn.classList.add('hidden');
        }
    }

    function renderBatchErrorCard(filename, errorMsg) {
        const card = document.createElement('div');
        card.className = 'confirm-card';
        card.innerHTML = `
            <div class="confirm-original">
                <span class="label">Original:</span>
                <span class="original-name">${escapeHtml(filename)}</span>
            </div>
            <div class="warning-banner" style="background:var(--error-subtle); color:var(--error); border-color:var(--error); display:block; margin-top:10px;">
                Failed: ${escapeHtml(errorMsg)}
            </div>
        `;
        confirmCardsWrapper.appendChild(card);
    }

    function renderBatchCard(data, index) {
        const clone = confirmCardTemplate.content.cloneNode(true);
        const card = clone.querySelector('.confirm-card');
        card.dataset.index = index;

        const projSelect = card.querySelector('.confirm-project');
        const typeSelect = card.querySelector('.confirm-type');
        const descInput  = card.querySelector('.confirm-description');
        const dateInput  = card.querySelector('.confirm-date');
        const verInput   = card.querySelector('.confirm-version');
        const preview    = card.querySelector('.confirm-preview-name');

        card.querySelector('.original-name').textContent = data.original_filename;
        populateProjectDropdown(projSelect, null);
        projSelect.value = data.project || '';
        typeSelect.value = data.type || '';
        descInput.value  = data.description || '';
        dateInput.value  = data.date || '';
        verInput.value   = data.version || '';

        if (data.date_estimated) {
            card.querySelector('.confirm-date-warning').classList.remove('hidden');
        }

        if (data.duplicate_warning) {
            const dupLabel = card.querySelector('.confirm-duplicate-warning');
            dupLabel.textContent = '⚠️ ' + data.duplicate_warning;
            dupLabel.classList.remove('hidden');
        }

        const currentExt = data.original_filename.split('.').pop() || '';

        const updatePreview = () => {
            const ext = currentExt ? `.${currentExt}` : '';
            preview.textContent = `${projSelect.value}_${typeSelect.value}_${descInput.value.replace(/\s/g, '')}_${dateInput.value}_v${verInput.value}${ext}`;
        };

        [projSelect, typeSelect, descInput, dateInput, verInput].forEach(el => {
            el.addEventListener('input', updatePreview);
            el.addEventListener('change', updatePreview);
        });
        updatePreview();
        
        bindBatchNewFolderLogic(card, projSelect, updatePreview);
        confirmCardsWrapper.appendChild(card);
    }

    function bindBatchNewFolderLogic(card, projSelect, updatePreview) {
        const toggleLink = card.querySelector('.new-folder-toggle-link');
        const inlineForm = card.querySelector('.new-folder-inline');
        const cancelLink = card.querySelector('.new-folder-cancel');
        const submitBtn  = card.querySelector('.new-folder-submit');
        const nameInput  = card.querySelector('.new-folder-name');
        const codeInput  = card.querySelector('.new-folder-code');
        const tierSelect = card.querySelector('.new-folder-tier');
        const msgDiv     = card.querySelector('.new-folder-msg');

        toggleLink.addEventListener('click', (e) => {
            e.preventDefault();
            inlineForm.classList.remove('hidden');
            toggleLink.classList.add('hidden');
            msgDiv.classList.add('hidden');
        });

        cancelLink.addEventListener('click', (e) => {
            e.preventDefault();
            inlineForm.classList.add('hidden');
            toggleLink.classList.remove('hidden');
            nameInput.value = '';
            codeInput.value = '';
            msgDiv.classList.add('hidden');
        });

        codeInput.addEventListener('input', () => {
            codeInput.value = codeInput.value.replace(/[^a-zA-Z]/g, '').toUpperCase();
        });

        submitBtn.addEventListener('click', async () => {
             const name = nameInput.value.trim();
             const code = codeInput.value.trim();
             const tier = tierSelect.value;

             if (!name || !code || code.length < 2) {
                 msgDiv.textContent = 'Folder name and 2-4 letter code required.';
                 msgDiv.className = 'new-folder-msg error';
                 msgDiv.classList.remove('hidden');
                 return;
             }

             submitBtn.disabled = true;
             submitBtn.textContent = '...';

             try {
                 const resp = await fetch(`${API_BASE}/gca/folder/create`, {
                     method: 'POST',
                     headers: { 'Content-Type': 'application/json' },
                     body: JSON.stringify({ name, code, tier }),
                 });

                 if (resp.ok) {
                     codesData = await resp.json();
                     // Update this dropdown and completely re-populate
                     document.querySelectorAll('.confirm-project').forEach(sel => {
                         const currentVal = sel.value;
                         populateProjectDropdown(sel, null);
                         if (sel === projSelect) sel.value = code;
                         else sel.value = currentVal;
                     });
                     
                     // Also update standard dropdowns
                     populateBrowseProjectDropdown(null);
                     if (confirmProject) populateProjectDropdown(confirmProject, confirmProject.value);

                     nameInput.value = '';
                     codeInput.value = '';
                     updatePreview();

                     msgDiv.textContent = 'Folder created successfully';
                     msgDiv.className = 'new-folder-msg'; 
                     msgDiv.classList.remove('hidden');

                     setTimeout(() => {
                         inlineForm.classList.add('hidden');
                         toggleLink.classList.remove('hidden');
                         msgDiv.classList.add('hidden');
                     }, 3000);
                 } else {
                     const err = await resp.json();
                     msgDiv.textContent = err.detail || 'Failed to create folder.';
                     msgDiv.className = 'new-folder-msg error';
                     msgDiv.classList.remove('hidden');
                 }
             } catch {
                 msgDiv.textContent = 'Cannot connect to server.';
                 msgDiv.className = 'new-folder-msg error';
                 msgDiv.classList.remove('hidden');
             }

             submitBtn.disabled = false;
             submitBtn.textContent = 'Submit';
        });
    }

    if (batchConfirmCancelBtn) {
        batchConfirmCancelBtn.addEventListener('click', resetUpload);
    }

    if (batchConfirmSubmitBtn) {
        batchConfirmSubmitBtn.addEventListener('click', async () => {
            batchConfirmSubmitBtn.disabled = true;
            batchConfirmCancelBtn.classList.add('hidden');
            batchProgressText.classList.remove('hidden');
            
            const total = currentBatch.length;
            let successCount = 0;
            const results = []; 

            for (let i = 0; i < total; i++) {
                batchProgressText.textContent = `Saving ${i + 1} of ${total}...`;
                
                const card = confirmCardsWrapper.querySelector(`.confirm-card[data-index="${i}"]`);
                if (!card) continue;

                const data = currentBatch[i];
                const p = card.querySelector('.confirm-project').value;
                const t = card.querySelector('.confirm-type').value;
                const d = card.querySelector('.confirm-description').value.replace(/\s/g, '');
                const dt = card.querySelector('.confirm-date').value;
                const v = card.querySelector('.confirm-version').value;
                const share = card.querySelector('.confirm-ready-to-share').checked;
                
                let tier = data.tier || 'Projects';
                if (codesData) {
                    if (codesData.Projects && codesData.Projects[p]) tier = 'Projects';
                    else if (codesData.Operations && codesData.Operations[p]) tier = 'Operations';
                }

                try {
                    const resp = await fetch(`${API_BASE}/gca/confirm`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            temp_id: data.temp_id,
                            tier: tier,
                            project: p,
                            type: t,
                            description: d,
                            date: dt,
                            version: v,
                            ready_to_share: share,
                        }),
                    });

                    if (resp.ok) {
                        const finalData = await resp.json();
                        successCount++;
                        results.push({ original: data.original_filename, final: finalData.assigned_filename, path: finalData.stored_path, ok: true });
                    } else {
                        const err = await resp.json();
                        results.push({ original: data.original_filename, error: err.detail || 'Confirmation failed', ok: false });
                    }
                } catch {
                    results.push({ original: data.original_filename, error: 'Cannot connect to server', ok: false });
                }
            }

            showUploadSuccess(results);
            batchConfirmSubmitBtn.disabled = false;
            batchConfirmCancelBtn.classList.remove('hidden');
        });
    }

    // =====================================================================
    // Upload — Shared Success & Reset
    // =====================================================================
    function showUploadSuccess(results) {
        singleConfirmContainer.classList.add('hidden');
        batchConfirmContainer.classList.add('hidden');
        uploadSuccess.classList.remove('hidden');
        
        const successCount = results.filter(r => r.ok).length;
        $('#success-title').textContent = `${successCount} file(s) saved successfully`;
        
        $('#success-list').innerHTML = results.map(r => {
            if (r.ok) {
                return `<div class="success-item">
                            <span class="success-item-name">${escapeHtml(r.final)}</span>
                            <span class="success-item-path">${escapeHtml(r.path)}</span>
                        </div>`;
            } else {
                return `<div class="success-item error">
                            <span class="success-item-name">${escapeHtml(r.original)}</span>
                            <span class="success-item-path">Error: ${escapeHtml(r.error)}</span>
                        </div>`;
            }
        }).join('');
    }

    uploadAnother.addEventListener('click', resetUpload);

    function resetUpload() {
        currentTempId = null;
        currentUploadExt = '';
        currentUploadTier = 'Projects';
        currentBatch = [];
        
        uploadFormContainer.classList.remove('hidden');
        singleConfirmContainer.classList.add('hidden');
        batchConfirmContainer.classList.add('hidden');
        uploadSuccess.classList.add('hidden');
        uploadProgress.classList.add('hidden');
        batchProgressText.classList.add('hidden');
        
        if (confirmCardsWrapper) confirmCardsWrapper.innerHTML = '';
        if (batchConfirmActions) {
            batchConfirmActions.classList.add('hidden');
            batchConfirmSubmitBtn.classList.remove('hidden');
            batchConfirmCancelBtn.textContent = 'Cancel All';
        }

        fileInput.value = '';
        uploadNote.value = '';
        readyToShare.checked = false;
        versionHint.textContent = 'Draft (v0.1)';

        if (newFolderInline) newFolderInline.classList.add('hidden');
        if (newFolderToggleLink) newFolderToggleLink.classList.remove('hidden');
        if (newFolderMsg) newFolderMsg.classList.add('hidden');
    }

    // =====================================================================
    // Pill Toggle Helper
    // =====================================================================
    function initPillToggle(container, callback) {
        const pills = container.querySelectorAll('.pill');
        pills.forEach(pill => {
            pill.addEventListener('click', () => {
                pills.forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                callback(pill.dataset.value);
            });
        });
    }

    // =====================================================================
    // Browse
    // =====================================================================
    initPillToggle(browseTierToggle, (value) => {
        browseTier = value;
        populateBrowseProjectDropdown(value === 'All' ? null : value);
        browseProjectFilter.value = '';
        loadBrowse();
    });

    async function loadBrowse() {
        browseFileList.innerHTML = '<div class="empty-state"><div class="loading-spinner"></div><p>Loading...</p></div>';

        const params = new URLSearchParams();
        if (browseProjectFilter.value) params.append('project', browseProjectFilter.value);
        if (browseTypeFilter.value) params.append('type', browseTypeFilter.value);
        if (browseTier !== 'All') params.append('tier', browseTier);
        params.append('sort', browseSort.value);

        try {
            const resp = await fetch(`${API_BASE}/gca/browse?${params}`);
            const data = await resp.json();

            let displayFiles = data.files;
            if (browseTier !== 'All') {
                displayFiles = displayFiles.filter(f => f.tier === browseTier || f.path.includes(`/${browseTier}/`));
            }

            if (displayFiles.length === 0) {
                browseFileList.innerHTML = '<div class="empty-state"><p>No files found.</p></div>';
                return;
            }

            browseFileList.innerHTML = displayFiles.map(f => `
                <div class="file-row">
                    <a class="file-name file-download-link" href="${API_BASE}/gca/download?path=${encodeURIComponent(f.path)}" title="Download ${escapeHtml(f.filename)}">${escapeHtml(f.filename)}</a>
                    <div class="file-badges">
                        <span class="badge badge-tier ${f.tier === 'Projects' ? 'tier-projects' : 'tier-operations'}">${f.tier === 'Projects' ? 'PRJ' : 'OPS'}</span>
                        <span class="badge badge-project ${f.project}">${f.project}</span>
                        <span class="badge badge-type">${f.type}</span>
                    </div>
                    <span class="file-date">${formatDate(f.date)}</span>
                    <span class="file-version">v${f.version}</span>
                </div>
            `).join('');
        } catch {
            browseFileList.innerHTML = '<div class="empty-state"><p>Cannot connect to server.</p></div>';
        }
    }

    browseProjectFilter.addEventListener('change', loadBrowse);
    browseTypeFilter.addEventListener('change', loadBrowse);
    browseSort.addEventListener('change', loadBrowse);
    browseRefresh.addEventListener('click', loadBrowse);

    // =====================================================================
    // Search
    // =====================================================================
    initPillToggle(searchScopeToggle, (value) => {
        searchScope = value;
    });

    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = searchInput.value.trim();
        if (!query) return;

        searchResults.innerHTML = '<div class="search-loading"><div class="loading-spinner"></div><span>Searching...</span></div>';
        searchSummary.classList.add('hidden');

        try {
            const resp = await fetch(`${API_BASE}/gca/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    synthesize: searchSynthesize.checked,
                    scope: searchScope,
                }),
            });

            if (resp.ok) {
                const data = await resp.json();

                // Show summary if present
                if (data.summary) {
                    searchSummary.textContent = data.summary;
                    searchSummary.classList.remove('hidden');
                }

                // Show results
                if (data.results.length === 0) {
                    searchResults.innerHTML = '<div class="empty-state"><p>No results found. Try different search terms.</p></div>';
                    return;
                }

                searchResults.innerHTML = data.results.map(r => `
                    <div class="search-result-card">
                        <div class="result-header">
                            <a class="result-filename file-download-link" href="${API_BASE}/gca/download?path=${encodeURIComponent(r.path)}" title="Download ${escapeHtml(r.filename)}">${escapeHtml(r.filename)}</a>
                            <div class="file-badges">
                                <span class="badge badge-tier ${r.tier === 'Projects' ? 'tier-projects' : 'tier-operations'}">${r.tier === 'Projects' ? 'PRJ' : 'OPS'}</span>
                                <span class="badge badge-project ${r.project}">${r.project}</span>
                                <span class="badge badge-type">${r.type}</span>
                            </div>
                            <span class="result-score">${(r.score * 100).toFixed(0)}% match</span>
                        </div>
                        <p class="result-excerpt">${escapeHtml(r.excerpt)}</p>
                    </div>
                `).join('');
            } else {
                const err = await resp.json();
                searchResults.innerHTML = `<div class="empty-state"><p>${escapeHtml(err.detail || 'Search failed.')}</p></div>`;
            }
        } catch {
            searchResults.innerHTML = '<div class="empty-state"><p>Cannot connect to server.</p></div>';
        }
    });

    // =====================================================================
    // Helpers
    // =====================================================================
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatDate(dateStr) {
        if (!dateStr || dateStr.length !== 8) return dateStr || '';
        return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
    }
})();
