// Builds the IFRS Agent presentation deck.
// Run: node build_deck.js   (produces presentation.pptx)
const pptxgen = require("pptxgenjs");

// ===== RESULTS (filled from the evaluation runs) =====
const R = {
  agentRecall: "0.74", agentSim: "0.31", agentRouge: "0.37", agentBleu: "0.16",
  baseRecall: "0.67", baseSim: "0.26", baseRouge: "0.32", baseBleu: "0.16",
  agentJudgeEq: "79%", agentJudgeConf: "0.97",
  refusal: "3 / 3",
};

// ===== palette: Midnight Executive (navy + ice blue + teal accent) =====
const NAVY = "1E2761", INK = "16203F", ICE = "CADCFC", TEAL = "00A896",
      WHITE = "FFFFFF", GREY = "5A6275", LIGHT = "F4F7FB";
const HFONT = "Georgia", BFONT = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
pres.author = "Ben Hassine Dhia Eddine, A-Madushani, Davide Papini";
pres.title = "IFRS Agent";
const W = 13.3, H = 7.5;

function darkTitle(slide, kicker, title, sub) {
  slide.background = { color: NAVY };
  if (kicker) slide.addText(kicker.toUpperCase(), { x: 0.9, y: 1.7, w: 11.5, h: 0.4, fontFace: BFONT, fontSize: 14, color: TEAL, charSpacing: 4, bold: true });
  slide.addText(title, { x: 0.9, y: 2.1, w: 11.5, h: 1.6, fontFace: HFONT, fontSize: 46, color: WHITE, bold: true });
  if (sub) slide.addText(sub, { x: 0.9, y: 3.8, w: 11.5, h: 1.2, fontFace: BFONT, fontSize: 18, color: ICE });
}
function header(slide, title) {
  slide.background = { color: WHITE };
  slide.addText(title, { x: 0.7, y: 0.45, w: 12, h: 0.8, fontFace: HFONT, fontSize: 30, color: NAVY, bold: true });
}
function card(slide, x, y, w, h, fill) {
  slide.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill || LIGHT }, line: { color: ICE, width: 1 },
    shadow: { type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.10 } });
}
function statCard(slide, x, y, w, big, label, color) {
  card(slide, x, y, w, 1.7, WHITE);
  slide.addText(big, { x, y: y + 0.18, w, h: 0.9, align: "center", fontFace: HFONT, fontSize: 40, bold: true, color: color || NAVY });
  slide.addText(label, { x: x + 0.15, y: y + 1.05, w: w - 0.3, h: 0.55, align: "center", fontFace: BFONT, fontSize: 12.5, color: GREY });
}

// 1 — TITLE
let s = pres.addSlide();
s.background = { color: NAVY };
s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.35, h: H, fill: { color: TEAL } });
s.addText("AI AGENT WITH TOOL USE", { x: 0.9, y: 1.6, w: 11, h: 0.4, fontFace: BFONT, fontSize: 15, color: TEAL, charSpacing: 5, bold: true });
s.addText("IFRS Agent", { x: 0.9, y: 2.0, w: 11.5, h: 1.3, fontFace: HFONT, fontSize: 60, color: WHITE, bold: true });
s.addText("A retrieval-augmented agent for international accounting standards — that cites the rule and computes the figure.",
  { x: 0.9, y: 3.4, w: 10.5, h: 1.0, fontFace: BFONT, fontSize: 20, color: ICE });
s.addText([
  { text: "Ben Hassine Dhia Eddine", options: { breakLine: true } },
  { text: "A-Madushani", options: { breakLine: true } },
  { text: "Davide Papini" },
], { x: 0.9, y: 5.2, w: 6, h: 1.2, fontFace: BFONT, fontSize: 15, color: WHITE });
s.addText("github.com/dhiatnit/ifrs-agent", { x: 7.2, y: 6.5, w: 5.2, h: 0.4, align: "right", fontFace: BFONT, fontSize: 13, color: TEAL });

