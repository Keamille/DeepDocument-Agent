// DeepDocument 前端交互（含未完成能力的 UI 骨架）

let currentProject = '';
let currentSection = null;

document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
    setupEventListeners();
});

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
        currentSection = null;
        document.getElementById('context-indicator').textContent = '';
        if (currentProject) {
            loadProject(currentProject);
        }
    });

    document.getElementById('new-project-btn').addEventListener('click', () => {
        document.getElementById('new-project-modal').style.display = 'flex';
    });
    document.getElementById('new-project-cancel').addEventListener('click', () => {
        document.getElementById('new-project-modal').style.display = 'none';
    });
    document.getElementById('new-project-ok').addEventListener('click', createProject);

    document.getElementById('export-btn').addEventListener('click', exportWord);
    document.getElementById('attach-input').addEventListener('change', onAttachFile);

    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    document.getElementById('modal-confirm').addEventListener('click', () => confirmAction(true));
    document.getElementById('modal-cancel').addEventListener('click', () => confirmAction(false));
}

async function createProject() {
    const title = document.getElementById('new-title').value.trim();
    const kind = document.getElementById('new-kind').value;
    const audience = document.getElementById('new-audience').value.trim();
    try {
        const result = await pywebview.api.create_project(title, kind, audience);
        if (!result.ok) {
            appendMessage('assistant', result.error || '创建失败');
            return;
        }
        document.getElementById('new-project-modal').style.display = 'none';
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
        const result = await pywebview.api.export_word(currentProject);
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
    if (!file || !currentProject) {
        return;
    }
    // pywebview 下 file.path 可用；浏览器环境可能没有，骨架先传 name
    const path = file.path || file.name;
    try {
        const result = await pywebview.api.attach_file(currentProject, path);
        appendMessage('assistant', result.message || JSON.stringify(result));
        refreshProject();
    } catch (error) {
        appendMessage('assistant', `附件错误: ${error}`);
    }
    e.target.value = '';
}

async function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    if (!message) return;

    appendMessage('user', message);
    input.value = '';

    const context = {};
    if (currentSection) {
        context.section_id = currentSection;
    }

    try {
        const result = await pywebview.api.send_message(message, currentProject, context);
        handleResponse(result);
    } catch (error) {
        appendMessage('assistant', `错误: ${error}`);
    }
}

function handleResponse(result) {
    if (result.type === 'message') {
        appendMessage('assistant', result.content);
        refreshProject();
    } else if (result.type === 'confirmation') {
        showConfirmation(result.data);
        if (result.content) {
            appendMessage('assistant', result.content);
        }
    } else if (result.type === 'update') {
        refreshProject();
        if (result.content) {
            appendMessage('assistant', result.content);
        }
    }
}

