import { useState, useCallback, useRef, useEffect } from "react";

// ============================================================
// 参考区间配置 (WS/T 405-2012)
// ============================================================
const REF = {
  Hb_lower: { male: 120, female: 110 },
  MCV_lower: 80,
  MCH_lower: 27,
  MCHC_lower: 0.32,
};
const REF_YEAR = "WS/T 405-2012";

// ============================================================
// 诊断引擎
// ============================================================
function runDiagnosis(patient, lab, clinical) {
  const evidence = {};
  const hbRef = REF.Hb_lower[patient.sex] || 110;

  // 条款0: 贫血
  const c0 = lab.Hb != null && lab.Hb < hbRef;
  evidence[0] = `Hb=${lab.Hb ?? "—"} g/L，参考下限=${hbRef} g/L（${REF_YEAR}）`;

  // 条款1: 小细胞低色素
  const c1 =
    lab.MCV != null && lab.MCH != null && lab.MCHC != null &&
    lab.MCV < REF.MCV_lower &&
    lab.MCH < REF.MCH_lower &&
    lab.MCHC < REF.MCHC_lower;
  evidence[1] = `MCV=${lab.MCV ?? "—"} fL（<${REF.MCV_lower}），MCH=${lab.MCH ?? "—"} pg（<${REF.MCH_lower}），MCHC=${lab.MCHC ?? "—"}（<${REF.MCHC_lower}）`;

  // 条款2: 病因+体征
  const hasEtiology = clinical.etiology && clinical.etiology.length > 0;
  const hasSymptom = clinical.symptoms && clinical.symptoms.length > 0;
  const c2 = hasEtiology && hasSymptom;
  evidence[2] = `病因：${hasEtiology ? clinical.etiology.join("、") : "无"}；体征：${hasSymptom ? clinical.symptoms.join("、") : "无"}`;

  // 条款3: 血清铁 + TIBC
  const c3 = lab.serum_iron != null && lab.TIBC != null && lab.serum_iron < 8.95 && lab.TIBC > 64.44;
  evidence[3] = `血清铁=${lab.serum_iron ?? "—"} μmol/L，TIBC=${lab.TIBC ?? "—"} μmol/L`;

  // 条款4: 转铁蛋白饱和度
  const c4 = lab.TS != null && lab.TS < 0.15;
  evidence[4] = `转铁蛋白饱和度=${lab.TS != null ? (lab.TS * 100).toFixed(1) + "%" : "—"}`;

  // 条款5: 骨髓铁染色
  let c5 = null;
  if (lab.bone_marrow === "positive") { c5 = true; evidence[5] = "骨髓铁染色：外铁 -~±，铁粒幼红细胞<15%"; }
  else if (lab.bone_marrow === "negative") { c5 = false; evidence[5] = "骨髓铁染色：未达标准"; }
  else { c5 = null; evidence[5] = "骨髓铁染色：未检查，跳过"; }

  // 条款6: FEP/ZPP
  const c6 = (lab.FEP != null && lab.FEP > 0.9) || (lab.ZPP != null && lab.ZPP > 0.96);
  evidence[6] = `FEP=${lab.FEP ?? "—"} μmol/L，ZPP=${lab.ZPP ?? "—"} μmol/L`;

  // 条款7: SF
  let c7 = null;
  if (lab.SF != null) { c7 = lab.SF < 14; evidence[7] = `SF=${lab.SF} μg/L（参考阈值 <14 μg/L）`; }
  else { c7 = null; evidence[7] = "SF：未检查或未录入，跳过"; }

  // 条款8: sTfR
  let c8 = null;
  if (lab.sTfR != null) { const cutoff = 26.5; c8 = lab.sTfR > cutoff; evidence[8] = `sTfR=${lab.sTfR} nmol/L（界限值=${cutoff} nmol/L）`; }
  else { c8 = null; evidence[8] = "sTfR：未开展，跳过"; }

  // 条款9: 铁剂治疗
  let c9 = null;
  if (lab.Hb_after != null && lab.Hb != null) { c9 = (lab.Hb_after - lab.Hb) > 15; evidence[9] = `治疗后Hb=${lab.Hb_after} g/L，较基线升高 ${lab.Hb_after - lab.Hb} g/L`; }
  else { c9 = null; evidence[9] = "铁剂治疗：尚未实施，跳过"; }

  const supporting = [c2, c3, c4, c5, c6, c7, c8, c9];
  const positiveCount = supporting.filter(c => c === true).length;

  // 贫血程度
  let severity = null;
  if (c0) {
    if (lab.Hb >= 90) severity = "轻度";
    else if (lab.Hb >= 60) severity = "中度";
    else if (lab.Hb >= 30) severity = "重度";
    else severity = "极重度";
  }

  // 形态学分类
  let morphology = "—";
  if (lab.MCV != null) {
    if (lab.MCV < 80) morphology = "小细胞低色素性贫血";
    else if (lab.MCV <= 100) morphology = "正细胞正色素性贫血";
    else morphology = "大细胞性贫血";
  }

  // 分期
  let stage = null;
  if (lab.SF != null && lab.SF < 14) {
    if (c0 && lab.MCV != null && lab.MCV < 80) stage = "缺铁性贫血期（IDA）";
    else if (lab.TS != null && lab.TS < 0.15) stage = "缺铁性红细胞生成期（IDE）";
    else stage = "铁减少期（ID）";
  }

  // 鉴别诊断
  const differential = [];
  if (c1 && (lab.SF == null || lab.SF >= 14)) differential.push({ disease: "地中海贫血", suggestion: "建议血红蛋白电泳" });
  if (c1 && lab.CRP != null && lab.CRP > 5) differential.push({ disease: "慢性病贫血", suggestion: "结合CRP/ESR综合判断" });
  if (c1 && (lab.SF == null || lab.SF >= 14) && (lab.CRP == null || lab.CRP <= 5)) differential.push({ disease: "铁粒幼细胞贫血", suggestion: "建议骨髓铁染色" });

  // 主判断
  let conclusion;
  if (patient.precondition) {
    conclusion = { verdict: "不适用后续流程", level: "不适用", activeKeys: [], remarks: ["存在血容量变化等前置条件，建议去医院找专业医生判断"] };
  } else if (!c0) {
    conclusion = { verdict: "不满足贫血诊断", level: "阴性", activeKeys: [0], remarks: ["提示排除高海拔居住、慢性呼吸道疾病等干扰因素后重新人工评估"] };
  } else if (c1 && positiveCount >= 2) {
    const keys = [0, 1, ...supporting.map((c, i) => c === true ? i + 2 : null).filter(k => k != null)];
    conclusion = { verdict: "可诊断为缺铁性贫血（IDA）", level: "确诊", activeKeys: keys, remarks: [] };
  } else if (c7 === true) {
    conclusion = { verdict: "高度提示缺铁性贫血，尚不满足确诊标准", level: "提示", activeKeys: [7], remarks: ["SF < 14 μg/L 敏感度/特异度较高，请结合其他检查进一步确认"] };
  } else {
    conclusion = { verdict: "证据不足，不能诊断缺铁性贫血", level: "阴性", activeKeys: Object.keys(evidence).map(Number), remarks: ["建议补充检查 / 随访 / 试验性铁剂治疗后评估"] };
  }

  return { conclusion, evidence, positiveCount, severity, morphology, stage, differential, supporting };
}