// 2 — PROBLEM
s = pres.addSlide(); header(s, "The problem");
const probs = [
  ["Long, technical texts", "IFRS/IAS standards run to hundreds of pages; finding the paragraph that governs a question is slow even for professionals."],
  ["Rules AND numbers", "Many questions need both the correct treatment and an exact figure (depreciation, impairment, leases)."],
  ["Generic chatbots fail", "They invent paragraph numbers and miscalculate — unacceptable in accounting."],
];
probs.forEach((p, i) => {
  const y = 1.5 + i * 1.75;
  card(s, 0.7, y, 11.9, 1.55, LIGHT);
  s.addShape(pres.shapes.OVAL, { x: 1.0, y: y + 0.42, w: 0.7, h: 0.7, fill: { color: NAVY } });
  s.addText(String(i + 1), { x: 1.0, y: y + 0.42, w: 0.7, h: 0.7, align: "center", valign: "middle", fontFace: HFONT, fontSize: 22, bold: true, color: WHITE });
  s.addText(p[0], { x: 2.0, y: y + 0.2, w: 10.2, h: 0.5, fontFace: HFONT, fontSize: 19, bold: true, color: NAVY });
  s.addText(p[1], { x: 2.0, y: y + 0.72, w: 10.2, h: 0.7, fontFace: BFONT, fontSize: 14.5, color: GREY });
});
s.addText("Goal: answer WITH citations, compute EXACTLY, and REFUSE what is out of scope.",
  { x: 0.7, y: 6.85, w: 11.9, h: 0.4, fontFace: BFONT, italic: true, fontSize: 15, color: TEAL });

// 3 — WHY AN AGENT
s = pres.addSlide(); header(s, "Why an agent, not just RAG");
card(s, 0.7, 1.5, 5.7, 4.9, LIGHT);
s.addText("Plain RAG", { x: 0.7, y: 1.7, w: 5.7, h: 0.5, align: "center", fontFace: HFONT, fontSize: 20, bold: true, color: GREY });
s.addText([
  { text: "Always: retrieve → answer", options: { bullet: true, breakLine: true } },
  { text: "No arithmetic guarantee", options: { bullet: true, breakLine: true } },
  { text: "Cannot decide to refuse", options: { bullet: true } },
], { x: 1.1, y: 2.5, w: 5.0, h: 3.5, fontFace: BFONT, fontSize: 16, color: INK, paraSpaceAfter: 12 });
card(s, 6.9, 1.5, 5.7, 4.9, NAVY);
s.addText("Our agent — it decides", { x: 6.9, y: 1.7, w: 5.7, h: 0.5, align: "center", fontFace: HFONT, fontSize: 20, bold: true, color: WHITE });
s.addText([
  { text: "search_standards — semantic search over the 5 standards", options: { bullet: true, breakLine: true } },
  { text: "calculator — exact arithmetic (LLMs are unreliable at math)", options: { bullet: true, breakLine: true } },
  { text: "Per question: search, compute, chain both, or refuse", options: { bullet: true, breakLine: true } },
  { text: "= a genuine \"agent with tool use\"", options: { bullet: false } },
], { x: 7.3, y: 2.5, w: 5.0, h: 3.5, fontFace: BFONT, fontSize: 16, color: ICE, paraSpaceAfter: 12 });

