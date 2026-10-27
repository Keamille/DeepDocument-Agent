// DeepDocument 前端交互

let currentProject = '';
let currentSection = null;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
    setupEventListeners();
});

// 设置事件监听
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
        if (currentProject) {
            loadProject(currentProject);
        }
    });

    // 标签切换
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            switchTab(tabName);
        });
    });

    // 确认卡
    document.getElementById('modal-confirm').addEventListener('click', () => {
        confirmAction(true);
    });

    document.getElementById('modal-cancel').addEventListener('click', () => {
        confirmAction(false);
    });
}

// 发送消息
async function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    if (!message) return;

    // 显示用户消息
    appendMessage('user', message);
    input.value = '';

    // 调用后端
    try {
        const result = await pywebview.api.send_message(message, currentProject);
        handleResponse(result);
    } catch (error) {
        appendMessage('assistant', `错误: ${error}`);
    }
}

// 处理响应
function handleResponse(result) {
    if (result.type === 'message') {
        appendMessage('assistant', result.content);
    } else if (result.type === 'confirmation') {
        showConfirmation(result.data);
    } else if (result.type === 'update') {
        refreshProject();
    }
}

// 追加消息
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

// 显示确认卡
function showConfirmation(data) {
    const modal = document.getElementById('confirmation-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');

    if (data.card_type === 'outline') {
        title.textContent = '确认大纲';
        body.innerHTML = `<pre>${data.diff}</pre>`;
    } else if (data.card_type === 'literature') {
        title.textContent = '选择文献';
        body.innerHTML = renderLiteratureCard(data.items);
    } else if (data.card_type === 'skill') {
        title.textContent = '保存 Skill';
        body.innerHTML = `<pre>${data.markdown}</pre>`;
    }

    modal.style.display = 'flex';
}

// 渲染文献卡
function renderLiteratureCard(items) {
    return items.map((item, idx) => `
        <div>
            <input type="checkbox" id="lit-${idx}" checked>
            <label for="lit-${idx}">
                ${item.title} (${item.year})
                ${item.available ? '' : '<span style="color: var(--accent-warm);">无可用文本</span>'}
            </label>
        </div>
    `).join('');
}

// 确认动作
async function confirmAction(accept) {
    const modal = document.getElementById('confirmation-modal');
    modal.style.display = 'none';

    try {
        const result = await pywebview.api.confirm_action(accept);
        handleResponse(result);
    } catch (error) {
        appendMessage('assistant', `错误: ${error}`);
    }
}

// 加载项目列表
async function loadProjects() {
    try {
        const projects = await pywebview.api.list_projects();
        const selector = document.getElementById('project-selector');
        projects.forEach(proj => {
            const option = document.createElement('option');
            option.value = proj.slug;
            option.textContent = proj.title;
            selector.appendChild(option);
        });
    } catch (error) {
        console.error('加载项目失败:', error);
    }
}

// 加载项目
async function loadProject(slug) {
    try {
        const data = await pywebview.api.load_project(slug);
        renderProject(data);
    } catch (error) {
        console.error('加载项目失败:', error);
    }
}

// 渲染项目
function renderProject(data) {
    // 渲染大纲
    const outlineView = document.getElementById('outline-view');
    outlineView.innerHTML = data.outline.map(title => `<h3>${title}</h3>`).join('');

    // 渲染正文
    const sectionsView = document.getElementById('sections-view');
    sectionsView.innerHTML = data.sections.map(sec => `
        <div class="section" data-id="${sec.id}">
            <h2>${sec.status === 'accepted' ? '✅' : '📝'} ${sec.title}</h2>
            ${marked.parse(sec.content || '')}
        </div>
    `).join('');

    // 点击节标题设置修订目标
    sectionsView.querySelectorAll('.section').forEach(el => {
        el.addEventListener('click', () => {
            currentSection = el.dataset.id;
            document.getElementById('context-indicator').textContent =
                `📍 正在修订: ${el.querySelector('h2').textContent}`;
        });
    });

    // 渲染文献
    const literatureView = document.getElementById('literature-view');
    literatureView.innerHTML = data.literature.map(lit => `
        <div>
            <strong>${lit.title}</strong> (${lit.year})<br>
            ${lit.authors.join(', ')}
        </div>
    `).join('');

    // 渲染画像
    const profileView = document.getElementById('profile-view');
    profileView.innerHTML = marked.parse(data.profile || '');
}

// 切换标签
function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
}

// 刷新项目
function refreshProject() {
    if (currentProject) {
        loadProject(currentProject);
    }
}
