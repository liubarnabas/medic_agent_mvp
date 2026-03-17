"""
端到端测试脚本
- 读取 data/test_cases.json（30% 测试集）
- 每条病例通过规则引擎运行
- 将引擎输出与 meta.label_clinical 标签对比（若标签含"缺铁"/"IDA" → 预期确诊/提示）
- 输出：
  - data/test_results.json    （每条病例的输入、引擎输出、标签对比）
  - 控制台摘要

运行：python scripts/run_e2e_tests.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.ida import diagnose
from src.ida.models import DiagnosisInput, PatientInput, LabInput, ClinicalInput

DATA_DIR = ROOT / "data"
TEST_CASES_PATH = DATA_DIR / "test_cases.json"
RESULTS_PATH    = DATA_DIR / "test_results.json"

# ── 标签推断（用于自动对比，无标签时跳过）─────────────────────
IDA_KEYWORDS = ["缺铁", "ida", "iron deficiency", "缺铁性贫血"]
ANEMIA_KEYWORDS = ["贫血", "anemia"]


def label_to_expected(label: str) -> str | None:
    """
    从临床诊断文本推断预期诊断等级：
    - 含 IDA 关键词 → "确诊" 或 "提示"（无法区分时返回 "ida"）
    - 含贫血但无 IDA → "贫血_非IDA"
    - 空 → None（不参与对比）
    """
    low = label.lower()
    if any(k in low for k in IDA_KEYWORDS):
        return "ida"
    if any(k in low for k in ANEMIA_KEYWORDS):
        return "anemia_other"
    if label.strip():
        return "other"
    return None


def build_input(case: dict) -> DiagnosisInput:
    """从病例字典构建 DiagnosisInput。"""
    inp = case["input"]
    p = inp["patient"]
    l = inp["lab"]

    lab = LabInput(
        Hb=l["Hb"],
        MCV=l["MCV"],
        MCH=l["MCH"],
        MCHC=l["MCHC"],
        SF=l.get("SF"),
        serum_iron=l.get("serum_iron"),
        TIBC=l.get("TIBC"),
        TS=l.get("TS"),
        CRP=l.get("CRP"),
        RDW=l.get("RDW"),
    )
    patient = PatientInput(
        sex=p["sex"],
        age=p["age"],
        pregnant=p.get("pregnant", False),
        precondition=p.get("precondition", False),
    )
    clinical = None
    if inp.get("clinical"):
        clinical = ClinicalInput(**inp["clinical"])

    return DiagnosisInput(patient=patient, lab=lab, clinical=clinical)


def evaluate(engine_level: str, expected: str | None) -> str:
    """
    对比引擎输出与预期标签，返回：pass / fail / skip（无标签）
    """
    if expected is None:
        return "skip"
    if expected == "ida":
        return "pass" if engine_level in ("确诊", "提示") else "fail"
    if expected == "anemia_other":
        return "pass" if engine_level == "阴性" else "inconclusive"
    return "skip"


def main():
    if not TEST_CASES_PATH.exists():
        print(f"错误：找不到 {TEST_CASES_PATH}，请先运行 scripts/prepare_data.py")
        sys.exit(1)

    cases = json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))
    if not cases:
        print("⚠️  测试集为空（data/test_cases.json 无数据），无法执行 E2E 测试。")
        print("    请先向 data/data.csv 填入真实病例，再运行 scripts/prepare_data.py。")
        RESULTS_PATH.write_text("[]", encoding="utf-8")
        return

    results = []
    stats = {"pass": 0, "fail": 0, "skip": 0, "inconclusive": 0, "error": 0}

    for case in cases:
        meta = case["meta"]
        label = meta.get("label_clinical") or meta.get("label_diag") or ""
        expected = label_to_expected(label)

        try:
            diag_input = build_input(case)
            output = diagnose(diag_input)
            verdict = evaluate(output.level, expected)
        except Exception as e:
            results.append({
                "meta": meta,
                "engine_output": None,
                "expected": expected,
                "verdict": "error",
                "error": str(e),
            })
            stats["error"] += 1
            continue

        stats[verdict] += 1
        results.append({
            "meta": meta,
            "engine_output": {
                "conclusion": output.conclusion,
                "level": output.level,
                "severity": output.severity,
                "stage": output.stage,
                "evidence_detail": output.evidence_detail,
                "differential_diagnosis": [d.model_dump() for d in output.differential_diagnosis],
                "supplementary_tests": output.supplementary_tests,
                "remarks": output.remarks,
            },
            "expected": expected,
            "label_raw": label,
            "verdict": verdict,
        })

    RESULTS_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total = len(results)
    print("=" * 50)
    print(f"E2E 测试结果摘要（共 {total} 例）")
    print("=" * 50)
    print(f"  ✅ PASS         : {stats['pass']}")
    print(f"  ❌ FAIL         : {stats['fail']}")
    print(f"  ⏭  SKIP（无标签）: {stats['skip']}")
    print(f"  ❓ INCONCLUSIVE : {stats['inconclusive']}")
    print(f"  💥 ERROR        : {stats['error']}")
    if stats["pass"] + stats["fail"] > 0:
        acc = stats["pass"] / (stats["pass"] + stats["fail"]) * 100
        print(f"\n  准确率（有标签）: {acc:.1f}%  （目标 ≥ 85%）")
    print(f"\n详细结果 → {RESULTS_PATH}")

    # 打印失败病例详情
    failed = [r for r in results if r["verdict"] == "fail"]
    if failed:
        print(f"\n失败病例（{len(failed)} 例）：")
        for r in failed:
            print(f"  行{r['meta']['row_idx']}: 标签='{r['label_raw']}' 引擎={r['engine_output']['level']}")


if __name__ == "__main__":
    main()