// 4 — ARCHITECTURE
s = pres.addSlide(); header(s, "Architecture");
function box(x, y, w, h, label, fill, txtcolor, fs) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: NAVY, width: 1 }, rectRadius: 0.08 });
  s.addText(label, { x, y, w, h, align: "center", valign: "middle", fontFace: BFONT, fontSize: fs || 14, bold: true, color: txtcolor || WHITE });
}
box(5.4, 1.45, 2.5, 0.8, "User question", ICE, NAVY);
box(5.0, 2.6, 3.3, 0.9, "LangChain Agent (Gemini)\ndecides", NAVY, WHITE);
s.addShape(pres.shapes.LINE, { x: 6.65, y: 2.25, w: 0, h: 0.35, line: { color: NAVY, width: 2 } });
box(2.3, 4.0, 3.6, 1.0, "search_standards\nFAISS over 5 IFRS standards", TEAL, WHITE, 13);
box(7.4, 4.0, 3.6, 1.0, "calculator\nexact figures", TEAL, WHITE, 13);
s.addShape(pres.shapes.LINE, { x: 5.8, y: 3.5, w: -1.4, h: 0.5, line: { color: NAVY, width: 2 } });
s.addShape(pres.shapes.LINE, { x: 7.5, y: 3.5, w: 1.4, h: 0.5, line: { color: NAVY, width: 2 } });
box(4.4, 5.6, 4.5, 1.0, "Answer + standard & paragraph citations", NAVY, WHITE, 14);
s.addShape(pres.shapes.LINE, { x: 4.1, y: 5.0, w: 2.55, h: 0.6, line: { color: NAVY, width: 2 } });
s.addShape(pres.shapes.LINE, { x: 9.2, y: 5.0, w: -2.55, h: 0.6, line: { color: NAVY, width: 2 } });
s.addText("167 chunks · embeddings: gemini-embedding-001 · agent: gemini-2.5-flash-lite · vector store: FAISS",
  { x: 0.7, y: 6.9, w: 11.9, h: 0.4, align: "center", fontFace: BFONT, italic: true, fontSize: 12.5, color: GREY });

// 5 — DATA
s = pres.addSlide(); header(s, "The data");
card(s, 0.7, 1.5, 6.0, 4.9, LIGHT);
s.addText("EU-endorsed, free, machine-readable", { x: 1.0, y: 1.75, w: 5.4, h: 0.5, fontFace: HFONT, fontSize: 18, bold: true, color: NAVY });
s.addText([
  { text: "Source: Regulation (EU) 2023/1803 via EUR-Lex (12 MB, all 40 standards)", options: { bullet: true, breakLine: true } },
  { text: "Why not ifrs.org: those texts are copyrighted; the EU versions are reusable with attribution", options: { bullet: true, breakLine: true } },
  { text: "Extracted from the 12 MB EU text, cleaned by the team (data QA), then automatically split into 167 section-aligned chunks", options: { bullet: true } },
], { x: 1.0, y: 2.4, w: 5.4, h: 3.7, fontFace: BFONT, fontSize: 14.5, color: INK, paraSpaceAfter: 12 });
const stds = ["IAS 2 — Inventories", "IAS 16 — Property, Plant & Equipment", "IAS 36 — Impairment of Assets", "IFRS 15 — Revenue from Contracts", "IFRS 16 — Leases"];
stds.forEach((t, i) => {
  const y = 1.5 + i * 0.98;
  card(s, 7.0, y, 5.6, 0.8, WHITE);
  s.addShape(pres.shapes.RECTANGLE, { x: 7.0, y, w: 0.12, h: 0.8, fill: { color: TEAL } });
  s.addText(t, { x: 7.35, y, w: 5.1, h: 0.8, valign: "middle", fontFace: BFONT, fontSize: 15, bold: true, color: NAVY });
});

// 6 — FOUNDATION / what we built and fixed
s = pres.addSlide(); header(s, "Built on the course template — and hardened");
const found = [
  ["Kept", "LangChain + Gemini + FAISS core and the evaluation scripts (rageval, LLM-as-judge) from Prof. Belli's studentsbot."],
  ["Changed", "Swapped university web pages for IFRS/IAS standards; replaced the system prompt with an IFRS one."],
  ["Added", "Two tools and the agent decision layer — the part that makes it an agent."],
  ["Fixed", "A silent chunking bug (5 giant chunks → 167) and three retired/changed Gemini models. LLM apps age fast."],
];
found.forEach((f, i) => {
  const x = 0.7 + (i % 2) * 6.05, y = 1.55 + Math.floor(i / 2) * 2.45;
  card(s, x, y, 5.8, 2.2, LIGHT);
  s.addText(f[0], { x: x + 0.25, y: y + 0.2, w: 5.3, h: 0.5, fontFace: HFONT, fontSize: 19, bold: true, color: TEAL });
  s.addText(f[1], { x: x + 0.25, y: y + 0.8, w: 5.3, h: 1.3, fontFace: BFONT, fontSize: 14.5, color: INK });
});