// ============================================================
// 枚举数据
// ============================================================
const ETIOLOGY_OPTIONS = [
  { key: "absorption_disorder", label: "吸收不良" },
  { key: "vegetarian", label: "素食/偏食" },
  { key: "adolescent", label: "青春期发育" },
  { key: "pregnancy", label: "妊娠期" },
  { key: "multiparity", label: "多次妊娠" },
  { key: "chronic_bleeding", label: "慢性出血" },
  { key: "other", label: "其他病因" },
];
const SYMPTOM_OPTIONS = [
  { key: "fatigue", label: "疲劳/乏力" },
  { key: "pallor", label: "皮肤苍白" },
  { key: "tachycardia", label: "心悸/心动过速" },
  { key: "dizziness", label: "头晕目眩" },
  { key: "dyspnea", label: "呼吸困难" },
  { key: "koilonychia", label: "反甲/勺状指" },
  { key: "pica", label: "异食癖" },
  { key: "melena", label: "黑便" },
  { key: "menorrhagia", label: "经血过多" },
  { key: "angular_cheilitis", label: "口角炎/舌炎" },
  { key: "brittle_hair", label: "头发干枯" },
  { key: "dry_skin", label: "皮肤干燥" },
];

// ============================================================
// 组件
// ============================================================
const LEVEL_STYLES = {
  "确诊": { bg: "#dc2626", text: "#fff" },
  "提示": { bg: "#ea580c", text: "#fff" },
  "阴性": { bg: "#6b7280", text: "#fff" },
  "不适用": { bg: "#9ca3af", text: "#fff" },
};

