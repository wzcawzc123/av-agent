/** 招标改单页面逻辑
 * - token 与当前项目与 app.js 共享（window.__token / __getProjectId），跨页面可用；
 * - 上传解析/匹配归属当前聊天项目（未选择时自动新建，返回真实 project_id）；
 * - 顶部快照下拉可回看同一项目的历次招标匹配结果（B7）。
 */
(function () {
  "use strict";

  function getToken() {
    if (window.__token && typeof window.__token === "function") return window.__token();
    return window.localStorage.getItem("av_access_token") || "";
  }
  function authHeaders(extra) {
    var h = Object.assign({ "X-Access-Token": getToken(), Accept: "application/json" }, extra || {});
    return h;
  }
  function currentProjectId() {
    if (window.__getProjectId && typeof window.__getProjectId === "function") return window.__getProjectId() || 0;
    return 0;
  }

  var lastResult = null; // {project_id, snapshot, items, merged, readonly}

  function el(id) { return document.getElementById(id); }
  function toast(msg) {
    if (window.__toast) return window.__toast(msg);
    alert(msg);
  }

  function statusColor(s) {
    return ({ matched: "var(--success)", partial: "var(--warning)", no_match: "var(--danger)",
      merged: "#999", extra: "var(--warning)", new: "#007aff" }[s] || "transparent");
  }

  function renderTable(items, readonly) {
    var wrap = el("tender-table-wrap");
    var saveCell = readonly ? "" : "<th>操作</th>";
    var html = '<table class="tender-table"><thead><tr><th>#</th><th>设备名称</th>' +
      "<th>品牌</th><th>型号</th><th>数量</th><th>状态</th><th>匹配型号</th><th>得分</th>" +
      "<th>备注</th>" + saveCell + "</tr></thead><tbody>";
    (items || []).forEach(function (it) {
      html += '<tr style="border-left:4px solid ' + statusColor(it.status) + '">' +
        "<td>" + it.idx + "</td><td>" + String(it.name || "").replace(/</g, "&lt;") + "</td>" +
        '<td><input class="edit-cell" data-field="brand" value="' + String(it.brand || "").replace(/"/g, "&quot;") + '" /></td>' +
        '<td><input class="edit-cell" data-field="model" value="' + String(it.model || "").replace(/"/g, "&quot;") + '" /></td>' +
        "<td>" + it.qty + "</td>" +
        '<td><span class="status-badge status-' + it.status + '">' + it.status + "</span></td>" +
        "<td>" + (it.matched_model || "-") + "</td>" +
        "<td>" + (it.score != null ? Number(it.score).toFixed(2) : "-") + "</td>" +
        '<td class="remark-cell">' + String(it.remark || "").replace(/</g, "&lt;") + "</td>" +
        (readonly ? "" : '<td><button class="save-row-btn" data-idx="' + it.idx + '" style="font-size:12px;padding:2px 8px;">保存</button></td>') +
        "</tr>";
    });
    html += "</tbody></table>";
    wrap.innerHTML = html;
    document.querySelectorAll(".save-row-btn").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var idx = btn.dataset.idx;
        var body = {};
        btn.closest("tr").querySelectorAll(".edit-cell").forEach(function (inp) { body[inp.dataset.field] = inp.value; });
        try {
          var r = await fetch("/api/tender/" + lastResult.project_id + "/rows/" + idx, {
            method: "PUT", headers: authHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify(body),
          });
          if (r.ok) { btn.textContent = "✓"; setTimeout(function () { btn.textContent = "保存"; }, 1500); }
          else { var e = await r.json().catch(function () { return { detail: "保存失败" }; }); toast(e.detail || "保存失败"); }
        } catch (err) { toast("保存失败：" + err.message); }
      });
    });
  }


  function showResult(data, opts) {
    opts = opts || {};
    lastResult = { project_id: data.project_id, snapshot: data.snapshot, items: data.items, readonly: !!opts.readonly };
    el("tender-busy").style.display = "none";
    el("tender-result").style.display = "block";
    var n = data.items.length;
    var matched = data.items.filter(function (i) { return i.status === "matched"; }).length;
    var partial = data.items.filter(function (i) { return i.status === "partial"; }).length;
    var noMatch = data.items.filter(function (i) { return i.status === "no_match"; }).length;
    var txt = "共 " + n + " 项设备需求，其中 " + matched + " 项已匹配，" + partial +
      " 项部分匹配，" + noMatch + " 项未匹配" +
      (data.merged > 0 ? "，" + data.merged + " 项已合并" : "") +
      (opts.readonly ? " ｜ 历史快照（只读）" : "") + " ｜ 快照: " + data.snapshot;
    el("tender-summary").textContent = txt;
    renderTable(data.items, opts.readonly);
  }

  async function loadSnapshot(pid, snap, readonly) {
    var r = await fetch("/api/tender/" + pid + "/snapshots/" + snap, { headers: authHeaders() });
    if (!r.ok) { var e = await r.json().catch(function () { return { detail: "加载快照失败" }; }); toast(e.detail || "加载快照失败"); return; }
    var d = await r.json();
    showResult({ project_id: d.project_id, snapshot: d.snapshot, items: d.rows, merged: 0 }, { readonly: readonly });
  }

  async function refreshSnapshots(pid) {
    var sel = el("tender-snapshot-select");
    if (!pid) { sel.style.display = "none"; return; }
    var r = await fetch("/api/tender/" + pid + "/snapshots", { headers: authHeaders() });
    if (!r.ok) { sel.style.display = "none"; return; }
    var d = await r.json();
    var snaps = (d.snapshots || []).slice().sort(function (a, b) { return a.snapshot < b.snapshot ? 1 : -1; });
    if (!snaps.length) { sel.style.display = "none"; return; }
    sel.style.display = "";
    var prev = sel.value;
    sel.innerHTML = '<option value="">历史快照：</option>' + snaps.map(function (s) {
      return '<option value="' + s.snapshot + '">' + s.snapshot + "（" + s.rows + " 行）</option>";
    }).join("");
    if (prev && snaps.some(function (s) { return s.snapshot === prev; })) sel.value = prev;
  }

  async function upload(file) {
    var fd = new FormData();
    fd.append("file", file);
    fd.append("project_id", String(currentProjectId() || 0));
    var r = await fetch("/api/tender/upload", { method: "POST", headers: authHeaders(), body: fd });
    if (!r.ok) {
      var err = await r.json().catch(function () { return { detail: r.statusText }; });
      throw new Error(err.detail || "上传失败");
    }
    return await r.json();
  }


  // A2/B2：对外联动——进入招标页 / 项目切换时刷新归属项目与快照下拉
  function enterTenderView() {
    var pid = currentProjectId();
    refreshSnapshots(pid);
  }
  window.__tenderEnter = enterTenderView;
  window.__tenderRefresh = function (pid) {
    // 切换到新项目时清空旧结果区（避免把 A 项目的结果误确认到 B 项目）
    lastResult = null;
    el("tender-result").style.display = "none";
    el("tender-busy").style.display = "none";
    refreshSnapshots(pid);
  };

  document.addEventListener("DOMContentLoaded", function () {
    var form = el("tender-form");
    var fileInput = el("tender-file-input");
    var busy = el("tender-busy");
    var resultDiv = el("tender-result");
    var confirmBtn = el("tender-confirm-btn");
    var snapSel = el("tender-snapshot-select");

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var file = fileInput.files[0];
      if (!file) { toast("请选择招标文件"); return; }
      busy.style.display = "block";
      resultDiv.style.display = "none";
      try {
        var data = await upload(file);
        await refreshSnapshots(data.project_id);
        if (window.__setProjectId && data.project_id) window.__setProjectId(data.project_id);
        showResult(data, {});
      } catch (err) {
        busy.style.display = "none";
        toast("解析失败：" + err.message);
      }
    });

    // B7：历史快照切换
    snapSel.addEventListener("change", function () {
      var pid = currentProjectId();
      if (!snapSel.value) { resultDiv.style.display = "none"; return; }
      loadSnapshot(pid, snapSel.value, true);
    });

    confirmBtn.addEventListener("click", async function () {
      if (!lastResult) return;
      confirmBtn.disabled = true;
      try {
        var r = await fetch("/api/tender/" + lastResult.project_id + "/confirm", {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ project_id: lastResult.project_id, snapshot: lastResult.snapshot }),
        });
        if (!r.ok) {
          var e0 = await r.json().catch(function () { return { detail: "确认失败" }; });
          throw new Error(e0.detail || "确认失败");
        }
        var data = await r.json();
        var file = data.files && data.files.excel;
        var msg = "已确认改单，生成 " + data.rows.length + " 行 BOM";
        if (file) msg += "，Excel 已保存到项目 #" + data.project_id;
        toast(msg);
        var dl = document.createElement("div");
        dl.style.cssText = "padding:.6rem;text-align:center;";
        if (file) {
          var b = document.createElement("button");
          b.className = "chat-dl";
          b.dataset.dl = encodeURIComponent(file);
          b.innerHTML = "⬇ 下载改单清单 " + file.split("/").pop();
          dl.appendChild(b);
        }
        var wrap = el("tender-table-wrap");
        wrap.appendChild(dl);
        wrap.querySelectorAll("[data-dl]").forEach(function (x) {
          x.addEventListener("click", function () { if (window.__download) window.__download(decodeURIComponent(x.dataset.dl)); });
        });
        await refreshSnapshots(lastResult.project_id);
      } catch (err) {
        toast(err.message);
      } finally {
        confirmBtn.disabled = false;
      }
    });

    // 初次进入：badge 已由 app.js 显示，这里补一次快照刷新
    var pid0 = currentProjectId();
    if (pid0) refreshSnapshots(pid0);
  });
})();