// 6b — DESIGN DECISIONS / ALTERNATIVES REJECTED
s = pres.addSlide(); header(s, "Design decisions & alternatives rejected");
s.addTable([
  [ {text:"Decision",options:{bold:true,color:WHITE,fill:{color:NAVY}}},
    {text:"We chose",options:{bold:true,color:WHITE,fill:{color:NAVY}}},
    {text:"Rejected — why",options:{bold:true,color:WHITE,fill:{color:NAVY}}} ],
  ["Architecture", "Agent + 2 tools", "Plain RAG — can't compute reliably; misses the tool-use track"],
  ["Doing math", "calculator tool", "LLM mental math — miscalculates, not auditable"],
  ["Data source", "EUR-Lex (Reg. 2023/1803)", "ifrs.org texts — copyrighted, not redistributable"],
  ["LLM", "gemini-2.5-flash-lite", "gemini-3.x — breaks course LangChain; bigger — no free quota"],
  ["Chunking", "by section heading", "fixed-size chunks — split paragraphs, blur citations"],
  ["Vector store", "FAISS (local)", "hosted vector DB — extra setup, no benefit at this scale"],
], { x: 0.7, y: 1.5, w: 11.9, h: 4.6, fontFace: BFONT, fontSize: 13, color: INK,
     border: { pt: 0.5, color: ICE }, valign: "middle", colW: [2.4, 3.3, 6.2],
     rowH: [0.5, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7] });
s.addText("Same reasoning underlies the evaluation: agent vs plain-RAG baseline on the SAME model isolates the effect of tool use.",
  { x: 0.7, y: 6.4, w: 11.9, h: 0.5, fontFace: BFONT, italic: true, fontSize: 12.5, color: TEAL });

// 7 — METHODOLOGY
s = pres.addSlide(); header(s, "Evaluation methodology");
card(s, 0.7, 1.5, 11.9, 2.2, LIGHT);
s.addText("Test set — 30 questions with known answers", { x: 1.0, y: 1.7, w: 11.3, h: 0.5, fontFace: HFONT, fontSize: 18, bold: true, color: NAVY });
s.addText([
  { text: "15 definitions / scope   ·   12 calculations (exact numbers)   ·   3 out-of-scope traps (must refuse)", options: {} },
], { x: 1.0, y: 2.3, w: 11.3, h: 1.2, fontFace: BFONT, fontSize: 15.5, color: INK });
card(s, 0.7, 3.95, 5.8, 2.6, WHITE);
s.addText("Quantitative", { x: 1.0, y: 4.15, w: 5.2, h: 0.5, fontFace: HFONT, fontSize: 17, bold: true, color: TEAL });
s.addText([
  { text: "rageval.py: similarity, ROUGE, BLEU, keyword P/R/F1", options: { bullet: true, breakLine: true } },
  { text: "Agent vs plain-RAG baseline, same model & questions", options: { bullet: true } },
], { x: 1.0, y: 4.7, w: 5.2, h: 1.7, fontFace: BFONT, fontSize: 14, color: INK, paraSpaceAfter: 8 });
card(s, 6.8, 3.95, 5.8, 2.6, WHITE);
s.addText("Qualitative", { x: 7.1, y: 4.15, w: 5.2, h: 0.5, fontFace: HFONT, fontSize: 17, bold: true, color: TEAL });
s.addText([
  { text: "LLM-as-judge: semantic equivalence + confidence", options: { bullet: true, breakLine: true } },
  { text: "Refusal accuracy + error analysis by category", options: { bullet: true } },
], { x: 7.1, y: 4.7, w: 5.2, h: 1.7, fontFace: BFONT, fontSize: 14, color: INK, paraSpaceAfter: 8 });