function NumberInput({ label, unit, value, onChange, required, hint }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", fontFamily: "'Noto Sans SC', sans-serif" }}>
        {label} {required && <span style={{ color: "#dc2626" }}>*</span>}
      </label>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <input
          type="number"
          step="any"
          value={value ?? ""}
          onChange={e => onChange(e.target.value === "" ? null : parseFloat(e.target.value))}
          placeholder="—"
          style={{
            width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6,
            fontSize: 14, fontFamily: "'JetBrains Mono', 'Fira Code', monospace", background: "#fafafa",
            outline: "none", transition: "border-color 0.2s",
          }}
          onFocus={e => e.target.style.borderColor = "#2563eb"}
          onBlur={e => e.target.style.borderColor = "#d1d5db"}
        />
        {unit && <span style={{ fontSize: 11, color: "#6b7280", whiteSpace: "nowrap", minWidth: 50 }}>{unit}</span>}
      </div>
      {hint && <span style={{ fontSize: 10, color: "#9ca3af" }}>{hint}</span>}
    </div>
  );
}

function ChipSelector({ options, selected, onToggle }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {options.map(opt => {
        const active = selected.includes(opt.key);
        return (
          <button key={opt.key} onClick={() => onToggle(opt.key)}
            style={{
              padding: "5px 12px", borderRadius: 20, border: active ? "1.5px solid #2563eb" : "1px solid #d1d5db",
              background: active ? "#eff6ff" : "#fff", color: active ? "#1d4ed8" : "#4b5563",
              fontSize: 12, cursor: "pointer", fontFamily: "'Noto Sans SC', sans-serif", fontWeight: active ? 600 : 400,
              transition: "all 0.15s",
            }}
          >{opt.label}</button>
        );
      })}
    </div>
  );
}

function ClauseRow({ idx, label, result, evidenceText }) {
  const isTrue = result === true;
  const isFalse = result === false;
  const isNull = result === null;
  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 10, padding: "8px 12px", borderRadius: 8,
      background: isTrue ? "#f0fdf4" : isNull ? "#f9fafb" : "#fff",
      border: isTrue ? "1px solid #bbf7d0" : "1px solid #f3f4f6",
    }}>
      <div style={{
        minWidth: 22, height: 22, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 11, fontWeight: 700, marginTop: 1,
        background: isTrue ? "#16a34a" : isNull ? "#d1d5db" : "#fca5a5",
        color: isTrue ? "#fff" : isNull ? "#6b7280" : "#991b1b",
      }}>{isTrue ? "✓" : isNull ? "—" : "✗"}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#1f2937", fontFamily: "'Noto Sans SC', sans-serif" }}>条款 {idx}：{label}</div>
        <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2, fontFamily: "'JetBrains Mono', monospace", lineHeight: 1.5 }}>{evidenceText}</div>
      </div>
    </div>
  );
}

