const API_BASE_URL = ["localhost", "127.0.0.1"].includes(window.location.hostname)
  ? "http://127.0.0.1:8000"
  : "https://s5qdehj6bi.execute-api.us-east-1.amazonaws.com";

const advisorList = document.querySelector("#advisor-list");
const agentList = document.querySelector("#agent-list");
const advisorTitle = document.querySelector("#advisor-title");
const advisorEmail = document.querySelector("#advisor-email");
const loadingState = document.querySelector("#loading-state");
const errorState = document.querySelector("#error-state");
const connectionBadge = document.querySelector("#connection-badge");
const activeTaskCount = document.querySelector("#active-task-count");
const completedTaskCount = document.querySelector("#completed-task-count");
const failedTaskCount = document.querySelector("#failed-task-count");
const advisorCount = document.querySelector("#advisor-count");
const advisorCountLabel = document.querySelector("#advisor-count-label");
let advisors = [];
let selectedAdvisorId = null;
let selectedTasks = [];
let renderedAdvisorSignature = "";
let renderedTaskSignature = "";
let taskActivityLoaded = false;
let knownTaskIds = null;
let notifiedAdvisorIds = new Set();
let advisorNotificationTimers = new Map();
let highlightedTaskIds = new Set();
let taskHighlightTimers = new Map();
let initialLoad = true;
const ALL_ADVISORS_ID = "__all__";

async function fetchJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) throw new Error(`API request failed (${response.status})`);
  return response.json();
}

function announceNewTasks(tasks) {
  const currentTaskIds = new Set(tasks.map(task => task.id));
  if (knownTaskIds === null) {
    knownTaskIds = currentTaskIds;
    return;
  }
  const newTasks = tasks.filter(task => !knownTaskIds.has(task.id));
  knownTaskIds = currentTaskIds;
  if (!newTasks.length) return;

  newTasks.forEach(task => {
    highlightedTaskIds.add(task.id);
    const existingTimer = taskHighlightTimers.get(task.id);
    if (existingTimer) window.clearTimeout(existingTimer);
    const timer = window.setTimeout(() => {
      highlightedTaskIds.delete(task.id);
      taskHighlightTimers.delete(task.id);
      if (selectedTasks.some(selectedTask => selectedTask.id === task.id)) {
        renderSelectedAdvisor();
      }
    }, 3600);
    taskHighlightTimers.set(task.id, timer);
  });
  const advisorIds = [...new Set(newTasks.map(task => {
    const advisor = advisors.find(item => item.id === task.advisor_id);
    return advisor?.id || task.advisor_id;
  }))];
  advisorIds.forEach(advisorId => showAdvisorNotification(advisorId));
}

function showAdvisorNotification(advisorId) {
  notifiedAdvisorIds.add(advisorId);
  renderAdvisors();
  const existingTimer = advisorNotificationTimers.get(advisorId);
  if (existingTimer) window.clearTimeout(existingTimer);
  const timer = window.setTimeout(() => {
    notifiedAdvisorIds.delete(advisorId);
    advisorNotificationTimers.delete(advisorId);
    renderAdvisors();
  }, 2200);
  advisorNotificationTimers.set(advisorId, timer);
}