// 8 — RESULTS (stat cards)
s = pres.addSlide(); header(s, "Results");
statCard(s, 0.7, 1.6, 2.85, "30 / 30", "questions answered", NAVY);
statCard(s, 3.75, 1.6, 2.85, R.refusal, "out-of-scope refusals", TEAL);
statCard(s, 6.8, 1.6, 2.85, R.agentJudgeEq, "LLM-judge: equivalent", NAVY);
statCard(s, 9.85, 1.6, 2.75, R.agentJudgeConf, "judge confidence", TEAL);
card(s, 0.7, 3.7, 11.9, 2.9, WHITE);
s.addText("Agent vs baseline — automatic metrics (same model, 30 questions)", { x: 1.0, y: 3.85, w: 11.3, h: 0.5, fontFace: HFONT, fontSize: 16, bold: true, color: NAVY });
s.addTable([
  [ {text:"Metric",options:{bold:true,color:WHITE,fill:{color:NAVY}}},
    {text:"Agent",options:{bold:true,color:WHITE,fill:{color:NAVY}}},
    {text:"Baseline (plain RAG)",options:{bold:true,color:WHITE,fill:{color:NAVY}}} ],
  ["Keyword recall", R.agentRecall, R.baseRecall],
  ["Keyword F1", "0.44", "0.40"],
  ["Text similarity", R.agentSim, R.baseSim],
  ["ROUGE-1 F1", R.agentRouge, R.baseRouge],
  ["BLEU", R.agentBleu, R.baseBleu],
], { x: 1.0, y: 4.4, w: 11.3, h: 2.0, fontFace: BFONT, fontSize: 13.5, color: INK, border: { pt: 0.5, color: ICE }, align: "center", valign: "middle", colW: [4.3, 3.5, 3.5] });

// 9 — READING THE METRICS (the honest insight)
s = pres.addSlide(); header(s, "Reading the metrics honestly");
card(s, 0.7, 1.6, 11.9, 2.0, LIGHT);
s.addText("Why overlap scores look low even when answers are correct", { x: 1.0, y: 1.8, w: 11.3, h: 0.5, fontFace: HFONT, fontSize: 17, bold: true, color: NAVY });
s.addText("Reference answers are one line; the agent gives a full, cited explanation. ROUGE/BLEU reward brevity and exact wording, so extra correct words lower the score.",
  { x: 1.0, y: 2.35, w: 11.3, h: 1.1, fontFace: BFONT, fontSize: 15, color: INK });
card(s, 0.7, 3.8, 5.8, 2.7, WHITE);
s.addText("The telling number", { x: 1.0, y: 4.0, w: 5.2, h: 0.4, fontFace: BFONT, fontSize: 13, color: GREY });
s.addText("Keyword recall " + R.agentRecall, { x: 1.0, y: 4.4, w: 5.2, h: 0.9, fontFace: HFONT, fontSize: 30, bold: true, color: TEAL });
s.addText("The agent's answers contain the right content — they are just fuller than the references.",
  { x: 1.0, y: 5.4, w: 5.2, h: 1.0, fontFace: BFONT, fontSize: 13.5, color: INK });
card(s, 6.8, 3.8, 5.8, 2.7, WHITE);
s.addText("So we also judge meaning", { x: 7.1, y: 4.0, w: 5.2, h: 0.4, fontFace: BFONT, fontSize: 13, color: GREY });
s.addText("LLM-as-judge", { x: 7.1, y: 4.4, w: 5.2, h: 0.7, fontFace: HFONT, fontSize: 26, bold: true, color: NAVY });
s.addText("Scores semantic equivalence rather than word overlap — the fairer measure for cited, explanatory answers.",
  { x: 7.1, y: 5.2, w: 5.2, h: 1.2, fontFace: BFONT, fontSize: 13.5, color: INK });

