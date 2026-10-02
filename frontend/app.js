const API_BASE_URL = "http://127.0.0.1:8000";

const advisorList = document.querySelector("#advisor-list");
const agentList = document.querySelector("#agent-list");
const advisorTitle = document.querySelector("#advisor-title");
const advisorEmail = document.querySelector("#advisor-email");
const loadingState = document.querySelector("#loading-state");
const errorState = document.querySelector("#error-state");
const connectionBadge = document.querySelector("#connection-badge");
let advisors = [];
let selectedAdvisorId = null;
let expandedAgentId = null;
let initialLoad = true;

async function fetchJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) throw new Error(`API request failed (${response.status})`);
  return response.json();
}

async function loadAdvisors() {
  if (initialLoad) loadingState.hidden = false;
  try {
    const response = await fetchJson("/advisors");
    advisors = response.advisors;
    if (!selectedAdvisorId || !advisors.some(advisor => advisor.id === selectedAdvisorId)) {
      selectedAdvisorId = advisors[0]?.id ?? null;
    }
    if (!expandedAgentId) {
      expandedAgentId = null;
    }
    renderAdvisors();
    renderSelectedAdvisor();
    connectionBadge.textContent = "Connected · Local API";
    connectionBadge.classList.add("connected");
    errorState.hidden = true;
  } catch (error) {
    errorState.textContent =
      "Could not load advisors. Start the backend with "
      + "'.venv\\Scripts\\python.exe -m backend.server'.";
    errorState.hidden = false;
    connectionBadge.textContent = "Backend unavailable";
  } finally {
    if (initialLoad) {
      loadingState.hidden = true;
      initialLoad = false;
    }
  }
}

function renderAdvisors() {
  if (!advisors.length) {
    advisorList.innerHTML = '<p class="muted advisor-empty">No advisors found.</p>';
    return;
  }
  advisorList.innerHTML = advisors.map(advisor => `
    <button type="button" class="advisor-item ${advisor.id === selectedAdvisorId ? "selected" : ""}"
      data-advisor-id="${escapeHtml(advisor.id)}">
      <span class="avatar">${escapeHtml(initials(advisor.name))}</span>
      <span class="advisor-name">${escapeHtml(advisor.name)}</span>
    </button>`).join("");
  advisorList.querySelectorAll(".advisor-item").forEach(button => {
    button.addEventListener("click", () => {
      selectedAdvisorId = button.dataset.advisorId;
      expandedAgentId = null;
      renderAdvisors();
      renderSelectedAdvisor();
    });
  });
}

function renderSelectedAdvisor() {
  const advisor = advisors.find(item => item.id === selectedAdvisorId);
  if (!advisor) {
    advisorTitle.textContent = "Select an advisor";
    advisorEmail.textContent = "";
    agentList.innerHTML = '<p class="muted">Select an advisor to view their agents.</p>';
    return;
  }
  advisorTitle.textContent = advisor.name;
  advisorEmail.textContent = advisor.email;
  const agents = [...advisor.agents].sort((left, right) => {
    const leftTime = left.latest_task?.started_at || left.created_at || "";
    const rightTime = right.latest_task?.started_at || right.created_at || "";
    return rightTime.localeCompare(leftTime);
  });
  agentList.innerHTML = agents.length
    ? agents.map(renderAgent).join("")
    : '<p class="muted">This advisor has no assigned agents.</p>';
  agentList.querySelectorAll(".agent-card").forEach(card => {
    card.querySelector(".agent-summary").addEventListener("click", () => {
      expandedAgentId = expandedAgentId === card.dataset.agentId ? null : card.dataset.agentId;
      renderSelectedAdvisor();
    });
    const taskButton = card.querySelector("[data-task-id]");
    if (taskButton) {
      taskButton.addEventListener("click", () => loadTaskDetails(taskButton.dataset.taskId));
    }
    const historyButton = card.querySelector(".secondary-button[data-agent-id]");
    if (historyButton) {
      historyButton.addEventListener("click", event => {
        event.stopPropagation();
        loadAgentTasks(historyButton.dataset.agentId);
      });
    }
  });
}

function renderAgent(agent) {
  const task = agent.latest_task;
  const expanded = agent.id === expandedAgentId;
  return `
    <article class="agent-card ${expanded ? "expanded" : ""}" data-agent-id="${escapeHtml(agent.id)}">
      <button type="button" class="agent-summary">
        <span class="agent-icon">AI</span>
        <span class="agent-main">
          <strong>${escapeHtml(formatTaskType(task?.task_type || "Agent"))}</strong>
          <small>${escapeHtml(agent.name)} · ${escapeHtml(agent.id)}</small>
        </span>
        <span class="agent-latest">
          <small>Last activity</small>
          <span>${task ? formatDate(task.started_at) : "No activity yet"}</span>
        </span>
        <span class="status status-${escapeHtml(task?.status || agent.status)}">
          ${escapeHtml(formatStatus(task?.status || agent.status))}
        </span>
        <span class="chevron">${expanded ? "−" : "+"}</span>
      </button>
      ${expanded ? renderAgentDetails(agent) : ""}
    </article>`;
}

