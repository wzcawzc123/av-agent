(() => {
  const TOKEN_KEY = "av_access_token";
  const token = () => localStorage.getItem(TOKEN_KEY) || "";
  const authHeaders = () => ({ "Content-Type": "application/json", "X-Access-Token": token() });

  let projectId = null;
  let currentTaskId = null;
  let editingProviderId = null;
  let providersCache = [];
  let lastBom = null;          // 最近一次生成的主设备清单（存为模板用）
  let lastSlots = {};
  let productsCache = [];
  let allProducts = [];

  const $ = (id) => document.getElementById(id);
  const chatLog = $("chat-log");
  const chatInput = $("chat-input");
  const confirmCard = $("confirm-card");
  const progressBar = $("progress-bar");
  const progressFill = $("progress-fill");
  const progressText = $("progress-text");
  const fileList = $("file-list");

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function addMsg(text, who) {
    const div = document.createElement("div");
    div.className = `msg ${who}`;
    div.innerHTML = text;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function ensureToken() {
    if (!token()) {
      const q = new URLSearchParams(location.search).get("token");
      if (q) { localStorage.setItem(TOKEN_KEY, q.trim()); }
      else { const t = prompt("请输入访问口令："); if (t) localStorage.setItem(TOKEN_KEY, t.trim()); }
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

  // ===== 鉴权下载（fetch blob，绕开 header 限制） =====
  async function download(path) {
    ensureToken();
    const r = await fetch(`/api/download?path=${encodeURIComponent(path)}`, { headers: authHeaders() });
    if (!r.ok) { addMsg(`下载失败（${r.status}）`, "bot"); return; }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = path.split("/").pop();
    a.click();
    URL.revokeObjectURL(url);
  }
  window.__download = download;

  // ===== 主 Tab 切换 =====
  document.querySelectorAll("#main-tabs .seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#main-tabs .seg-btn").forEach((b) => b.classList.toggle("active", b === btn));
      const v = btn.dataset.view;
      $("chat-view").hidden = v !== "chat";
      $("projects-view").hidden = v !== "projects";
      if (v === "projects") loadProjects();
    });
  });

  // ===== 示例需求快捷输入 =====
  $("suggest-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    chatInput.value = chip.textContent.trim();
    chatInput.focus();
  });

  // ===== 聊天主流程 =====
  chatLog.addEventListener("click", (e) => {
    if (e.target.id === "btn-confirm") startGeneration();
    if (e.target.id === "btn-revise") addMsg("请告诉我需要修改的地方：", "bot");
    const dl = e.target.closest("[data-dl]");
    if (dl) download(dl.dataset.dl);
  });
  fileList.addEventListener("click", (e) => {
    const el = e.target.closest("[data-dl]");
    if (el) download(el.dataset.dl);
  });

  $("chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = "";
    addMsg(escapeHtml(text), "user");
    const r = await api("/api/chat", { method: "POST", body: JSON.stringify({ text, project_id: projectId }) });
    if (!r) return;
    const data = await r.json();
    projectId = data.project_id;
    let replyHtml = escapeHtml(data.reply).replace(/\n/g, "<br>");
    if (data.files && data.files.length) {
      replyHtml += "<br>" + data.files.map(f =>
        `<button class="chat-dl" data-dl="${encodeURIComponent(f)}">⬇ 下载 ${f.split("/").pop()}</button>`).join(" ");
    }
    addMsg(replyHtml, "bot");
    if (data.status === "CONFIRMING") {
      confirmCard.hidden = false;
      confirmCard.innerHTML = `<div>${escapeHtml(data.reply).replace(/\n/g, "<br>")}</div>
        <button id="btn-confirm">确认，开始生成</button>
        <button id="btn-revise" class="revise-btn">修改需求</button>`;
    } else {
      confirmCard.hidden = true;
    }
  });

  async function startGeneration() {
    confirmCard.hidden = true;
    fileList.innerHTML = "";
    lastBom = null;
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
          lastBom = (event.result && event.result.bom) || null;
          lastSlots = {
            scene: (event.result && event.result.scene) || "",
            brand: (event.result && event.result.brand) || "",
          };
          const files = (event.result && event.result.files) || {};
          const kinds = { doc: "📄 Word 方案", excel: "📊 Excel 清单", ppt: "📽 PPT 方案", pdf: "📕 PDF 方案", deviation: "📋 偏离表" };
          for (const [kind, path] of Object.entries(files)) {
            const a = document.createElement("button");
            a.className = "file-btn";
            a.dataset.dl = path;
            a.innerHTML = `${kinds[kind] || kind} → ${path.split("/").pop()}`;
            fileList.appendChild(a);
          }
          if (lastBom && lastBom.length) {
            const btn = document.createElement("button");
            btn.className = "file-btn save-tpl-btn";
            btn.textContent = "⭐ 存为模板";
            btn.addEventListener("click", openSaveTemplate);
            fileList.appendChild(btn);
          }
        } else {
          addMsg(`生成失败：${JSON.stringify((event.result && event.result.errors) || {})}`, "bot");
        }
      }
    };
  }

  // ===== 项目视图 =====
  const STATUS_CN = { IDLE: "新建", COLLECTING: "需求收集中", CONFIRMING: "待确认", GENERATING: "生成中", DELIVERED: "已完成" };
  const KIND_ICON = { doc: "📄", excel: "📊", ppt: "📽", pdf: "📕", deviation: "📋" };

  async function loadProjects() {
    const r = await api("/api/projects");
    if (!r) return;
    const rows = await r.json();
    const box = $("project-list");
    $("project-count").textContent = rows.length ? `共 ${rows.length} 个项目` : "";
    if (!rows.length) {
      box.innerHTML = `<div class="empty-state">
        <div class="empty-icon">🗂</div>
        <div class="empty-title">还没有项目</div>
        <div class="empty-desc">在「方案对话」中输入需求并生成方案后，项目会出现在这里，可随时回看与下载。</div>
        <button class="btn-primary empty-btn" id="empty-go-chat">去生成第一个方案</button>
      </div>`;
      $("empty-go-chat").addEventListener("click", () => {
        document.querySelector('#main-tabs .seg-btn[data-view="chat"]').click();
      });
      return;
    }
    box.innerHTML = rows.map((p) => {
      let req = "";
      try {
        const j = JSON.parse(p.requirement_json || "{}");
        req = [j.scene, j.area ? `${j.area}㎡` : "", (j.systems || []).join("、")].filter(Boolean).join(" · ");
      } catch (e) { req = ""; }
      return `<div class="project-card" data-id="${p.id}">
        <div class="project-head">
          <div class="project-name">${escapeHtml(p.name)}</div>
          <span class="status-badge status-${p.status}">${STATUS_CN[p.status] || p.status}</span>
        </div>
        <div class="project-meta">${escapeHtml(req) || "未填写需求"}</div>
        <div class="project-actions">
          <button class="pact open" data-act="open">继续对话</button>
          <button class="pact files" data-act="files">查看文件</button>
          <button class="pact del" data-act="del">删除</button>
        </div>
        <div class="project-files" hidden></div>
      </div>`;
    }).join("");
  }

  async function onProjectAction(e) {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const card = btn.closest(".project-card");
    const pid = card.dataset.id;
    const act = btn.dataset.act;
    if (act === "open") {
      projectId = parseInt(pid, 10);
      document.querySelector('#main-tabs .seg-btn[data-view="chat"]').click();
      addMsg(`已切换到项目 #${pid}，可直接补充需求或重新生成。`, "bot");
    } else if (act === "del") {
      if (!confirm(`确认删除项目 #${pid}？产出文件将一并删除。`)) return;
      const r = await api(`/api/projects/${pid}`, { method: "DELETE" });
      if (r) loadProjects();
    } else if (act === "files") {
      const box = card.querySelector(".project-files");
      if (!box.hidden) { box.hidden = true; return; }
      const r = await api(`/api/projects/${pid}/files`);
      if (!r) return;
      const data = await r.json();
      box.hidden = false;
      if (!data.files.length) {
        box.innerHTML = `<div class="toolbar-hint">暂无产出文件</div>`;
        return;
      }
      box.innerHTML = data.files.map((f) =>
        `<button class="file-btn" data-dl="${encodeURIComponent(f.path)}">${KIND_ICON[f.kind] || "📁"} ${escapeHtml(f.name)}</button>`).join("");
      box.querySelectorAll("[data-dl]").forEach((el) => el.addEventListener("click", () => download(el.dataset.dl)));
    }
  }

  // ===== 存为模板 =====
  function openSaveTemplate() {
    $("st-name").value = (lastSlots.scene || "项目") + "配置模板";
    $("st-scene").value = lastSlots.scene || "";
    $("st-brand").value = lastSlots.brand || "";
    $("st-result").textContent = "";
    $("save-tpl-drawer").hidden = false;
  }
  $("st-close").addEventListener("click", () => { $("save-tpl-drawer").hidden = true; });
  $("st-save").addEventListener("click", async () => {
    const name = $("st-name").value.trim();
    if (!name) { $("st-result").textContent = "请填写模板名称"; return; }
    if (!lastBom || !lastBom.length) { $("st-result").textContent = "没有可保存的清单"; return; }
    const r = await api("/api/templates/from-bom", {
      method: "POST",
      body: JSON.stringify({
        name, scene: $("st-scene").value.trim(), area: lastSlots.area || 0,
        systems: lastSlots.systems || [], config_level: lastSlots.config_level || "",
        brand: $("st-brand").value.trim(), rows: lastBom,
      }),
    });
    if (!r) return;
    $("st-result").textContent = "已保存到模板库 ✅";
    setTimeout(() => { $("save-tpl-drawer").hidden = true; }, 900);
  });

  // ===== 模型提供商管理 =====
  $("btnSettings").addEventListener("click", async () => {
    $("settings-drawer").hidden = false;
    await loadProviders();
  });
  $("cfg-close").addEventListener("click", () => { $("settings-drawer").hidden = true; });

  async function loadProviders() {
    const r = await api("/api/providers");
    if (!r) return;
    providersCache = await r.json();
    const box = $("prov-list");
    if (!providersCache.length) {
      box.innerHTML = `<div class="item-card">暂无提供商</div>`;
      return;
    }
    box.innerHTML = providersCache.map((p) => {
      const keyState = p.has_api_key ? "🔑 已填" : "🔒 未填 Key";
      const models = (p.models || []).map((m) => m.model_id).join(", ") || "无模型";
      return `
      <div class="item-card">
        <div class="item-title">${escapeHtml(p.name)} <span style="color:#6b7280;font-weight:400">${p.is_built_in ? "内置" : "自定义"}</span></div>
        <div class="item-meta">${p.provider_type} ｜ ${keyState} ｜ 模型：${escapeHtml(models)}</div>
        <div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap">
          <button class="item-del" data-act="edit" data-id="${p.id}">编辑</button>
          <button class="item-del" style="background:#e0f2fe;color:#0369a1" data-act="select" data-id="${p.id}">设为当前</button>
          ${p.is_built_in ? `
            <button class="item-del" style="background:#e0e7ff;color:#3730a3" data-act="reset" data-id="${p.id}">重置</button>
            <button class="item-del" style="background:#f1f5f9;color:#334155" data-act="copy" data-id="${p.id}">复制</button>` : `
            <button class="item-del" style="background:#fee2e2;color:#b91c1c" data-act="del" data-id="${p.id}">删除</button>`}
        </div>
      </div>`;
    }).join("");
    box.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => providerAction(btn.dataset.act, btn.dataset.id));
    });
  }

  async function providerAction(act, id) {
    if (act === "edit") {
      const p = providersCache.find((x) => x.id === id);
      openProviderEditor(p);
      return;
    }
    if (act === "select") {
      const p = providersCache.find((x) => x.id === id);
      const model = (p.models && p.models[0] && p.models[0].model_id) || "";
      const r = await api("/api/settings/model", {
        method: "PUT",
        body: JSON.stringify({ provider: id, model }),
      });
      if (r) addMsg(`已切换到 ${escapeHtml(p.name)}。`, "bot");
      await loadProviders();
      return;
    }
    if (act === "del") {
      const r = await api(`/api/providers/${id}`, { method: "DELETE" });
      if (r) await loadProviders();
      return;
    }
    if (act === "copy") {
      const r = await api(`/api/providers/${id}/copy`, { method: "POST" });
      if (r) await loadProviders();
      return;
    }
    if (act === "reset") {
      const r = await api(`/api/providers/${id}/reset`, { method: "POST" });
      if (r) await loadProviders();
      return;
    }
  }

  $("prov-add").addEventListener("click", () => {
    editingProviderId = null;
    $("pe-name").value = "";
    $("pe-base").value = "";
    $("pe-key").value = "";
    $("pe-models").value = "";
    $("pe-type").value = "openai_compatible";
    $("prov-edit-title").textContent = "新增自定义提供商";
    $("pe-result").textContent = "";
    $("settings-drawer").hidden = true;
    $("prov-edit-drawer").hidden = false;
  });

  function openProviderEditor(p) {
    editingProviderId = p.id;
    $("pe-name").value = p.name;
    $("pe-base").value = p.base_url;
    $("pe-key").value = "";
    $("pe-models").value = (p.models || []).map((m) => m.model_id).join(",");
    $("pe-type").value = p.provider_type || "openai_compatible";
    $("prov-edit-title").textContent = `编辑：${p.name}${p.is_built_in ? "（内置）" : ""}`;
    $("pe-result").textContent = p.has_api_key ? "已配置 API Key，留空则不修改。" : "";
    $("settings-drawer").hidden = true;
    $("prov-edit-drawer").hidden = false;
  }

  $("pe-close").addEventListener("click", () => {
    $("prov-edit-drawer").hidden = true;
    $("settings-drawer").hidden = false;
    loadProviders();
  });

  $("pe-save").addEventListener("click", async () => {
    const body = {
      name: $("pe-name").value.trim(),
      base_url: $("pe-base").value.trim(),
      api_key: $("pe-key").value.trim(),
      provider_type: $("pe-type").value,
      models: ($("pe-models").value.split(",").map((s) => s.trim()).filter(Boolean))
        .map((m, i) => ({ model_id: m, display_name: m })),
    };
    if (!body.name) { $("pe-result").textContent = "请填写提供商名称"; return; }
    const r = editingProviderId
      ? await api(`/api/providers/${editingProviderId}`, { method: "PUT", body: JSON.stringify(body) })
      : await api("/api/providers", { method: "POST", body: JSON.stringify(body) });
    if (!r) return;
    $("pe-result").textContent = "已保存 ✅";
    setTimeout(() => { $("prov-edit-drawer").hidden = true; $("settings-drawer").hidden = false; loadProviders(); }, 400);
  });

  $("pe-fetch").addEventListener("click", async () => {
    if (!editingProviderId) { $("pe-result").textContent = "请先保存再拉取模型"; return; }
    const r = await api(`/api/providers/${editingProviderId}/fetch-models`, { method: "POST" });
    if (!r) return;
    const data = await r.json();
    $("pe-result").textContent = `拉取到 ${data.fetched.length} 个模型`;
    const p = providersCache.find((x) => x.id === editingProviderId);
    if (p) { $("pe-models").value = data.fetched.join(","); }
  });

  // ===== 产品库 =====
  $("btnProducts").addEventListener("click", async () => {
    $("products-drawer").hidden = false;
    await loadProducts();
  });
  $("prod-close").addEventListener("click", () => { $("products-drawer").hidden = true; });
  ["prod-search", "prod-brand", "prod-cat"].forEach((id) => {
    $(id).addEventListener("change", () => loadProducts());
    $(id).addEventListener("input", () => loadProducts());
  });

  async function loadProducts() {
    const q = encodeURIComponent($("prod-search").value.trim());
    const brand = encodeURIComponent($("prod-brand").value);
    const cat = encodeURIComponent($("prod-cat").value);
    const r = await api(`/api/products?q=${q}&brand=${brand}&category=${cat}`);
    if (!r) return;
    const rows = await r.json();
    productsCache = rows;
    if (!q && !brand && !cat) allProducts = rows;
    const pool = allProducts.length ? allProducts : rows;
    const box = $("prod-list");
    $("prod-count").textContent = rows.length ? `共 ${rows.length} 条` : "";
    // 动态填充筛选选项（保留当前选中）
    const brands = [...new Set(pool.map((p) => p.brand || "").filter(Boolean))].sort();
    const cats = [...new Set(pool.map((p) => p.category || "").filter(Boolean))].sort();
    fillSelect($("prod-brand"), brands, $("prod-brand").value);
    fillSelect($("prod-cat"), cats, $("prod-cat").value);
    if (!rows.length) {
      box.innerHTML = `<div class="item-card">没有匹配的产品，可调整筛选或上传 Excel。</div>`;
      return;
    }
    box.innerHTML = rows.map((p) => `
      <div class="item-card">
        <div class="item-title">${escapeHtml(p.name)}${p.model ? " / " + escapeHtml(p.model) : ""}</div>
        <div class="item-meta">
          分类：${escapeHtml(p.category || "—")}${p.brand ? " ｜ 品牌：" + escapeHtml(p.brand) : ""}
          ｜ 底价：${p.base_price ?? 0} ｜ 市场价：${p.market_price ?? 0}
        </div>
        <div class="prod-row">
          ${p.roles && p.roles.length ? `<span class="tag">${p.roles.map(escapeHtml).join(" ")}</span>` : ""}
          <button class="item-del prod-del" data-id="${p.id}">删除</button>
        </div>
      </div>`).join("");
    box.querySelectorAll(".prod-del").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("确认删除该产品？")) return;
        await api(`/api/products/${btn.dataset.id}`, { method: "DELETE" });
        await loadProducts();
      });
    });
  }

  function fillSelect(sel, values, current) {
    const prev = sel.value || current;
    sel.innerHTML = `<option value="">全部${sel === $("prod-brand") ? "品牌" : "系统/分类"}</option>` +
      values.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
    sel.value = values.includes(prev) ? prev : "";
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
    $("prod-file").value = "";
    await loadProducts();
  });

  // ===== 模板库 =====
  $("btnTemplates").addEventListener("click", async () => {
    $("templates-drawer").hidden = false;
    await loadTemplates();
  });
  $("tpl-close").addEventListener("click", () => { $("templates-drawer").hidden = true; });

  function tplFieldsVisible() {
    const t = $("tpl-type").value;
    $("tpl-config-fields").style.display = t === "config" ? "block" : "none";
    $("tpl-doc-fields").style.display = (t === "doc" || t === "ppt") ? "block" : "none";
  }
  $("tpl-type").addEventListener("change", tplFieldsVisible);
  tplFieldsVisible();

  async function loadTemplates() {
    const r = await api("/api/templates");
    if (!r) return;
    const rows = await r.json();
    const box = $("tpl-list");
    if (!rows.length) {
      box.innerHTML = `<div class="item-card">暂无模板，注册后生成时可套用；生成清单后也可一键「存为模板」。</div>`;
      return;
    }
    box.innerHTML = rows.map((t) => {
      let meta = "";
      if (t.type === "config") {
        const tags = [t.area ? `${t.area}㎡` : "", t.scene, t.config_level, t.brand].filter(Boolean);
        const sys = Array.isArray(t.systems) && t.systems.length ? t.systems.join("+") : "";
        meta = (tags.length ? tags.join(" · ") : "面积不限") + (sys ? ` ｜ 系统：${sys}` : "");
      } else {
        meta = [t.scene, t.brand].filter(Boolean).join(" · ") + (t.file_path ? " ｜ " + t.file_path : "");
      }
      return `
      <div class="item-card">
        <div class="item-title">${escapeHtml(t.name)} <span style="color:#6b7280;font-weight:400">(${t.type})</span></div>
        <div class="item-meta">${escapeHtml(meta)}${t.description ? " ｜ " + escapeHtml(t.description) : ""}</div>
        <button class="item-del" data-id="${t.id}" data-type="${t.type}">删除</button>
      </div>`;
    }).join("");
    box.querySelectorAll(".item-del").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("确认删除该模板？")) return;
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
      const area = parseInt($("tpl-area").value, 10) || 0;
      const systems = [...document.querySelectorAll("#tpl-sys input:checked")].map((c) => c.value);
      body = {
        name, type: "config", description: desc, file_path: "",
        area, scene: $("tpl-scene").value.trim(),
        systems, config_level: $("tpl-level").value, brand: $("tpl-brand").value.trim(),
      };
    } else {
      if (!path) { $("tpl-list").innerHTML = `<div class="item-card">请填写模板文件路径。</div>`; return; }
      body = {
        name, type, description: desc, file_path: path,
        scene: $("tpl-doc-scene").value.trim(), brand: $("tpl-doc-brand").value.trim(),
      };
    }
    const r = await api("/api/templates", { method: "POST", body: JSON.stringify(body) });
    if (!r) return;
    $("tpl-name").value = ""; $("tpl-path").value = ""; $("tpl-desc").value = "";
    $("tpl-area").value = ""; $("tpl-scene").value = ""; $("tpl-brand").value = "";
    $("tpl-level").value = ""; $("tpl-doc-scene").value = ""; $("tpl-doc-brand").value = "";
    document.querySelectorAll("#tpl-sys input:checked").forEach((c) => { c.checked = false; });
    await loadTemplates();
  });

  // ===== 软件更新 =====
  async function loadUpdateCfg() {
    const r = await api("/api/update/config");
    if (!r) return;
    $("upd-url").value = r.check_url || "";
    $("upd-token").placeholder = r.has_token ? "已配置 Token（留空不修改）" : "GitHub Token（私有仓库选填）";
  }
  $("upd-save").addEventListener("click", async () => {
    const url = $("upd-url").value.trim();
    const token = $("upd-token").value.trim();
    if (!url) { $("upd-result").textContent = "请填写更新检查地址。"; return; }
    const r = await api("/api/update/config", { method: "PUT", body: JSON.stringify({ check_url: url, token }) });
    if (!r) return;
    $("upd-token").value = "";
    $("upd-result").textContent = "更新配置已保存。";
    await loadUpdateCfg();
  });
  $("upd-check").addEventListener("click", async () => {
    $("upd-result").textContent = "正在检查更新…";
    const r = await api("/api/update/check");
    if (!r) return;
    if (r.has_update) {
      $("upd-result").innerHTML =
        `<div class="item-card">🎉 发现新版本 <b>v${r.latest_version}</b>（当前 v${r.current_version}）` +
        `<br>发布：${r.published_at || "未知"}` +
        (r.notes ? `<br>更新说明：${escapeHtml(r.notes.slice(0, 500))}` : "") +
        (r.download_url ? `<br><a href="${r.download_url}" target="_blank" rel="noopener">⬇ 下载新版本</a>` : "") +
        `</div>`;
    } else {
      $("upd-result").innerHTML = `<div class="item-card">✅ 已是最新版本 v${r.current_version}。</div>`;
    }
  });

  if (!token()) addMsg("请先点击右上角 ⚙️ 或发送消息时输入访问口令。", "bot");

  // ===== 方案工具箱（四引擎） =====
  $("btnTools").addEventListener("click", () => { $("engines-drawer").hidden = false; });
  $("eng-close").addEventListener("click", () => { $("engines-drawer").hidden = true; });

  function engTable(headers, rows) {
    if (!rows.length) return "<div class='item-card'>无数据</div>";
    return `<table class="eng-table"><thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead>
      <tbody>${rows.map(r => `<tr>${r.map(c => `<td>${escapeHtml(String(c ?? ""))}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  }

  function engDownload(path) {
    return `<div class="eng-dl"><button class="chat-dl" data-dl="${encodeURIComponent(path)}">⬇ 下载 Excel（${path.split("/").pop()}）</button></div>`;
  }

  async function runEngine(url, body, resultId) {
    const box = $(resultId);
    box.innerHTML = "<div class='item-card'>计算中…</div>";
    const r = await api(url, { method: "POST", body: JSON.stringify(body) });
    if (!r) { box.innerHTML = ""; return null; }
    const data = await r.json();
    if (!r.ok) { box.innerHTML = `<div class='item-card' style='color:#b91c1c'>${escapeHtml(data.detail || "请求失败")}</div>`; return null; }
    return data;
  }

  // 会议
  $("m-run").addEventListener("click", async () => {
    let code = $("m-code").value.trim();
    if (!code) {
      const scene = { "圆桌": 1, "阶梯": 2, "报告厅": 3 }[$("m-scene").value] || 1;
      const config = { "中配": 2, "高配": 1, "低配": 3 }[$("m-config").value] || 2;
      code = [$("m-len").value || 0, $("m-wid").value || 0, $("m-hei").value || 0,
              0, 0, scene, config, 0, $("m-mic").value, $("m-ant").value].join("-") + "-";
    }
    const data = await runEngine("/api/engines/meeting", { code, header: {} }, "m-result");
    if (!data) return;
    const rows = data.rows.map(r => [r.seq, r.name, r.spec, r.brand, r.model, r.qty, r.unit, r.price]);
    $("m-result").innerHTML = engTable(["#", "名称", "规格", "品牌", "型号", "数量", "单位", "价格"], rows) + engDownload(data.file);
  });

  // 广播
  $("bc-run").addEventListener("click", async () => {
    const text = $("bc-zones").value.trim();
    if (!text) { $("bc-result").innerHTML = "<div class='item-card'>请填写分区</div>"; return; }
    const zones = text.split("\n").map(l => l.trim()).filter(Boolean).map((line) => {
      const parts = line.split(/[,，]/).map(s => s.trim()).filter(Boolean);
      const zone = { zone: parts.shift() };
      for (const part of parts) {
        const m = part.match(/^(.+?)\s*[×x*]\s*(\d+)$/);
        if (m) zone[m[1]] = parseInt(m[2], 10);
      }
      return zone;
    });
    const data = await runEngine("/api/engines/broadcast", { zones, header: {} }, "bc-result");
    if (!data) return;
    const rows = data.zones_with_power.map(z => [z.zone, z.power_w, z.amplifier]);
    $("bc-result").innerHTML = engTable(["分区", "功率(W)×1.5", "功放选型"], rows) + engDownload(data.file);
  });

  // LED
  $("led-run").addEventListener("click", async () => {
    const body = {
      want_w_m: parseFloat($("led-w").value),
      want_h_m: parseFloat($("led-h").value),
      model: $("led-model").value,
      round_mode: $("led-mode").value,
      header: {},
    };
    if (!body.want_w_m || !body.want_h_m) { $("led-result").innerHTML = "<div class='item-card'>请填写宽高</div>"; return; }
    const data = await runEngine("/api/engines/led", body, "led-result");
    if (!data) return;
    const l = data.layout;
    const rows = [["模组排布", `${l.count_w} × ${l.count_h}`],
                  ["实际尺寸", `${l.actual_w_m}m × ${l.actual_h_m}m`],
                  ["分辨率", `${l.res_w} × ${l.res_h}`],
                  ["总像素(万)", l.total_pixels_wan],
                  ["功耗(kW)×1.3", l.power_kw],
                  ["电缆线径(mm²)", l.cable_mm2]];
    $("led-result").innerHTML = engTable(["项目", "结果"], rows) + engDownload(data.file);
  });

  // 偏离表
  $("dv-run").addEventListener("click", async () => {
    const items = $("dv-items").value.split("\n").map(s => s.trim()).filter(Boolean);
    const models = $("dv-models").value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
    if (!items.length) { $("dv-result").innerHTML = "<div class='item-card'>请填写招标参数</div>"; return; }
    const data = await runEngine("/api/engines/deviation",
      { tender_items: items, models, llm_enabled: $("dv-llm").checked }, "dv-result");
    if (!data) return;
    const rows = data.results.map((r, i) => [items[i], r.model, r.matched_param, r.score, r.confidence]);
    $("dv-result").innerHTML = engTable(["招标参数", "匹配型号", "匹配参数", "得分", "置信度"], rows)
      + `<div class='item-card' style='color:${data.low_confidence ? "#b45309" : "#16a34a"}'>低置信度 ${data.low_confidence} 条（将标为「待人工确认」）</div>`
      + engDownload(data.file);
  });
})();
