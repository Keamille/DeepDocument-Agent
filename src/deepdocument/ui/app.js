// DeepDocument 前端：对接 WindowAPI，完成确认卡 / 画像 / skill 交互

let currentProject = '';
let currentSection = null;
let currentCursor = '';
let pendingCard = null;

document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
    setupEventListeners();
});

function api() {
    if (!window.pywebview || !window.pywebview.api) {
        throw new Error('pywebview API 不可用');
    }
    return window.pywebview.api;
}

function setupEventListeners() {
    document.getElementById('send-btn').addEventListener('click', sendMessage);
    document.getElementById('user-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    document.getElementById('project-selector').addEventListener('change', (e) => {
        currentProject = e.target.value;
        clearSectionTarget();
        if (currentProject) {
            loadProject(currentProject);
        }
    });

    document.getElementById('new-project-btn').addEventListener('click', () => {
        document.getElementById('new-project-modal').style.display = 'flex';
        document.getElementById('new-title').focus();
    });
    document.getElementById('new-project-cancel').addEventListener('click', () => {
        document.getElementById('new-project-modal').style.display = 'none';
    });
    document.getElementById('new-project-ok').addEventListener('click', createProject);

    document.getElementById('export-btn').addEventListener('click', exportWord);
    document.getElementById('attach-input').addEventListener('change', onAttachFile);

    document.querySelectorAll('.tab').forEach((tab) => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    document.getElementById('modal-confirm').addEventListener('click', () => confirmAction(true));
    document.getElementById('modal-cancel').addEventListener('click', () => confirmAction(false));

    document.getElementById('context-indicator').addEventListener('click', () => {
        if (currentSection) {
            clearSectionTarget();
        }
    });
}

function clearSectionTarget() {
    currentSection = null;
    const el = document.getElementById('context-indicator');
    el.textContent = '';
    el.title = '';
}

async function createProject() {
    const title = document.getElementById('new-title').value.trim();
    const kind = document.getElementById('new-kind').value;
    const audience = document.getElementById('new-audience').value.trim();
    if (!title) {
        appendMessage('assistant', '题目不能为空');
        return;
    }
    try {
        const result = await api().create_project(title, kind, audience);
        if (!result.ok) {
            appendMessage('assistant', result.error || '创建失败');
            return;
        }
        document.getElementById('new-project-modal').style.display = 'none';
        document.getElementById('new-title').value = '';
        document.getElementById('new-audience').value = '';
        await loadProjects();
        const selector = document.getElementById('project-selector');
        selector.value = result.slug;
        currentProject = result.slug;
        await loadProject(result.slug);
        appendMessage('assistant', `已创建项目 ${result.title}`);
    } catch (error) {
        appendMessage('assistant', `错误: ${error}`);
    }
}

async function exportWord() {
    if (!currentProject) {
        appendMessage('assistant', '请先选择项目');
        return;
    }
    try {
        const result = await api().export_word(currentProject);
        if (result.ok) {
            appendMessage('assistant', `已导出: ${result.path}`);
        } else {
            appendMessage('assistant', result.error || '导出失败');
        }
    } catch (error) {
        appendMessage('assistant', `错误: ${error}`);
    }
}

async function onAttachFile(e) {
    const file = e.target.files && e.target.files[0];
    if (!file) {
        return;
    }
    if (!currentProject) {
        appendMessage('assistant', '请先选择项目');
        e.target.value = '';
        return;
    }
    const path = file.path || file.name;
    try {
        const result = await api().attach_file(currentProject, path);
        appendMessage('assistant', result.message || JSON.stringify(result));
        if (result.suggested_outline && result.suggested_outline.length) {
            appendMessage(
                'assistant',
                `模板大纲候选: ${result.suggested_outline.join(' / ')}`
            );
        }
        refreshProject();
    } catch (error) {
        appendMessage('assistant', `附件错误: ${error}`);
    }
    e.target.value = '';
}

async function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    if (!message) {
        return;
    }
    if (!currentProject) {
        appendMessage('assistant', '请先选择或新建项目');
        return;
    }

    appendMessage('user', message);
    input.value = '';

    const context = {};
    if (currentSection) {
        context.section_id = currentSection;
    }

    setSending(true);
    try {
        const result = await api().send_message(message, currentProject, context);
        handleResponse(result);
    } catch (error) {
        appendMessage('assistant', `错误: ${error}`);
    } finally {
        setSending(false);
    }
}

function setSending(busy) {
    const btn = document.getElementById('send-btn');
    const input = document.getElementById('user-input');
    btn.disabled = busy;
    input.disabled = busy;
    btn.textContent = busy ? '处理中…' : '发送';
}

