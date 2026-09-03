(() => {
  const TOKEN_KEY = "av_access_token";
  const token = () => localStorage.getItem(TOKEN_KEY) || "";
  const authHeaders = () => ({ "Content-Type": "application/json", "X-Access-Token": token() });

  let projectId = null;
  let currentTaskId = null;

  const $ = (id) => document.getElementById(id);
  const chatLog = $("chat-log");
  const chatInput = $("chat-input");
  const confirmCard = $("confirm-card");
  const progressBar = $("progress-bar");
  const progressFill = $("progress-fill");
  const progressText = $("progress-text");
  const fileList = $("file-list");

  function addMsg(text, who) {
    const div = document.createElement("div");
    div.className = `msg ${who}`;
    div.textContent = text;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function ensureToken() {
    if (!token()) {
      const t = prompt("请输入访问口令：");
      if (t) localStorage.setItem(TOKEN_KEY, t.trim());
    }
    return token();
  }

  async function api(path, opts = {}) {
    ensureToken();
    const r = await fetch(path, { ...opts, headers: { ...authHeaders(), ...(opts.headers || {}) } });
    if (r.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      addMsg("访问口令无效，请重新输入。", "bot");
      return null;
    }
    return r;
  }

  chatLog.addEventListener("click", (e) => {
    if (e.target.id === "btn-confirm") {
      startGeneration();
    }
    if (e.target.id === "btn-revise") {
      addMsg("请告诉我需要修改的地方：", "bot");
    }
  });

  $("chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = "";
    addMsg(text, "user");
    const r = await api("/api/chat", { method: "POST", body: JSON.stringify({ text, project_id: projectId }) });
    if (!r) return;
    const data = await r.json();
    projectId = data.project_id;
    addMsg(data.reply, "bot");
    if (data.status === "CONFIRMING") {
      confirmCard.hidden = false;
      confirmCard.innerHTML = `<div>${data.reply.replace(/\n/g, "<br>")}</div>
        <button id="btn-confirm">确认，开始生成</button>
        <button id="btn-revise" style="background:#e5e7eb;color:#374151">修改需求</button>`;
    } else {
      confirmCard.hidden = true;
    }
  });

  async function startGeneration() {
    confirmCard.hidden = true;
    fileList.innerHTML = "";
    const r = await api("/api/generate", { method: "POST", body: JSON.stringify({ project_id: projectId }) });
    if (!r) return;
    const { task_id } = await r.json();
    currentTaskId = task_id;
    progressBar.hidden = false;
    const es = new EventSource(`/api/tasks/${task_id}/stream`);
    es.onmessage = (ev) => {
      const event = JSON.parse(ev.data);
      if (event.type === "progress") {
        progressFill.style.width = `${event.percent}%`;
        progressText.textContent = `${event.percent}% ${event.message}`;
      } else if (event.type === "done") {
        es.close();
        progressBar.hidden = true;
        if (event.status === "success") {
          addMsg("生成完成 ✅", "bot");
          const files = event.result.files || {};
          for (const [kind, path] of Object.entries(files)) {
            const a = document.createElement("a");
            a.href = `/api/download?path=${encodeURIComponent(path)}`;
            a.textContent = `📄 ${kind} → ${path.split("/").pop()}`;
            fileList.appendChild(a);
          }
        } else {
          addMsg(`生成失败：${event.result?.errors ? JSON.stringify(event.result.errors) : ""}`, "bot");
        }
      }
    };
  }

  // ===== 产品库抽屉 =====
  $("btnProducts").addEventListener("click", async () => {
    $("products-drawer").hidden = false;
    await loadProducts();
  });
  $("prod-close").addEventListener("click", () => { $("products-drawer").hidden = true; });

  async function loadProducts() {
    const r = await api("/api/products");
    if (!r) return;
    const rows = await r.json();
    const box = $("prod-list");
    if (!rows.length) {
      box.innerHTML = `<div class="item-card">暂无产品，请上传公司产品 Excel。</div>`;
      return;
    }
    box.innerHTML = rows.map((p) => `
      <div class="item-card">
        <div class="item-title">${p.name}${p.model ? " / " + p.model : ""}</div>
        <div class="item-meta">分类：${p.category || "—"} ｜ 底价：${p.base_price ?? 0} ｜ 市场价：${p.market_price ?? 0}</div>
      </div>`).join("");
  }

  $("prod-upload").addEventListener("click", async () => {
    const file = $("prod-file").files[0];
    if (!file) { $("prod-result").textContent = "请先选择 Excel 文件"; return; }
    const fd = new FormData();
    fd.append("file", file);
    ensureToken();
    const r = await fetch("/api/products", { method: "POST", headers: { "X-Access-Token": token() }, body: fd });
    if (r.status === 401) { localStorage.removeItem(TOKEN_KEY); addMsg("访问口令无效，请重新输入。", "bot"); return; }
    const data = await r.json();
    $("prod-result").textContent = `导入完成：新增 ${data.inserted}，更新 ${data.updated}`;
    await loadProducts();
  });

  // ===== 模板库抽屉 =====
  $("btnTemplates").addEventListener("click", async () => {
    $("templates-drawer").hidden = false;
    await loadTemplates();
  });
  $("tpl-close").addEventListener("click", () => { $("templates-drawer").hidden = true; });

  function tplConfigFieldsVisible() {
    $("tpl-config-fields").style.display = $("tpl-type").value === "config" ? "flex" : "none";
  }
  $("tpl-type").addEventListener("change", tplConfigFieldsVisible);

  async function loadTemplates() {
    const r = await api("/api/templates");
    if (!r) return;
    const rows = await r.json();
    const box = $("tpl-list");
    if (!rows.length) {
      box.innerHTML = `<div class="item-card">暂无模板，注册后生成时可套用。</div>`;
      return;
    }
    box.innerHTML = rows.map((t) => `
      <div class="item-card">
        <div class="item-title">${t.name} <span style="color:#6b7280;font-weight:400">(${t.type})</span></div>
        <div class="item-meta">${t.type === "config" ? `适用 ${t.area}㎡` : t.file_path || "—"}${t.description ? " ｜ " + t.description : ""}</div>
        <button class="item-del" data-id="${t.id}" data-type="${t.type}">删除</button>
      </div>`).join("");
    box.querySelectorAll(".item-del").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await api(`/api/templates/${btn.dataset.id}?type=${btn.dataset.type}`, { method: "DELETE" });
        await loadTemplates();
      });
    });
  }

  $("tpl-add").addEventListener("click", async () => {
    const type = $("tpl-type").value;
    const name = $("tpl-name").value.trim();
    const path = $("tpl-path").value.trim();
    const desc = $("tpl-desc").value.trim();
    if (!name) { $("tpl-list").innerHTML = `<div class="item-card">请填写模板名称。</div>`; return; }
    let body = { name, type, description: desc, file_path: path };
    if (type === "config") {
      const area = parseInt($("tpl-area").value, 10);
      if (!area || area <= 0) { $("tpl-list").innerHTML = `<div class="item-card">请填写正确的适用面积（㎡）。</div>`; return; }
      body = { name, type: "config", description: desc, file_path: "", area, scene: $("tpl-scene").value.trim() };
    } else if (!path) {
      $("tpl-list").innerHTML = `<div class="item-card">请填写模板文件路径。</div>`;
      return;
    }
    const r = await api("/api/templates", { method: "POST", body: JSON.stringify(body) });
    if (!r) return;
    $("tpl-name").value = ""; $("tpl-path").value = ""; $("tpl-desc").value = "";
    $("tpl-area").value = ""; $("tpl-scene").value = "";
    await loadTemplates();
  });

  // ===== 设置抽屉 =====
  const PROVIDERS = ["deepseek", "openai", "qwen", "kimi", "glm", "wenxin", "gemini"];
  $("cfg-provider").innerHTML = PROVIDERS.map((p) => `<option value="${p}">${p}</option>`).join("");

  $("btnSettings").addEventListener("click", async () => {
    $("settings-drawer").hidden = false;
    const r = await api("/api/settings/model");
    if (!r) return;
    const cfg = await r.json();
    if (cfg.provider) $("cfg-provider").value = cfg.provider;
    $("cfg-key").value = cfg.api_key || "";
    $("cfg-model").value = cfg.model || "";
    $("cfg-base").value = cfg.base_url || "";
  });

  $("cfg-close").addEventListener("click", () => { $("settings-drawer").hidden = true; });

  $("cfg-save").addEventListener("click", async () => {
    const body = {
      provider: $("cfg-provider").value,
      api_key: $("cfg-key").value.trim(),
      model: $("cfg-model").value.trim(),
      base_url: $("cfg-base").value.trim(),
    };
    const r = await api("/api/settings/model", { method: "PUT", body: JSON.stringify(body) });
    if (r) {
      addMsg("模型配置已保存。", "bot");
      $("settings-drawer").hidden = true;
    }
  });

  // ===== 下载文件（带鉴权） =====
  async function download(path) {
    ensureToken();
    const r = await fetch(`/api/download?path=${encodeURIComponent(path)}`, { headers: authHeaders() });
    if (!r.ok) return;
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = path.split("/").pop();
    a.click();
    URL.revokeObjectURL(url);
  }
  window.__download = download;

  if (!token()) addMsg("请先点击右上角 ⚙️ 或发送消息时输入访问口令。", "bot");
})();
