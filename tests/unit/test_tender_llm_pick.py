"""LLM 精修层测试（monkeypatch 模拟 LLM 返回 + 降级路径）。"""

from app.engines.tender import llm_pick
from app.engines.tender.model import TenderMatchRow


def _row(idx, name, status="partial", matched_model="X-1", remark=""):
    return TenderMatchRow(
        source_idx=idx,
        name=name,
        params=[name],
        status=status,
        matched_model=matched_model,
        remark=remark,
    )


class TestRefineRows:
    def test_disabled_noop(self):
        rows = [_row(1, "功放")]
        out = llm_pick.refine_rows(rows, llm_enabled=False)
        assert out[0].status == "partial"

    def test_keep_confirms(self, monkeypatch):
        monkeypatch.setattr(
            llm_pick, "_call_llm", lambda p: {"partials": [{"idx": 1, "decision": "keep", "note": "够用"}]}
        )
        rows = [_row(1, "功放")]
        llm_pick.refine_rows(rows)
        assert rows[0].status == "matched"
        assert "确认可用" in rows[0].remark

    def test_new(self, monkeypatch):
        monkeypatch.setattr(
            llm_pick, "_call_llm", lambda p: {"partials": [{"idx": 1, "decision": "new"}]}
        )
        rows = [_row(1, "功放")]
        llm_pick.refine_rows(rows)
        assert rows[0].status == "new"

    def test_replace_keeps_partial(self, monkeypatch):
        monkeypatch.setattr(
            llm_pick, "_call_llm", lambda p: {"partials": [{"idx": 1, "decision": "replace", "model": "GX-2"}]}
        )
        rows = [_row(1, "功放")]
        llm_pick.refine_rows(rows)
        assert rows[0].status == "partial"
        assert "GX-2" in rows[0].remark

    def test_llm_failure_degrades(self, monkeypatch):
        def boom(p):
            raise RuntimeError("no key")

        monkeypatch.setattr(llm_pick, "_call_llm", boom)
        rows = [_row(1, "功放")]
        llm_pick.refine_rows(rows)
        assert rows[0].status == "partial"

    def test_no_partial_skips_call(self, monkeypatch):
        called = {"n": 0}

        def spy(p):
            called["n"] += 1
            return {}

        monkeypatch.setattr(llm_pick, "_call_llm", spy)
        rows = [_row(1, "功放", status="matched")]
        llm_pick.refine_rows(rows)
        assert called["n"] == 0


class TestFlagExtras:
    def test_flag(self, monkeypatch):
        monkeypatch.setattr(llm_pick, "_call_llm", lambda p: {"extras": [2]})
        rows = [_row(1, "主音箱"), _row(2, "备用音箱")]
        llm_pick.flag_extras(rows)
        assert rows[0].status == "partial"
        assert rows[1].status == "extra"

    def test_skip_merged_new(self, monkeypatch):
        monkeypatch.setattr(llm_pick, "_call_llm", lambda p: {"extras": [1, 2]})
        rows = [
            _row(1, "调音台", status="merged"),
            _row(2, "功放", status="new"),
        ]
        llm_pick.flag_extras(rows)
        assert rows[0].status == "merged"  # merged 不被覆盖
        assert rows[1].status == "new"  # new 不被覆盖

    def test_single_row_noop(self, monkeypatch):
        called = {"n": 0}

        def spy(p):
            called["n"] += 1
            return {"extras": [1]}

        monkeypatch.setattr(llm_pick, "_call_llm", spy)
        rows = [_row(1, "功放")]
        llm_pick.flag_extras(rows)
        assert called["n"] == 0

    def test_failure_degrades(self, monkeypatch):
        def boom(p):
            raise RuntimeError("no key")

        monkeypatch.setattr(llm_pick, "_call_llm", boom)
        rows = [_row(1, "主音箱"), _row(2, "备用音箱")]
        llm_pick.flag_extras(rows)
        assert rows[1].status == "partial"