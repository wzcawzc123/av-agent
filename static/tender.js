/** 招标改单页面逻辑 */
(function () {
  "use strict";

  function getToken() {
    return window.localStorage.getItem("token") || window.__token || "";
  }
  function authHeaders() {
    return { Authorization: "Bearer " + getToken(), Accept: "application/json" };
  }

  let lastResult = null; // {project_id, snapshot, items, merged}

  async function upload(file) {
    var fd = new FormData();
    fd.append("file", file);
    fd.append("project_id", "1");
    var r = await fetch("/api/tender/upload", {
      method: "POST",
      headers: { Authorization: "Bearer " + getToken() },
      body: fd,
    });
    if (!r.ok) {
      var err = await r.json().catch(function () { return { detail: r.statusText }; });
      throw new Error(err.detail || "上传失败");
    }
    return await r.json();
  }

  function statusColor(s) {
    return (
      {
        matched: "var(--success)",
        partial: "var(--warning)",
        no_match: "var(--danger)",
        merged: "#999",
        extra: "var(--warning)",
        new: "#007aff",
      }[s] || "transparent"
    );
  }

  function renderTable(items) {
    var wrap = document.getElementById("tender-table-wrap");
    var html =
      '<table class="tender-table"><thead><tr>' +
      "<th>#</th><th>设备名称</th><th>品牌</th><th>型号</th><th>数量</th>" +
      "<th>状态</th><th>匹配型号</th><th>得分</th><th>备注</th><th>操作</th>" +
      "</tr></thead><tbody>";
    items.forEach(function (it) {
      html +=
        '<tr style="border-left:4px solid ' +
        statusColor(it.status) +
        '">' +
        "<td>" +
        it.idx +
        "</td>" +
        "<td>" +
        it.name +
        "</td>" +
        '<td><input class="edit-cell" data-field="brand" value="' +
        (it.brand || "") +
        '" /></td>' +
        '<td><input class="edit-cell" data-field="model" value="' +
        (it.model || "") +
        '" /></td>' +
        "<td>" +
        it.qty +
        "</td>" +
        '<td><span class="status-badge status-' +
        it.status +
        '">' +
        it.status +
        "</span></td>" +
        "<td>" +
        (it.matched_model || "-") +
        "</td>" +
        "<td>" +
        (it.score ? it.score.toFixed(2) : "-") +
        "</td>" +
        '<td class="remark-cell">' +
        (it.remark || "") +
        "</td>" +
        '<td><button class="save-row-btn" data-idx="' +
        it.idx +
        '" style="font-size:12px;padding:2px 8px;">保存</button></td>' +
        "</tr>";
    });
    html += "</tbody></table>";
    wrap.innerHTML = html;

    // 保存按钮监听
    document.querySelectorAll(".save-row-btn").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var idx = btn.dataset.idx;
        var tr = btn.closest("tr");
        var inputs = tr.querySelectorAll(".edit-cell");
        var body = {};
        inputs.forEach(function (inp) {
          body[inp.dataset.field] = inp.value;
        });
        var r = await fetch("/api/tender/" + lastResult.project_id + "/rows/" + idx, {
          method: "PUT",
          headers: Object.assign({ "Content-Type": "application/json" }, authHeaders()),
          body: JSON.stringify(body),
        });
        if (r.ok) {
          btn.textContent = "✓";
          setTimeout(function () { btn.textContent = "保存"; }, 1500);
        } else {
          alert("保存失败");
        }
      });
    });
  }

  async function showResult(data) {
    lastResult = data;
    document.getElementById("tender-busy").style.display = "none";
    document.getElementById("tender-result").style.display = "block";
    var matched = data.items.filter(function (i) { return i.status === "matched"; }).length;
    var partial = data.items.filter(function (i) { return i.status === "partial"; }).length;
    var noMatch = data.items.filter(function (i) { return i.status === "no_match"; }).length;
    document.getElementById("tender-summary").textContent =
      "共 " +
      data.items.length +
      " 项设备需求，其中 " +
      matched +
      " 项已匹配，" +
      partial +
      " 项部分匹配，" +
      noMatch +
      " 项未匹配" +
      (data.merged > 0 ? "，" + data.merged + " 项已合并" : "") +
      " | 快照: " +
      data.snapshot;
    renderTable(data.items);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("tender-form");
    var fileInput = document.getElementById("tender-file-input");
    var busy = document.getElementById("tender-busy");
    var resultDiv = document.getElementById("tender-result");
    var confirmBtn = document.getElementById("tender-confirm-btn");

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var file = fileInput.files[0];
      if (!file) return alert("请选择文件");
      busy.style.display = "block";
      resultDiv.style.display = "none";
      try {
        var data = await upload(file);
        await showResult(data);
      } catch (err) {
        busy.style.display = "none";
        alert("解析失败：" + err.message);
      }
    });

    confirmBtn.addEventListener("click", async function () {
      if (!lastResult) return;
      var r = await fetch("/api/tender/" + lastResult.project_id + "/confirm", {
        method: "POST",
        headers: Object.assign({ "Content-Type": "application/json" }, authHeaders()),
        body: JSON.stringify({
          project_id: lastResult.project_id,
          snapshot: lastResult.snapshot,
        }),
      });
      if (r.ok) {
        var data = await r.json();
        alert("已确认改单，生成 " + data.rows.length + " 行 BOM 数据");
      } else {
        alert("确认失败");
      }
    });
  });
})();