// 10 — DEMO (the signature interaction)
s = pres.addSlide(); header(s, "Demo: tool chaining in one answer");
s.addText("\"A machine costs €120,000, residual €20,000, useful life 8 years. Annual depreciation, and which standard?\"",
  { x: 0.7, y: 1.45, w: 11.9, h: 0.8, fontFace: BFONT, italic: true, fontSize: 16, color: NAVY });
const steps = [
  ["1 · search_standards", "Finds IAS 16 — depreciable amount allocated over useful life (¶50, 53, 62)."],
  ["2 · calculator", "(120000 − 20000) / 8 = 12500 — exact, not estimated."],
  ["3 · answer", "“Annual depreciation is €12,500 (IAS 16, ¶50/53/62).” with the formula shown."],
];
steps.forEach((st, i) => {
  const y = 2.45 + i * 1.4;
  card(s, 0.7, y, 11.9, 1.2, i === 2 ? NAVY : LIGHT);
  s.addText(st[0], { x: 1.0, y: y + 0.15, w: 3.3, h: 0.9, valign: "middle", fontFace: HFONT, fontSize: 17, bold: true, color: i === 2 ? TEAL : NAVY });
  s.addText(st[1], { x: 4.3, y: y + 0.15, w: 8.0, h: 0.9, valign: "middle", fontFace: BFONT, fontSize: 14.5, color: i === 2 ? ICE : INK });
});

// 11 — CHALLENGES
s = pres.addSlide(); header(s, "Challenges we solved");
const ch = [
  ["Models age fast", "Three Gemini models we depended on were retired or zero-quota within months — pinned versions and documented the stack."],
  ["Silent chunking bug", "The template indexed 5 giant blobs; fixed to 167 section-aligned chunks with citations."],
  ["Free-tier quotas", "Agents are multi-call per question; daily caps were the real limit. Made every run paced, retrying and resumable."],
  ["Retry storms", "Naive auto-retries deepen rate-limiting — backing off deliberately beats retrying aggressively."],
];
ch.forEach((c, i) => {
  const x = 0.7 + (i % 2) * 6.05, y = 1.55 + Math.floor(i / 2) * 2.45;
  card(s, x, y, 5.8, 2.2, LIGHT);
  s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.12, h: 2.2, fill: { color: TEAL } });
  s.addText(c[0], { x: x + 0.3, y: y + 0.2, w: 5.3, h: 0.5, fontFace: HFONT, fontSize: 18, bold: true, color: NAVY });
  s.addText(c[1], { x: x + 0.3, y: y + 0.8, w: 5.3, h: 1.3, fontFace: BFONT, fontSize: 14, color: INK });
});

// 12 — CONCLUSION
s = pres.addSlide();
darkTitle(s, "Conclusion", "An agent that cites, computes, and knows its limits.",
  "30/30 questions answered, " + R.refusal + " refusals, agent-vs-baseline evaluation with automatic and LLM-judge scoring. Built on the course stack, extended into a real tool-using agent.");
s.addText("Future work: more standards · retrieval metrics (Hit@k / MRR) · concise-answer prompting · hybrid / GraphRAG.",
  { x: 0.9, y: 5.6, w: 11.5, h: 0.8, fontFace: BFONT, italic: true, fontSize: 15, color: TEAL });
s.addText("github.com/dhiatnit/ifrs-agent", { x: 0.9, y: 6.6, w: 11.5, h: 0.4, fontFace: BFONT, fontSize: 13, color: ICE });

pres.writeFile({ fileName: "presentation.pptx" }).then(f => console.log("wrote", f));