function renderAgentDetails(agent) {
  const task = agent.latest_task;
  if (!task) {
    return '<div class="agent-details"><p class="muted">This agent has not run a task yet.</p></div>';
  }
  return `
    <div class="agent-details">
      <div class="detail-grid">
        <div><span>Task ID</span><strong>${escapeHtml(task.id)}</strong></div>
        <div><span>Status</span><strong class="status status-${escapeHtml(task.status)}">${escapeHtml(formatStatus(task.status))}</strong></div>
        <div><span>Task type</span><strong>${escapeHtml(formatTaskType(task.task_type || "Agent task"))}</strong></div>
        <div><span>Started</span><strong>${formatDate(task.started_at)}</strong></div>
      </div>
      <div class="task-prompt">
        <span class="prompt-label">Requested work</span>
        <strong>“${escapeHtml(task.prompt || "No prompt recorded") }”</strong>
      </div>
      ${task.error_message ? `<p class="error-state">${escapeHtml(task.error_message)}</p>` : ""}
      <div class="detail-actions">
        <button type="button" class="trace-button" data-task-id="${escapeHtml(task.id)}">View task trace</button>
        <button type="button" class="secondary-button" data-agent-id="${escapeHtml(agent.id)}">View past tasks</button>
      </div>
    </div>`;
}

async function loadAgentTasks(agentId) {
  try {
    const response = await fetchJson(`/agents/${encodeURIComponent(agentId)}/tasks`);
    const agent = advisors.flatMap(advisor => advisor.agents).find(item => item.id === agentId);
    const currentTaskId = agent?.latest_task?.id;
    const pastTasks = response.tasks.filter(task => task.id !== currentTaskId);
    const modal = document.createElement("dialog");
    modal.className = "trace-dialog";
    modal.innerHTML = `
      <form method="dialog">
        <button class="dialog-close" aria-label="Close">×</button>
        <p class="eyebrow">Task history</p>
        <h2>${escapeHtml(agent?.name || "Agent")}</h2>
        ${pastTasks.length ? `<ol class="task-history">${pastTasks.map(task => `
          <li>
            <div>
              <strong>${escapeHtml(formatTaskType(task.task_type || "Agent task"))}</strong>
              <span>${escapeHtml(formatStatus(task.status))} · ${formatDate(task.started_at)}</span>
              <p>${escapeHtml(task.prompt || "No prompt recorded")}</p>
            </div>
            <button type="button" class="secondary-button" data-task-id="${escapeHtml(task.id)}">View trace</button>
          </li>`).join("")}          </ol>` : '<p class="muted">This agent has no other recorded tasks yet.</p>'}
      </form>`;
    document.body.appendChild(modal);
    modal.addEventListener("close", () => modal.remove());
    modal.querySelectorAll("[data-task-id]").forEach(button => {
      button.addEventListener("click", () => loadTaskDetails(button.dataset.taskId));
    });
    modal.showModal();
  } catch (error) {
    errorState.textContent = "Could not load this agent's task history.";
    errorState.hidden = false;
  }
}

async function loadTaskDetails(taskId) {
  try {
    const task = await fetchJson(`/tasks/${encodeURIComponent(taskId)}`);
    const modal = document.createElement("dialog");
    modal.className = "trace-dialog";
    modal.innerHTML = `
      <form method="dialog">
        <button class="dialog-close" aria-label="Close">×</button>
        <p class="eyebrow">Execution trace</p>
        <h2>${escapeHtml(formatTaskType(task.task_type || "Task"))}</h2>
        <div class="task-prompt">
          <span class="prompt-label">Requested work</span>
          <strong>“${escapeHtml(task.prompt || "No prompt recorded") }”</strong>
        </div>
        <ol class="timeline">${(task.events || []).map(event => `
          <li class="${escapeHtml(event.status)}">
            <strong>${escapeHtml(formatLabel(event.tool_name || event.event_type))}</strong>
            <span>${escapeHtml(formatLabel(event.event_type))}${event.duration_ms != null ? ` · ${event.duration_ms} ms` : ""}</span>
            ${event.error_message ? `<em>${escapeHtml(event.error_message)}</em>` : ""}
          </li>`).join("")}</ol>
      </form>`;
    document.body.appendChild(modal);
    modal.addEventListener("close", () => modal.remove());
    modal.showModal();
  } catch (error) {
    errorState.textContent = "Could not load the selected task trace.";
    errorState.hidden = false;
  }
}

function initials(name) {
  return name.split(" ").map(part => part[0]).slice(0, 2).join("").toUpperCase();
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "Not started";
}

function formatTaskType(value) {
  return formatLabel(value);
}

function formatStatus(value) {
  return formatLabel(value);
}

function formatLabel(value) {
  return String(value ?? "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, character => character.toUpperCase());
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[character]));
}

loadAdvisors();
setInterval(loadAdvisors, 3000);
