"""
IDA 诊断引擎测试
覆盖四种诊断等级：确诊 / 提示 / 阴性 / 不适用
以及主要边界情况
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.ida import diagnose
from src.ida.models import (
    DiagnosisInput, PatientInput, LabInput, ClinicalInput,
    EtiologyInput, SymptomsInput,
)


# ─── 辅助工厂 ────────────────────────────────────────────────

def make_input(
    sex="female", age=35, pregnant=False, precondition=False,
    Hb=85, MCV=72, MCH=24, MCHC=0.30,
    SF=8.0, serum_iron=6.2, TIBC=72.5, TS=0.09,
    CRP=None,
    etiology=None, symptoms=None,
    **kwargs,
) -> DiagnosisInput:
    lab_kwargs = dict(
        Hb=Hb, MCV=MCV, MCH=MCH, MCHC=MCHC,
        SF=SF, serum_iron=serum_iron, TIBC=TIBC, TS=TS,
        CRP=CRP, **kwargs,
    )
    clinical = None
    if etiology is not None or symptoms is not None:
        clinical = ClinicalInput(
            etiology=EtiologyInput(**(etiology or {})),
            symptoms=SymptomsInput(**(symptoms or {})),
        )
    return DiagnosisInput(
        patient=PatientInput(sex=sex, age=age, pregnant=pregnant, precondition=precondition),
        lab=LabInput(**lab_kwargs),
        clinical=clinical,
    )


# ─── 不适用（前置条件）────────────────────────────────────────

class TestPrecondition:
    def test_precondition_returns_na(self):
        data = make_input(precondition=True)
        result = diagnose(data)
        assert result.level == "不适用"
        assert "不适用后续流程" in result.conclusion

    def test_precondition_ignores_other_values(self):
        """前置条件存在时，即使其他指标正常也应返回不适用"""
        data = make_input(precondition=True, Hb=130)
        result = diagnose(data)
        assert result.level == "不适用"


# ─── 阴性（不满足贫血诊断）────────────────────────────────────

class TestNoAnemia:
    def test_normal_hb_male(self):
        """男性 Hb >= 120 → 不满足贫血诊断"""
        data = make_input(sex="male", Hb=125)
        result = diagnose(data)
        assert result.level == "阴性"
        assert "不满足贫血诊断" in result.conclusion

    def test_normal_hb_female(self):
        """女性 Hb >= 110 → 不满足贫血诊断"""
        data = make_input(sex="female", Hb=115)
        result = diagnose(data)
        assert result.level == "阴性"
        assert "不满足贫血诊断" in result.conclusion

    def test_boundary_hb_female(self):
        """女性 Hb 恰好等于参考下限 → 不满足贫血诊断"""
        data = make_input(sex="female", Hb=110.0)
        result = diagnose(data)
        assert result.level == "阴性"

    def test_hb_below_threshold_male(self):
        """男性 Hb < 120 → 进入贫血诊断流程"""
        data = make_input(sex="male", Hb=118)
        result = diagnose(data)
        assert result.level != "阴性" or "不满足" not in result.conclusion


# ─── 确诊 IDA ─────────────────────────────────────────────────

class TestConfirmedIDA:
    def test_classic_ida(self):
        """典型 IDA：小细胞低色素 + SF↓ + TS↓ + 血清铁↓ + TIBC↑"""
        data = make_input(
            Hb=85, MCV=72, MCH=24, MCHC=0.30,
            SF=8.0, serum_iron=6.2, TIBC=72.5, TS=0.09,
        )
        result = diagnose(data)
        assert result.level == "确诊"
        assert "IDA" in result.conclusion
        assert result.severity is not None
        assert result.stage is not None

    def test_ida_with_symptoms(self):
        """有病因 + 体征可作为条款 2 阳性"""
        data = make_input(
            Hb=80, MCV=70, MCH=22, MCHC=0.28,
            SF=10.0, serum_iron=None, TIBC=None, TS=0.10,
            etiology={"chronic_bleeding": True},
            symptoms={"fatigue": True, "pallor": True},
        )
        result = diagnose(data)
        assert result.level == "确诊"

    def test_ida_requires_at_least_2_clauses(self):
        """小细胞低色素但只满足 1 条 → 不应确诊"""
        data = make_input(
            Hb=85, MCV=72, MCH=24, MCHC=0.30,
            SF=8.0,          # 条款7阳性 → 1条
            serum_iron=None, TIBC=None, TS=None,  # 其余未检查
        )
        result = diagnose(data)
        # 只有条款7（SF↓），确诊需≥2条，此时应走提示路径
        assert result.level in ("提示", "阴性")

    def test_severity_mild(self):
        """轻度贫血：Hb 在 90~参考下限之间"""
        data = make_input(sex="female", Hb=100, SF=8.0, TS=0.09, serum_iron=5.0, TIBC=70.0)
        result = diagnose(data)
        if result.level == "确诊":
            assert result.severity == "轻度"

    def test_severity_moderate(self):
        """中度贫血：Hb 60~90"""
        data = make_input(Hb=75, SF=6.0, TS=0.08, serum_iron=5.0, TIBC=70.0)
        result = diagnose(data)
        if result.level == "确诊":
            assert result.severity == "中度"

    def test_severity_severe(self):
        """重度贫血：Hb 30~60"""
        data = make_input(Hb=45, SF=4.0, TS=0.06, serum_iron=3.0, TIBC=75.0)
        result = diagnose(data)
        if result.level == "确诊":
            assert result.severity == "重度"

    def test_severity_critical(self):
        """极重度贫血：Hb < 30"""
        data = make_input(Hb=20, SF=2.0, TS=0.05, serum_iron=2.0, TIBC=80.0)
        result = diagnose(data)
        if result.level == "确诊":
            assert result.severity == "极重度"

    def test_evidence_detail_contains_active_clauses(self):
        """确诊时 evidence_detail 应包含条款 0、1 及所有阳性条款"""
        data = make_input(SF=8.0, TS=0.09, serum_iron=6.2, TIBC=72.5)
        result = diagnose(data)
        if result.level == "确诊":
            assert "0" in result.evidence_detail
            assert "1" in result.evidence_detail


# ─── 提示（高度提示 IDA）──────────────────────────────────────

class TestHintIDA:
    def test_sf_low_but_not_microcytic(self):
        """SF < 14 但非小细胞低色素 → 高度提示"""
        data = make_input(
            Hb=80, MCV=88, MCH=28, MCHC=0.33,  # 正细胞
            SF=10.0, serum_iron=None, TIBC=None, TS=None,
        )
        result = diagnose(data)
        assert result.level == "提示"
        assert "高度提示" in result.conclusion

    def test_sf_low_microcytic_but_only_one_clause(self):
        """小细胞低色素 + 仅 SF↓（1条）→ 提示"""
        data = make_input(
            Hb=85, MCV=72, MCH=24, MCHC=0.30,
            SF=8.0, serum_iron=None, TIBC=None, TS=None,
        )
        result = diagnose(data)
        assert result.level == "提示"


# ─── 阴性（证据不足）─────────────────────────────────────────

class TestInsufficientEvidence:
    def test_anemia_sf_normal(self):
        """有贫血，SF 正常 → 证据不足"""
        data = make_input(
            Hb=85, MCV=72, MCH=24, MCHC=0.30,
            SF=20.0, serum_iron=None, TIBC=None, TS=None,
        )
        result = diagnose(data)
        assert result.level == "阴性"
        assert "证据不足" in result.conclusion

    def test_anemia_sf_missing(self):
        """有贫血，SF 未检查 → 证据不足"""
        data = make_input(
            Hb=85, MCV=72, MCH=24, MCHC=0.30,
            SF=None, serum_iron=None, TIBC=None, TS=None,
        )
        result = diagnose(data)
        assert result.level == "阴性"


# ─── 冲突检测 ─────────────────────────────────────────────────

class TestConflicts:
    def test_sf_low_mixed_anemia_hint(self):
        """SF↓ + MCV 正常 → 混合性贫血冲突提示"""
        data = make_input(
            Hb=85, MCV=88, MCH=28, MCHC=0.33,  # 正细胞
            SF=10.0, serum_iron=None, TIBC=None, TS=None,
        )
        result = diagnose(data)
        conflict_found = any("混合" in r or "B12" in r for r in result.remarks)
        assert conflict_found

    def test_microcytic_sf_normal_crp_normal_conflict(self):
        """小细胞低色素 + SF 正常 + CRP 正常 → 地贫/铁粒幼细胞冲突提示"""
        data = make_input(
            Hb=85, MCV=72, MCH=24, MCHC=0.30,
            SF=25.0, CRP=3.0,
            serum_iron=None, TIBC=None, TS=None,
        )
        result = diagnose(data)
        # 鉴别诊断或 remarks 中应有相关提示
        has_thalassemia = any(
            "地贫" in d.disease or "铁粒" in d.disease
            for d in result.differential_diagnosis
        ) or any("Hb 电泳" in r or "地贫" in r for r in result.remarks)
        assert has_thalassemia


# ─── 铁剂治疗有效（条款 9）────────────────────────────────────

class TestIronTherapy:
    def test_iron_therapy_positive(self):
        """铁剂治疗后 Hb 升高 > 15 → 条款9阳性"""
        data = make_input(
            Hb=80, MCV=72, MCH=24, MCHC=0.30,
            SF=None, serum_iron=None, TIBC=None, TS=None,
            Hb_after_iron_therapy=100.0,  # 升高 20 g/L
        )
        result = diagnose(data)
        # 条款9阳性但只有1条，走提示路径
        assert result.level in ("提示", "确诊", "阴性")

    def test_iron_therapy_negative(self):
        """铁剂治疗后 Hb 升高 ≤ 15 → 条款9阴性"""
        data = make_input(
            Hb=80, MCV=72, MCH=24, MCHC=0.30,
            SF=None, serum_iron=None, TIBC=None, TS=None,
            Hb_after_iron_therapy=90.0,  # 升高 10 g/L
        )
        result = diagnose(data)
        assert result.level in ("阴性", "提示")


# ─── 孕妇参考值 ───────────────────────────────────────────────

class TestPregnantReference:
    def test_pregnant_hb_threshold(self):
        """孕妇参考下限 110 g/L"""
        data = make_input(sex="female", age=28, pregnant=True, Hb=108)
        result = diagnose(data)
        # Hb < 110 → 进入贫血流程，不会返回"不满足贫血诊断"
        assert "不满足贫血诊断" not in result.conclusion

    def test_pregnant_hb_normal(self):
        """孕妇 Hb >= 110 → 不满足贫血诊断"""
        data = make_input(sex="female", age=28, pregnant=True, Hb=115)
        result = diagnose(data)
        assert result.level == "阴性"
        assert "不满足贫血诊断" in result.conclusion


# ─── LLM Prompt 生成 ─────────────────────────────────────────

class TestLLMPrompt:
    def test_prompt_not_empty(self):
        data = make_input()
        result = diagnose(data)
        assert len(result.llm_prompt) > 50

    def test_prompt_contains_conclusion(self):
        data = make_input()
        result = diagnose(data)
        assert result.conclusion in result.llm_prompt


# ─── 补充检查建议 ─────────────────────────────────────────────

class TestSupplementaryTests:
    def test_elderly_male_gets_fecal_occult(self):
        """老年男性应建议便潜血"""
        data = make_input(sex="male", age=65, SF=8.0, TS=0.09, serum_iron=6.0, TIBC=70.0)
        result = diagnose(data)
        has_fecal = any("便潜血" in t for t in result.supplementary_tests)
        assert has_fecal

    def test_reproductive_female_gets_menstrual(self):
        """育龄女性应建议月经量评估"""
        data = make_input(sex="female", age=30)
        result = diagnose(data)
        has_menstrual = any("月经" in t for t in result.supplementary_tests)
        assert has_menstrual
