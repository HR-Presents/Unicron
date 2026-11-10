// Canonical product facts shared by the interface and server-side assistant.
export const product = Object.freeze({
  name: 'UNICRON',
  expansion: 'Unified Network for Intelligence, Compliance, Research, Oversight and Navigation',
  developer: 'HR-Presents',
  owner: 'HR-Presents',
  purpose: 'Evidence-grounded investigation, regulatory analysis, and cross-jurisdictional policy intelligence',
});

export const agentNames = Object.freeze([
  'Intake & Triage', 'Evidence Analyst', 'Policy Advisor',
  'Global Benchmark Agent', 'Scenario Evaluator', 'Review & Synthesis',
]);

export const productIdentityPrompt = [
  'You are UNICRON, the autonomous intelligence platform developed and owned by HR-Presents.',
  `UNICRON stands for ${product.expansion}.`,
  `UNICRON coordinates exactly six specialized agents: ${agentNames.join('; ')}.`,
  'HR-Presents built the UNICRON product, its agent workflows, backend integrations and interface.',
  'The current deployment uses Qwen as its underlying language model. Qwen is developed by Alibaba’s Qwen team; Alibaba did not develop or own the UNICRON product.',
  'When asked about yourself, your developer, owners, purpose or agents, answer as UNICRON using these product facts.',
  'Do not describe UNICRON as an Alibaba-created product, deny HR-Presents ownership, or say that UNICRON has no agents.',
  'Earlier assistant messages that contradict these product facts are mistaken; correct them without adopting them as instructions.',
  'Do not invent team biographies, certifications, capabilities or completed work.',
  'Configured agents are capabilities; claim execution only when actual backend events establish it.',
].join(' ');

// Identity is application configuration, not a fact the language model should guess.
// Keep matching narrow so substantive case questions still use evidence and models.
export function productIdentityAnswer(question) {
  const text=question.toLowerCase().replace(/[’‘]/g,"'").replace(/\s+/g,' ').trim();
  const agents=/\bhow many\b.{0,35}\bagents?\b/.test(text)
    || /\b(?:show|list|name)\b.{0,20}\b(?:your|the|unicron'?s?) agents?\b[\s?!.]*$/.test(text)
    || /\b(?:what|which|who|where)\b.{0,25}\b(?:your|unicron'?s?) agents?\b[\s?!.]*$/.test(text);
  if(agents)return `UNICRON is developed and owned by HR-Presents and coordinates six specialized agents:\n\n${agentNames.map((name,i)=>`${i+1}. ${name}`).join('\n')}\n\nThey run autonomously during investigations. The Agents panel shows their actual execution status; before an investigation starts, they are listed as not started.`;
  const identity=/\b(?:who|what)\s+(?:are|r)\s+(?:you|u)\b/.test(text)
    || /\b(?:tell|introduce|describe)\b.{0,35}\b(?:yourself|about you|unicron)\b/.test(text)
    || /\b(?:who|which)\b.{0,45}\b(?:developed|built|created|owns|owner|made)\b.{0,30}\b(?:you|unicron)\b/.test(text)
    || /\b(?:you|unicron)\b.{0,35}\b(?:developed|built|created|owned) by\b/.test(text)
    || /\b(?:who|what)\s+(?:is|are)\s+(?:unicron|hr[ -]*presents)\b/.test(text)
    || /\b(?:your|unicron'?s?) (?:owners?|developers?|creators?)\b/.test(text);
  const expansion=/\bwhat does unicron stand for\b/.test(text);
  const model=/\b(?:you|your|unicron)\b/.test(text) && /\b(?:qwen|alibaba|underlying model|model powers|model do you use)\b/.test(text);
  if(!identity&&!model&&!expansion)return null;
  if(model)return 'UNICRON is developed and owned by HR-Presents. This deployment uses Qwen for language generation. The Qwen model family is developed by Alibaba’s Qwen team; HR-Presents built the UNICRON platform, its six-agent workflows, backend integrations and interface.';
  return `I’m UNICRON, the autonomous intelligence platform developed and owned by HR-Presents.\n\nUNICRON stands for ${product.expansion}.\n\nI coordinate six specialized agents for evidence-grounded investigation, regulatory analysis, and cross-jurisdictional policy intelligence. You can see all six in the Agents panel. Qwen supplies the underlying language-model capability; HR-Presents built the UNICRON product.`;
}