// ============================================================
// Main App
// ============================================================
export default function App() {
  const [page, setPage] = useState("input"); // input | result
  const [patient, setPatient] = useState({ sex: "female", precondition: false });
  const [lab, setLab] = useState({});
  const [etiology, setEtiology] = useState([]);
  const [symptoms, setSymptoms] = useState([]);
  const [result, setResult] = useState(null);
  const [llmText, setLlmText] = useState("");
  const [llmLoading, setLlmLoading] = useState(false);
  const topRef = useRef(null);

  const updateLab = useCallback((key, val) => setLab(prev => ({ ...prev, [key]: val })), []);
  const toggleList = (list, setList, key) => {
    setList(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]);
  };

  const handleDiagnose = () => {
    if (lab.Hb == null) { alert("请至少输入血红蛋白（Hb）值"); return; }
    const clinical = {
      etiology: etiology.map(k => ETIOLOGY_OPTIONS.find(o => o.key === k)?.label).filter(Boolean),
      symptoms: symptoms.map(k => SYMPTOM_OPTIONS.find(o => o.key === k)?.label).filter(Boolean),
    };
    const res = runDiagnosis(patient, lab, clinical);
    setResult(res);
    setPage("result");
    setLlmText("");
    // Auto-generate LLM description
    generateLLM(res);
  };

  const generateLLM = async (res) => {
    setLlmLoading(true);
    const activeEvidence = res.conclusion.activeKeys.map(k => `  · 条款${k}：${res.evidence[k]}`).join("\n");
    const remarks = res.conclusion.remarks.length > 0 ? res.conclusion.remarks.join("；") : "无";
    const prompt = `你是一名经验丰富的血液科医生助手。请根据以下结构化诊断结论，用简洁、专业的语言撰写一段诊断依据描述，供主治医生参考。
要求：
1. 先给出诊断结论（一句话）。
2. 逐条列出支持该结论的阳性指标及其数值，并注明参考标准。
3. 如有未检查项目或需排除的干扰因素，在末尾单独说明。
4. 语言简洁，避免重复，不超过 300 字。

诊断结论：${res.conclusion.verdict}（${res.conclusion.level}）
贫血程度：${res.severity || "—"}
形态学分类：${res.morphology}
分期：${res.stage || "—"}
阳性/关键证据：
${activeEvidence}
备注：${remarks}`;
    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }
      const data = await response.json();
      setLlmText(data.text || "生成失败");
    } catch (e) {
      setLlmText("LLM 生成失败：" + e.message);
    }
    setLlmLoading(false);
  };

  useEffect(() => {
    if (page === "result" && topRef.current) topRef.current.scrollIntoView({ behavior: "smooth" });
  }, [page]);

  const clauseLabels = ["贫血判定", "小细胞低色素", "病因+体征", "血清铁+TIBC", "转铁蛋白饱和度", "骨髓铁染色", "FEP/ZPP", "血清铁蛋白(SF)", "sTfR", "铁剂治疗反应"];

  // ============================================================
  // RENDER
  // ============================================================
  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(160deg, #f0f4f8 0%, #e8ecf1 50%, #f5f0eb 100%)", fontFamily: "'Noto Sans SC', 'Helvetica Neue', sans-serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />

      {/* HEADER */}
      <div style={{
        background: "linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #334155 100%)",
        padding: "28px 24px 22px", borderBottom: "3px solid #3b82f6",
      }}>
        <div style={{ maxWidth: 800, margin: "0 auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{
              width: 42, height: 42, borderRadius: 10, background: "linear-gradient(135deg, #3b82f6, #1d4ed8)",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, color: "#fff",
              boxShadow: "0 4px 12px rgba(59,130,246,0.4)",
            }}>🔬</div>
            <div>
              <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#f1f5f9", letterSpacing: 1 }}>
                临床辅助诊断智能体
              </h1>
              <p style={{ margin: 0, fontSize: 11, color: "#94a3b8", fontWeight: 400, letterSpacing: 0.5 }}>
                缺铁性贫血（IDA）诊断通路 · MVP v1.0
              </p>
            </div>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 800, margin: "0 auto", padding: "16px 12px 60px" }} ref={topRef}>

        {/* ========== INPUT PAGE ========== */}
        {page === "input" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

            {/* 患者基本信息 */}
            <section style={{ background: "#fff", borderRadius: 12, padding: "16px 14px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", margin: "0 0 14px", borderLeft: "3px solid #3b82f6", paddingLeft: 10 }}>
                患者基本信息
              </h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>性别 <span style={{ color: "#dc2626" }}>*</span></label>
                  <div style={{ display: "flex", gap: 8 }}>
                    {[["male", "男"], ["female", "女"]].map(([v, l]) => (
                      <button key={v} onClick={() => setPatient(p => ({ ...p, sex: v }))}
                        style={{
                          flex: 1, padding: "8px 0", borderRadius: 6, cursor: "pointer", fontSize: 13, fontWeight: 600,
                          border: patient.sex === v ? "2px solid #2563eb" : "1px solid #d1d5db",
                          background: patient.sex === v ? "#eff6ff" : "#fff",
                          color: patient.sex === v ? "#1d4ed8" : "#6b7280",
                        }}
                      >{l}</button>
                    ))}
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>前置条件</label>
                  <button onClick={() => setPatient(p => ({ ...p, precondition: !p.precondition }))}
                    style={{
                      padding: "8px 12px", borderRadius: 6, cursor: "pointer", fontSize: 12,
                      border: patient.precondition ? "2px solid #dc2626" : "1px solid #d1d5db",
                      background: patient.precondition ? "#fef2f2" : "#fff",
                      color: patient.precondition ? "#dc2626" : "#6b7280", fontWeight: 500,
                      textAlign: "left",
                    }}
                  >{patient.precondition ? "⚠ 存在前置条件（妊娠/肝硬化/急性大出血等）" : "无（点击标记）"}</button>
                </div>
              </div>
            </section>

            {/* 血常规 */}
            <section style={{ background: "#fff", borderRadius: 12, padding: "16px 14px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", margin: "0 0 14px", borderLeft: "3px solid #10b981", paddingLeft: 10 }}>
                血常规
              </h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 14 }}>
                <NumberInput label="Hb 血红蛋白" unit="g/L" value={lab.Hb} onChange={v => updateLab("Hb", v)} required hint={`参考下限：${patient.sex === "male" ? 120 : 110}`} />
                <NumberInput label="MCV 平均红细胞体积" unit="fL" value={lab.MCV} onChange={v => updateLab("MCV", v)} required hint="参考下限：80" />
                <NumberInput label="MCH 平均Hb含量" unit="pg" value={lab.MCH} onChange={v => updateLab("MCH", v)} required hint="参考下限：27" />
                <NumberInput label="MCHC 平均Hb浓度" unit="(0~1)" value={lab.MCHC} onChange={v => updateLab("MCHC", v)} required hint="参考下限：0.32" />
                <NumberInput label="RDW 红细胞分布宽度" unit="%" value={lab.RDW} onChange={v => updateLab("RDW", v)} />
              </div>
            </section>

            {/* 铁代谢 */}
            <section style={{ background: "#fff", borderRadius: 12, padding: "16px 14px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", margin: "0 0 14px", borderLeft: "3px solid #f59e0b", paddingLeft: 10 }}>
                铁代谢指标
              </h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 14 }}>
                <NumberInput label="SF 血清铁蛋白" unit="μg/L" value={lab.SF} onChange={v => updateLab("SF", v)} required hint="<14 高度提示IDA" />
                <NumberInput label="血清铁" unit="μmol/L" value={lab.serum_iron} onChange={v => updateLab("serum_iron", v)} required hint="<8.95 为阳性" />
                <NumberInput label="TIBC 总铁结合力" unit="μmol/L" value={lab.TIBC} onChange={v => updateLab("TIBC", v)} required hint=">64.44 为阳性" />
                <NumberInput label="TS 转铁蛋白饱和度" unit="(0~1)" value={lab.TS} onChange={v => updateLab("TS", v)} required hint="<0.15 为阳性" />
                <NumberInput label="CRP" unit="mg/L" value={lab.CRP} onChange={v => updateLab("CRP", v)} hint="排除炎症干扰" />
              </div>
            </section>

            {/* 扩展检验 */}
            <section style={{ background: "#fff", borderRadius: 12, padding: "16px 14px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", margin: "0 0 14px", borderLeft: "3px solid #8b5cf6", paddingLeft: 10 }}>
                扩展检验（可选）
              </h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 14 }}>
                <NumberInput label="FEP 红细胞游离原卟啉" unit="μmol/L" value={lab.FEP} onChange={v => updateLab("FEP", v)} hint=">0.9 为阳性" />
                <NumberInput label="ZPP 锌原卟啉" unit="μmol/L" value={lab.ZPP} onChange={v => updateLab("ZPP", v)} hint=">0.96 为阳性" />
                <NumberInput label="sTfR 可溶性转铁蛋白受体" unit="nmol/L" value={lab.sTfR} onChange={v => updateLab("sTfR", v)} hint=">26.5 为阳性" />
                <NumberInput label="铁剂治疗后 Hb" unit="g/L" value={lab.Hb_after} onChange={v => updateLab("Hb_after", v)} hint="治疗2~4周后" />
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>骨髓铁染色</label>
                  <select value={lab.bone_marrow || ""} onChange={e => updateLab("bone_marrow", e.target.value || null)}
                    style={{ padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 13, background: "#fafafa" }}>
                    <option value="">未检查</option>
                    <option value="positive">外铁阴性~弱阳，铁粒幼红&lt;15%</option>
                    <option value="negative">未达标准</option>
                  </select>
                </div>
              </div>
            </section>

            {/* 临床信息 */}
            <section style={{ background: "#fff", borderRadius: 12, padding: "16px 14px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", margin: "0 0 14px", borderLeft: "3px solid #ec4899", paddingLeft: 10 }}>
                临床信息（可选）
              </h2>
              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 8 }}>缺铁病因</label>
                <ChipSelector options={ETIOLOGY_OPTIONS} selected={etiology} onToggle={k => toggleList(etiology, setEtiology, k)} />
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 8 }}>临床体征</label>
                <ChipSelector options={SYMPTOM_OPTIONS} selected={symptoms} onToggle={k => toggleList(symptoms, setSymptoms, k)} />
              </div>
            </section>

            {/* 提交按钮 */}
            <button onClick={handleDiagnose}
              style={{
                width: "100%", padding: "16px 0", borderRadius: 10, border: "none", cursor: "pointer",
                background: "linear-gradient(135deg, #1d4ed8, #2563eb)", color: "#fff",
                fontSize: 16, fontWeight: 700, letterSpacing: 2, fontFamily: "'Noto Sans SC', sans-serif",
                boxShadow: "0 4px 16px rgba(37,99,235,0.3)", transition: "transform 0.1s, box-shadow 0.1s",
              }}
              onMouseDown={e => { e.target.style.transform = "scale(0.98)"; }}
              onMouseUp={e => { e.target.style.transform = "scale(1)"; }}
            >
              🔍 开始诊断分析
            </button>

            <div style={{ fontSize: 11, color: "#9ca3af", textAlign: "center", lineHeight: 1.6 }}>
              ⚠️ 本系统为辅助诊断工具，所有输出结论为辅助诊断建议，最终诊断由临床医生负责。
            </div>
          </div>
        )}

        {/* ========== RESULT PAGE ========== */}
        {page === "result" && result && (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>

            <button onClick={() => setPage("input")}
              style={{
                alignSelf: "flex-start", padding: "8px 18px", borderRadius: 8, border: "1px solid #d1d5db",
                background: "#fff", cursor: "pointer", fontSize: 13, color: "#374151", fontWeight: 500,
              }}
            >← 返回修改</button>

            {/* 诊断结论卡片 */}
            <section style={{
              background: "#fff", borderRadius: 14, overflow: "hidden",
              boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
            }}>
              <div style={{
                background: LEVEL_STYLES[result.conclusion.level]?.bg || "#6b7280",
                padding: "16px 20px", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
              }}>
                <div style={{ fontSize: 32 }}>
                  {result.conclusion.level === "确诊" ? "✅" : result.conclusion.level === "提示" ? "⚠️" : result.conclusion.level === "不适用" ? "🚫" : "❌"}
                </div>
                <div style={{ flex: "1 1 200px", minWidth: 0 }}>
                  <div style={{ fontSize: 10, color: "rgba(255,255,255,0.7)", fontWeight: 600, textTransform: "uppercase", letterSpacing: 2, marginBottom: 4 }}>诊断结论</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: "#fff", lineHeight: 1.3, wordBreak: "break-word" }}>{result.conclusion.verdict}</div>
                </div>
                <div style={{
                  padding: "6px 16px", borderRadius: 20,
                  background: "rgba(255,255,255,0.2)", color: "#fff", fontSize: 13, fontWeight: 700,
                }}>{result.conclusion.level}</div>
              </div>

              <div style={{ padding: "14px 20px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 12 }}>
                {result.severity && (
                  <div><div style={{ fontSize: 10, color: "#9ca3af", fontWeight: 600 }}>贫血程度</div><div style={{ fontSize: 15, fontWeight: 700, color: "#1f2937" }}>{result.severity}</div></div>
                )}
                <div><div style={{ fontSize: 10, color: "#9ca3af", fontWeight: 600 }}>形态学分类</div><div style={{ fontSize: 15, fontWeight: 700, color: "#1f2937" }}>{result.morphology}</div></div>
                {result.stage && (
                  <div><div style={{ fontSize: 10, color: "#9ca3af", fontWeight: 600 }}>分期</div><div style={{ fontSize: 15, fontWeight: 700, color: "#1f2937" }}>{result.stage}</div></div>
                )}
                <div><div style={{ fontSize: 10, color: "#9ca3af", fontWeight: 600 }}>阳性条款数</div><div style={{ fontSize: 15, fontWeight: 700, color: "#1f2937" }}>{result.positiveCount} / 8</div></div>
              </div>
            </section>

            {/* 逐条证据 */}
            <section style={{ background: "#fff", borderRadius: 12, padding: "16px 14px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", margin: "0 0 14px", borderLeft: "3px solid #3b82f6", paddingLeft: 10 }}>
                诊断证据明细（条款 0~9）
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map(i => {
                  let r;
                  if (i === 0) r = lab.Hb != null && lab.Hb < (REF.Hb_lower[patient.sex] || 110);
                  else if (i === 1) r = lab.MCV != null && lab.MCH != null && lab.MCHC != null && lab.MCV < 80 && lab.MCH < 27 && lab.MCHC < 0.32;
                  else { const s = result.supporting[i - 2]; r = s; }
                  return <ClauseRow key={i} idx={i} label={clauseLabels[i]} result={r} evidenceText={result.evidence[i]} />;
                })}
              </div>
            </section>

            {/* 鉴别诊断 */}
            {result.differential.length > 0 && (
              <section style={{ background: "#fff", borderRadius: 12, padding: "16px 14px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
                <h2 style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", margin: "0 0 14px", borderLeft: "3px solid #f59e0b", paddingLeft: 10 }}>鉴别诊断提示</h2>
                {result.differential.map((d, i) => (
                  <div key={i} style={{ padding: "8px 12px", background: "#fffbeb", borderRadius: 8, marginBottom: 6, border: "1px solid #fde68a" }}>
                    <span style={{ fontWeight: 600, fontSize: 13, color: "#92400e" }}>{d.disease}</span>
                    <span style={{ fontSize: 12, color: "#78716c", marginLeft: 8 }}>→ {d.suggestion}</span>
                  </div>
                ))}
              </section>
            )}

            {/* 备注 */}
            {result.conclusion.remarks.length > 0 && (
              <section style={{ background: "#fff", borderRadius: 12, padding: "16px 14px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
                <h2 style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", margin: "0 0 14px", borderLeft: "3px solid #6b7280", paddingLeft: 10 }}>备注</h2>
                {result.conclusion.remarks.map((r, i) => (
                  <div key={i} style={{ fontSize: 13, color: "#4b5563", lineHeight: 1.7 }}>• {r}</div>
                ))}
              </section>
            )}

            {/* LLM 生成描述 */}
            <section style={{ background: "#fff", borderRadius: 12, padding: "16px 14px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", margin: "0 0 14px", borderLeft: "3px solid #8b5cf6", paddingLeft: 10 }}>
                LLM 诊断描述
              </h2>
              {llmLoading ? (
                <div style={{ padding: 20, textAlign: "center" }}>
                  <div style={{ display: "inline-block", width: 24, height: 24, border: "3px solid #e5e7eb", borderTopColor: "#8b5cf6", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                  <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                  <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>正在生成自然语言诊断描述…</div>
                </div>
              ) : (
                <div style={{
                  fontSize: 13, color: "#374151", lineHeight: 1.8, whiteSpace: "pre-wrap",
                  background: "#faf5ff", padding: 16, borderRadius: 8, border: "1px solid #e9d5ff",
                  fontFamily: "'Noto Sans SC', sans-serif",
                }}>
                  {llmText || "等待生成…"}
                </div>
              )}
            </section>

            {/* 参考指南 */}
            <section style={{ background: "#f8fafc", borderRadius: 12, padding: "16px 22px", border: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: 11, color: "#64748b", lineHeight: 1.7 }}>
                <strong>参考指南：</strong>{REF_YEAR} · 中华医学会血液学分会《IDA诊治指南》<br />
                ⚠️ 本报告为辅助诊断建议，最终诊断由临床医生负责。
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
