"""招标改单数据结构。"""
from dataclasses import dataclass, field


@dataclass
class TenderItem:
    """解析器输出：招标文件中的一行设备需求。"""

    idx: int
    name: str
    brand: str = ""
    model: str = ""
    qty: int = 1
    params: list[str] = field(default_factory=list)
    raw: str = ""


@dataclass
class DimValue:
    """一个参数维度提取值。"""

    value: float
    unit: str
    raw: str


@dataclass
class TenderMatchRow:
    """匹配结果行：对应一个招标需求项或派生项（新增/补充）。"""

    source_idx: int
    name: str
    brand: str = ""
    model: str = ""
    qty: int = 1
    params: list[str] = field(default_factory=list)
    status: str = "no_match"  # matched|partial|no_match|merged|extra|new
    matched_product_id: int = 0
    matched_model: str = ""
    score: float = 0.0
    remark: str = ""
    merged_into: str = ""
    preference: str = "higher"

    def to_dict(self) -> dict:
        return {
            "source_idx": self.source_idx,
            "name": self.name,
            "brand": self.brand,
            "model": self.model,
            "qty": self.qty,
            "params": list(self.params),
            "status": self.status,
            "matched_product_id": self.matched_product_id,
            "matched_model": self.matched_model,
            "score": round(self.score, 4),
            "remark": self.remark,
            "merged_into": self.merged_into,
            "preference": self.preference,
        }


# 状态常量
STATUS_MATCHED = "matched"
STATUS_PARTIAL = "partial"
STATUS_NO_MATCH = "no_match"  # 库内无候选 → 生成新增行
STATUS_MERGED = "merged"  # 功能被其他产品集成 → 标红
STATUS_EXTRA = "extra"  # 冗余 → 标红
STATUS_NEW = "new"  # 新增/补充项