function handleResponse(result) {
    if (!result || !result.type) {
        appendMessage('assistant', '未知响应');
        return;
    }
    if (result.type === 'message') {
        appendMessage('assistant', result.content || '');
        refreshProject();
    } else if (result.type === 'confirmation') {
        showConfirmation(result.data);
        if (result.content) {
            appendMessage('assistant', result.content);
        }
    } else if (result.type === 'conflict') {
        showConflict(result.data);
    } else if (result.type === 'update') {
        refreshProject();
        if (result.content) {
            appendMessage('assistant', result.content);
        }
    } else {
        appendMessage('assistant', result.content || JSON.stringify(result));
    }
}

async function showConflict(data) {
    const summary = (data && data.diff && data.diff.summary) || '文件被外部修改';
    const keep = window.confirm(
        `${data.message || '检测到外部修改'}\n\n${summary}\n\n确定=保留磁盘并继续；取消=回到确认卡`
    );
    try {
        const result = await api().confirm_action(true, {
            conflict_resolution: keep ? 'keep_disk' : 'abort',
        });
        handleResponse(result);
    } catch (error) {
        appendMessage('assistant', `错误: ${error}`);
    }
}

function appendMessage(role, content) {
    const messagesDiv = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content == null ? '' : String(content);
    messageDiv.appendChild(contentDiv);
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function showConfirmation(data) {
    pendingCard = data || null;
    const modal = document.getElementById('confirmation-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    const confirmBtn = document.getElementById('modal-confirm');
    const cancelBtn = document.getElementById('modal-cancel');

    confirmBtn.style.display = '';
    cancelBtn.textContent = '拒绝';

    const cardType = data && data.card_type;
    if (cardType === 'outline') {
        title.textContent = '确认大纲';
        const titles = data.titles || parseDiffTitles(data.diff || '');
        body.innerHTML = `
            <p class="hint">可编辑标题（一行一节），再同意写入。</p>
            <textarea id="outline-edit" class="card-edit" rows="8">${escapeHtml(titles.join('\n'))}</textarea>
            <pre class="diff-preview">${escapeHtml(data.diff || '')}</pre>
        `;
    } else if (cardType === 'literature') {
        title.textContent = '选择文献';
        body.innerHTML = renderLiteratureCard(data.items || []);
    } else if (cardType === 'skill') {
        title.textContent = '保存 Skill';
        body.innerHTML = `
            <p class="hint">可编辑后同意写入 skills_user/。</p>
            <label>名称 <input id="skill-name-edit" type="text" value="${escapeHtml(data.name || '')}" /></label>
            <textarea id="skill-edit" class="card-edit" rows="12">${escapeHtml(data.markdown || '')}</textarea>
        `;
    } else if (cardType === 'question') {
        title.textContent = '需要补充信息';
        body.innerHTML = `
            <p>${escapeHtml(data.question || '')}</p>
            <p class="hint">请在左侧输入框回答后发送；也可点「关闭」稍后再答。</p>
        `;
        confirmBtn.style.display = 'none';
        cancelBtn.textContent = '关闭';
    } else {
        title.textContent = '确认';
        body.innerHTML = `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
    }

    modal.style.display = 'flex';
}

function parseDiffTitles(diff) {
    return String(diff || '')
        .split('\n')
        .map((line) => line.replace(/^[+\\-\\s]+/, '').trim())
        .filter(Boolean);
}

function renderLiteratureCard(items) {
    if (!items.length) {
        return '<p class="hint">没有候选文献</p>';
    }
    return items
        .map(
            (item) => `
        <div class="lit-item">
            <label class="lit-label">
                <input type="checkbox" class="lit-check" data-id="${escapeHtml(item.id || '')}"
                    ${item.available === false ? '' : 'checked'}>
                <span>
                    <strong>${escapeHtml(item.title || '')}</strong>
                    (${item.year || ''})
                    ${item.available === false ? '<span class="warn">无可用文本</span>' : ''}
                    <br>
                    <span class="meta">${escapeHtml((item.authors || []).join(', '))}</span>
                    ${item.venue ? `<br><span class="meta">${escapeHtml(item.venue)}</span>` : ''}
                    ${item.url ? `<br><a href="${escapeHtml(item.url)}" target="_blank" rel="noopener">链接</a>` : ''}
                </span>
            </label>
        </div>`
        )
        .join('');
}

function collectConfirmPayload() {
    const payload = {};
    const cardType = pendingCard && pendingCard.card_type;

    if (cardType === 'literature') {
        const selected_ids = [];
        document.querySelectorAll('.lit-check').forEach((el) => {
            if (el.checked && el.dataset.id) {
                selected_ids.push(el.dataset.id);
            }
        });
        payload.selected_ids = selected_ids;
    } else if (cardType === 'outline') {
        const edit = document.getElementById('outline-edit');
        if (edit) {
            payload.titles = edit.value
                .split('\n')
                .map((line) => line.trim())
                .filter(Boolean);
        }
    } else if (cardType === 'skill') {
        const md = document.getElementById('skill-edit');
        const name = document.getElementById('skill-name-edit');
        if (md) {
            payload.markdown = md.value;
        }
        if (name && name.value.trim()) {
            payload.name = name.value.trim();
        }
    }
    return payload;
}

async function confirmAction(accept) {
    const payload = collectConfirmPayload();
    document.getElementById('confirmation-modal').style.display = 'none';
    pendingCard = null;
    try {
        const result = await api().confirm_action(accept, payload);
        handleResponse(result);
    } catch (error) {
        appendMessage('assistant', `错误: ${error}`);
    }
}

async function loadProjects() {
    try {
        const projects = await api().list_projects();
        const selector = document.getElementById('project-selector');
        const previous = selector.value || currentProject;
        selector.innerHTML = '<option value="">选择项目…</option>';
        projects.forEach((proj) => {
            const option = document.createElement('option');
            option.value = proj.slug;
            option.textContent = proj.title;
            selector.appendChild(option);
        });
        if (previous) {
            selector.value = previous;
            currentProject = previous;
        }
    } catch (error) {
        console.error('加载项目失败:', error);
    }
}

async function loadProject(slug) {
    try {
        const data = await api().load_project(slug);
        currentProject = slug;
        renderProject(data);
        if (data.pending_confirmation) {
            showConfirmation(data.pending_confirmation);
        }
    } catch (error) {
        console.error('加载项目失败:', error);
        appendMessage('assistant', `加载项目失败: ${error}`);
    }
}

function markdownParse(text) {
    if (window.marked && typeof marked.parse === 'function') {
        return marked.parse(text || '');
    }
    return escapeHtml(text || '').replace(/\n/g, '<br>');
}

function renderProject(data) {
    currentCursor = data.cursor || '';

    document.getElementById('outline-view').innerHTML =
        (data.outline || []).map((title) => `<h3>${escapeHtml(title)}</h3>`).join('') ||
        '<p class="hint">尚无大纲</p>';

    const sectionsView = document.getElementById('sections-view');
    sectionsView.innerHTML =
        (data.sections || [])
            .map((sec) => {
                const active =
                    sec.id === currentSection || sec.id === currentCursor ? ' active-section' : '';
                const mark =
                    sec.status === 'accepted' ? '✓' : sec.status === 'draft' ? '✎' : '○';
                return `
        <div class="section${active}" data-id="${escapeHtml(sec.id)}">
            <h2>${mark} ${escapeHtml(sec.title)} <small>${escapeHtml(sec.status)}</small></h2>
            ${sec.gist ? `<p class="meta">要旨: ${escapeHtml(sec.gist)}</p>` : ''}
            ${markdownParse(sec.content || '')}
        </div>`;
            })
            .join('') || '<p class="hint">尚无章节</p>';

    sectionsView.querySelectorAll('.section').forEach((el) => {
        el.addEventListener('click', () => {
            currentSection = el.dataset.id;
            const title = el.querySelector('h2') ? el.querySelector('h2').textContent : el.dataset.id;
            const indicator = document.getElementById('context-indicator');
            indicator.textContent = `📍 正在修订: ${title}（点击此处取消）`;
            indicator.title = '点击取消修订目标';
            sectionsView.querySelectorAll('.section').forEach((s) => s.classList.remove('active-section'));
            el.classList.add('active-section');
            document.getElementById('user-input').focus();
        });
    });

    document.getElementById('literature-view').innerHTML =
        (data.literature || [])
            .map(
                (lit) => `
        <div class="lit-item">
            <strong>${escapeHtml(lit.title)}</strong> (${lit.year || ''})
            <span class="meta">[${escapeHtml(lit.content_source || '?')}]</span><br>
            ${escapeHtml((lit.authors || []).join(', '))}
            ${lit.venue ? `<br><span class="meta">${escapeHtml(lit.venue)}</span>` : ''}
            ${lit.url ? `<br><a href="${escapeHtml(lit.url)}" target="_blank" rel="noopener">链接</a>` : ''}
        </div>`
            )
            .join('') || '<p class="hint">尚无已确认文献</p>';

    renderProfile(data);
    renderSkills(data.skills || []);
}

function renderProfile(data) {
    const profileView = document.getElementById('profile-view');
    const pd = data.profile_data || {};
    const rejects = pd.rejects || [];
    const rows = [
        ['language', pd.language || ''],
        ['tone', pd.tone || ''],
        ['structure', pd.structure || ''],
        ['citation', pd.citation || ''],
    ]
        .map(
            ([k, v]) =>
                `<div class="profile-row"><span class="meta">${k}</span> ${escapeHtml(v || '（空）')}</div>`
        )
        .join('');

    const rejectList =
        rejects
            .map(
                (text, index) => `
        <div class="reject-item" data-index="${index}">
            <span>${escapeHtml(text)}</span>
            <button type="button" class="reject-del secondary-btn">删除</button>
        </div>`
            )
            .join('') || '<p class="hint">暂无拒绝项</p>';

    profileView.innerHTML = `
        ${rows}
        <h3>rejects</h3>
        ${rejectList}
    `;

    profileView.querySelectorAll('.reject-del').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const index = Number(btn.closest('.reject-item').dataset.index);
            try {
                const result = await api().delete_profile_reject(index);
                if (!result.ok) {
                    appendMessage('assistant', result.error || '删除失败');
                    return;
                }
                refreshProject();
            } catch (error) {
                appendMessage('assistant', `错误: ${error}`);
            }
        });
    });
}

function renderSkills(skills) {
    const skillsView = document.getElementById('skills-view');
    skillsView.innerHTML =
        skills
            .map(
                (sk) => `
        <div class="skill-item" data-name="${escapeHtml(sk.name)}">
            <div class="skill-head">
                <strong>${escapeHtml(sk.name)}</strong>
                ${
                    sk.is_builtin
                        ? '<span class="meta">内置</span>'
                        : '<button type="button" class="skill-del secondary-btn">删除</button>'
                }
            </div>
            <div class="skill-desc" title="${sk.is_builtin ? '' : '点击编辑 description'}">${escapeHtml(
                sk.description || ''
            )}</div>
        </div>`
            )
            .join('') || '<p class="hint">暂无 skill</p>';

    skillsView.querySelectorAll('.skill-del').forEach((btn) => {
        btn.addEventListener('click', async (ev) => {
            ev.stopPropagation();
            const name = btn.closest('.skill-item').dataset.name;
            if (!window.confirm(`删除 skill「${name}」？`)) {
                return;
            }
            try {
                const result = await api().delete_skill(name);
                if (!result.ok) {
                    appendMessage('assistant', result.error || '删除失败');
                    return;
                }
                refreshProject();
            } catch (error) {
                appendMessage('assistant', `错误: ${error}`);
            }
        });
    });

    skillsView.querySelectorAll('.skill-item').forEach((item) => {
        const desc = item.querySelector('.skill-desc');
        const builtin = item.querySelector('.meta');
        if (builtin && builtin.textContent.includes('内置')) {
            return;
        }
        desc.addEventListener('click', () => beginEditSkillDescription(item));
    });
}

function beginEditSkillDescription(item) {
    const name = item.dataset.name;
    const descEl = item.querySelector('.skill-desc');
    if (item.querySelector('.skill-desc-edit')) {
        return;
    }
    const current = descEl.textContent || '';
    descEl.style.display = 'none';
    const editor = document.createElement('div');
    editor.className = 'skill-desc-edit';
    editor.innerHTML = `
        <textarea rows="3">${escapeHtml(current)}</textarea>
        <div class="modal-actions">
            <button type="button" class="primary-btn skill-save">保存</button>
            <button type="button" class="secondary-btn skill-cancel">取消</button>
        </div>
    `;
    item.appendChild(editor);
    const textarea = editor.querySelector('textarea');
    textarea.focus();

    editor.querySelector('.skill-cancel').addEventListener('click', () => {
        editor.remove();
        descEl.style.display = '';
    });
    editor.querySelector('.skill-save').addEventListener('click', async () => {
        try {
            const result = await api().update_skill_description(name, textarea.value.trim());
            if (!result.ok) {
                appendMessage('assistant', result.error || '保存失败');
                return;
            }
            refreshProject();
        } catch (error) {
            appendMessage('assistant', `错误: ${error}`);
        }
    });
}

function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach((content) => content.classList.remove('active'));
    const tab = document.querySelector(`[data-tab="${tabName}"]`);
    const pane = document.getElementById(`tab-${tabName}`);
    if (tab) {
        tab.classList.add('active');
    }
    if (pane) {
        pane.classList.add('active');
    }
}

function refreshProject() {
    if (currentProject) {
        loadProject(currentProject);
    }
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