async function loadAdvisors() {
  if (initialLoad) loadingState.hidden = false;
  try {
    const response = await fetchJson("/advisors");
    advisors = response.advisors;
    advisorCount.textContent = advisors.length;
    advisorCountLabel.textContent = `${advisors.length} covered`;
    if (!selectedAdvisorId || (
      selectedAdvisorId !== ALL_ADVISORS_ID
      && !advisors.some(advisor => advisor.id === selectedAdvisorId)
    )) {
      selectedAdvisorId = ALL_ADVISORS_ID;
    }
    const advisorSignature = JSON.stringify(advisors);
    if (advisorSignature !== renderedAdvisorSignature) {
      renderedAdvisorSignature = advisorSignature;
      renderAdvisors();
    }
    await loadSelectedAdvisorTasks();
    connectionBadge.textContent = `Connected · ${API_BASE_URL.includes("127.0.0.1") ? "Local API" : "Cloud API"}`;
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
  const sortedAdvisors = [...advisors].sort((left, right) => {
    const latestTaskTime = advisor => advisor.agents.reduce((latest, agent) => {
      const task = agent.latest_task;
      const timestamp = task?.started_at || task?.created_at || agent.created_at || "";
      return timestamp > latest ? timestamp : latest;
    }, "");
    return latestTaskTime(right).localeCompare(latestTaskTime(left));
  });
  const allAdvisorsButton = `
    <button type="button" class="advisor-item all-advisors-item ${selectedAdvisorId === ALL_ADVISORS_ID ? "selected" : ""}"
      data-advisor-id="${ALL_ADVISORS_ID}">
      <span class="avatar all-advisors-avatar">ALL</span>
      <span class="advisor-name">All advisors</span>
      <span class="all-advisors-count">${advisors.length}</span>
    </button>`;
  advisorList.innerHTML = allAdvisorsButton + sortedAdvisors.map(advisor => `
    <button type="button" class="advisor-item ${advisor.id === selectedAdvisorId ? "selected" : ""}"
      data-advisor-id="${escapeHtml(advisor.id)}">
      <span class="avatar">${escapeHtml(initials(advisor.name))}</span>
      <span class="advisor-name">${escapeHtml(advisor.name)}</span>
      ${notifiedAdvisorIds.has(advisor.id) ? '<span class="advisor-task-notification">New task</span>' : ""}
    </button>`).join("");
  advisorList.querySelectorAll(".advisor-item").forEach(button => {
    button.addEventListener("click", () => {
      selectedAdvisorId = button.dataset.advisorId;
      renderedTaskSignature = "";
      taskActivityLoaded = false;
      renderAdvisors();
      loadSelectedAdvisorTasks();
    });
  });
}

function renderSelectedAdvisor() {
  const advisor = advisors.find(item => item.id === selectedAdvisorId);
  if (selectedAdvisorId === ALL_ADVISORS_ID) {
    advisorTitle.textContent = "All advisors";
    advisorEmail.textContent = "Combined task activity";
  } else if (!advisor) {
    advisorTitle.textContent = "Select an advisor";
    advisorEmail.textContent = "";
    agentList.innerHTML = '<p class="muted empty-task-state">Select an advisor to view their task activity.</p>';
    return;
  } else {
    advisorTitle.textContent = advisor.name;
    advisorEmail.textContent = advisor.email;
  }
  agentList.innerHTML = selectedTasks.length
    ? selectedTasks.map(renderTaskActivity).join("")
    : '<p class="muted empty-task-state">This advisor has no recorded tasks yet.</p>';
  agentList.querySelectorAll("[data-task-id]").forEach(button => {
    button.addEventListener("click", () => loadTaskDetails(button.dataset.taskId));
  });
}

async function loadSelectedAdvisorTasks() {
  const advisorId = selectedAdvisorId;
  const advisor = advisors.find(item => item.id === advisorId);
  if (!advisor && advisorId !== ALL_ADVISORS_ID) {
    selectedTasks = [];
    renderSelectedAdvisor();
    return;
  }
  if (advisorId === ALL_ADVISORS_ID) {
    advisorTitle.textContent = "All advisors";
    advisorEmail.textContent = "Combined task activity";
  } else {
    advisorTitle.textContent = advisor.name;
    advisorEmail.textContent = advisor.email;
  }
  if (!taskActivityLoaded) {
    agentList.innerHTML = '<p class="muted empty-task-state">Loading task activity...</p>';
  }
  try {
    const response = await fetchJson("/tasks");
    if (advisorId !== selectedAdvisorId) return;
    announceNewTasks(response.tasks);
    activeTaskCount.textContent = response.tasks.filter(task => task.status === "running").length;
    completedTaskCount.textContent = response.tasks.filter(task => task.status === "completed").length;
    failedTaskCount.textContent = response.tasks.filter(task => task.status === "failed").length;
    selectedTasks = response.tasks
      .filter(task => advisorId === ALL_ADVISORS_ID || task.advisor_id === advisorId)
      .sort((left, right) => {
        const leftTime = left.started_at || left.created_at || "";
        const rightTime = right.started_at || right.created_at || "";
        return rightTime.localeCompare(leftTime);
      });
    const taskSignature = JSON.stringify(selectedTasks);
    if (taskSignature !== renderedTaskSignature) {
      renderedTaskSignature = taskSignature;
      renderSelectedAdvisor();
    }
    taskActivityLoaded = true;
  } catch (error) {
    if (advisorId !== selectedAdvisorId) return;
    agentList.innerHTML = '<p class="muted empty-task-state">Could not load task activity.</p>';
  }
}

function renderTaskActivity(task) {
  return `
    <article class="task-card ${highlightedTaskIds.has(task.id) ? "new-task" : ""}">
      <div class="task-card-main">
        <div class="task-card-heading">
          <strong>${escapeHtml(formatTaskType(task.task_type || "Agent task"))}</strong>
        </div>
        <p class="task-description">${escapeHtml(task.prompt || "No prompt recorded")}</p>
      </div>
      <p class="task-agent"><strong>${escapeHtml(task.agent_name || task.agent_id || "Unknown agent")}</strong><br><span class="muted">${escapeHtml(task.agent_id || "Unknown ID")}</span></p>
      <span class="status status-${escapeHtml(task.status)}">${escapeHtml(formatStatus(task.status))}</span>
      <div class="task-card-meta">
        <span>${escapeHtml(formatDate(task.started_at || task.created_at))}</span>
        <button type="button" class="trace-button" data-task-id="${escapeHtml(task.id)}">View trace</button>
      </div>
    </article>`;
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