function appendMessage(role, content) {
    const messagesDiv = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    messageDiv.appendChild(contentDiv);
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function showConfirmation(data) {
    const modal = document.getElementById('confirmation-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');

    if (data.card_type === 'outline') {
        title.textContent = '确认大纲';
        // TODO: 可编辑 titles 后再同意
        body.innerHTML = `<pre class="editable-outline">${escapeHtml(data.diff || '')}</pre>`;
    } else if (data.card_type === 'literature') {
        title.textContent = '选择文献';
        body.innerHTML = renderLiteratureCard(data.items || []);
    } else if (data.card_type === 'skill') {
        title.textContent = '保存 Skill';
        // TODO: 可编辑 markdown 后再同意
        body.innerHTML = `<pre class="editable-skill">${escapeHtml(data.markdown || '')}</pre>`;
    } else if (data.card_type === 'question') {
        title.textContent = '需要补充信息';
        body.innerHTML = `<p>${escapeHtml(data.question || '')}</p><p class="hint">请在输入框回答后发送</p>`;
    } else {
        title.textContent = '确认';
        body.innerHTML = `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
    }

    modal.style.display = 'flex';
}

function renderLiteratureCard(items) {
    return items.map((item) => `
        <div class="lit-item">
            <input type="checkbox" class="lit-check" data-id="${item.id}" ${item.available === false ? '' : 'checked'}>
            <label>
                <strong>${escapeHtml(item.title || '')}</strong>
                (${item.year || ''})
                ${item.available === false ? '<span class="warn">无可用文本</span>' : ''}
                <br>
                <span class="meta">${escapeHtml((item.authors || []).join(', '))}</span>
                ${item.venue ? `<br><span class="meta">${escapeHtml(item.venue)}</span>` : ''}
                ${item.url ? `<br><a href="${escapeHtml(item.url)}" target="_blank">链接</a>` : ''}
            </label>
        </div>
    `).join('');
}

function collectConfirmPayload() {
    const checks = document.querySelectorAll('.lit-check');
    if (!checks.length) {
        return {};
    }
    const selected_ids = [];
    checks.forEach((el) => {
        if (el.checked && el.dataset.id) {
            selected_ids.push(el.dataset.id);
        }
    });
    return { selected_ids };
}

async function confirmAction(accept) {
    const payload = collectConfirmPayload();
    document.getElementById('confirmation-modal').style.display = 'none';
    try {
        const result = await pywebview.api.confirm_action(accept, payload);
        handleResponse(result);
    } catch (error) {
        appendMessage('assistant', `错误: ${error}`);
    }
}

async function loadProjects() {
    try {
        const projects = await pywebview.api.list_projects();
        const selector = document.getElementById('project-selector');
        const previous = selector.value;
        selector.innerHTML = '<option value="">选择项目…</option>';
        projects.forEach(proj => {
            const option = document.createElement('option');
            option.value = proj.slug;
            option.textContent = proj.title;
            selector.appendChild(option);
        });
        if (previous) {
            selector.value = previous;
        }
    } catch (error) {
        console.error('加载项目失败:', error);
    }
}

async function loadProject(slug) {
    try {
        const data = await pywebview.api.load_project(slug);
        renderProject(data);
        if (data.pending_confirmation) {
            showConfirmation(data.pending_confirmation);
        }
    } catch (error) {
        console.error('加载项目失败:', error);
    }
}

function renderProject(data) {
    document.getElementById('outline-view').innerHTML =
        (data.outline || []).map(title => `<h3>${escapeHtml(title)}</h3>`).join('');

    const sectionsView = document.getElementById('sections-view');
    const parse = (window.marked && marked.parse) ? marked.parse : (t => t);
    sectionsView.innerHTML = (data.sections || []).map(sec => `
        <div class="section" data-id="${sec.id}">
            <h2>${sec.status === 'accepted' ? '✅' : '📝'} ${escapeHtml(sec.title)} <small>${sec.status}</small></h2>
            ${parse(sec.content || '')}
        </div>
    `).join('');

    sectionsView.querySelectorAll('.section').forEach(el => {
        el.addEventListener('click', () => {
            currentSection = el.dataset.id;
            document.getElementById('context-indicator').textContent =
                `📍 正在修订: ${el.querySelector('h2').textContent}`;
        });
    });

    document.getElementById('literature-view').innerHTML = (data.literature || []).map(lit => `
        <div>
            <strong>${escapeHtml(lit.title)}</strong> (${lit.year || ''})
            <span class="meta">[${lit.content_source || '?'}]</span><br>
            ${escapeHtml((lit.authors || []).join(', '))}
        </div>
    `).join('');

    document.getElementById('profile-view').innerHTML = parse(data.profile || '');
    // TODO: 画像 rejects 逐条删除按钮对接 delete_profile_reject

    const skillsView = document.getElementById('skills-view');
    skillsView.innerHTML = (data.skills || []).map(sk => `
        <div class="skill-item" data-name="${escapeHtml(sk.name)}">
            <strong>${escapeHtml(sk.name)}</strong>
            ${sk.is_builtin ? '<span class="meta">内置</span>' : '<button type="button" class="skill-del">删除</button>'}
            <div class="skill-desc">${escapeHtml(sk.description || '')}</div>
        </div>
    `).join('') || '<p class="hint">暂无 skill</p>';

    skillsView.querySelectorAll('.skill-del').forEach(btn => {
        btn.addEventListener('click', async (ev) => {
            ev.stopPropagation();
            const name = btn.closest('.skill-item').dataset.name;
            if (!confirm(`删除 skill ${name}？`)) return;
            await pywebview.api.delete_skill(name);
            refreshProject();
        });
    });
    // TODO: 点击 description 进入编辑 → update_skill_description
}

function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
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
