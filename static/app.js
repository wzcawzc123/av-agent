(() => {
  const TOKEN_KEY = "av_access_token";
  const token = () => localStorage.getItem(TOKEN_KEY) || "";
  const authHeaders = () => ({ "Content-Type": "application/json", "X-Access-Token": token() });

  let projectId = null;
  let currentTaskId = null;
  let editingProviderId = null;
  let providersCache = [];

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
    let replyHtml = data.reply.replace(/\n/g, "<br>");
    if (data.files && data.files.length) {
      replyHtml += "<br>" + data.files.map(f =>
        `<a href="/api/download?path=${encodeURIComponent(f)}" class="chat-dl">⬇ 下载 ${f.split("/").pop()}</a>`).join(" ");
    }
    addMsg(replyHtml, "bot");
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
      const keyState = p.has_api_key ? `🔑 已填` : `🔒 未填 Key`;
      const models = (p.models || []).map((m) => m.model_id).join(", ") || "无模型";
      return `
      <div class="item-card">
        <div class="item-title">${p.name} <span style="color:#6b7280;font-weight:400">${p.is_built_in ? "内置" : "自定义"}</span></div>
        <div class="item-meta">${p.provider_type} ｜ ${keyState} ｜ 模型：${models}</div>
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
      if (r) addMsg(`已切换到 ${p.name}。`, "bot");
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
    $("pe-key").value = ""; // 掩码不回填，留空表示不修改
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
      <tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  }

  function engDownload(path) {
    return `<div class="eng-dl"><a href="/api/download?path=${encodeURIComponent(path)}">⬇ 下载 Excel（${path.split("/").pop()}）</a></div>`;
  }

  async function runEngine(url, body, resultId) {
    const box = $(resultId);
    box.innerHTML = "<div class='item-card'>计算中…</div>";
    const r = await api(url, { method: "POST", body: JSON.stringify(body) });
    if (!r) { box.innerHTML = ""; return null; }
    const data = await r.json();
    if (!r.ok) { box.innerHTML = `<div class='item-card' style='color:#b91c1c'>${data.detail || "请求失败"}</div>`; return null; }
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
        const m = part.match(/^([^\d×x*]+)\s*[×x*]\s*(\d+)$/);
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
