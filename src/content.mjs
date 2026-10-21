/**
 * Content for the seven responsive templates. Fidelity mode reads all slides from
 * data/catalog.json and data/slides/NNN.json extracted from the complete PPTX. Wording and
 * indices come from the versioned reference, not inference.
 *
 * @module content
 */
import fs from 'node:fs';
import path from 'node:path';
import { root } from './components.mjs';

export const source = JSON.parse(fs.readFileSync(path.join(root, 'data/source.json'))).slides;
/**
 * Return source slide text in XML order; number is the original slide number.
 */
const texts = number => source[number].texts.map(t => t.text);

export const contents = {
  5: {
    template: 'executiveSummary', title: texts(5)[0], kicker: 'EXECUTIVE SUMMARY',
    paragraphs: source[5].texts[1].paragraphs,
  },
  10: { template: 'agenda', title: texts(10)[0], rows: source[10].tables[0] },
  21: {
    template: 'timeline', title: texts(21)[0], kicker: 'HIGH-LEVEL OVERVIEW OF SEPTEMBER BOARD',
    disclaimer: 'Preliminary – to be refined with key stakeholders',
    start: '2026-06-15', end: '2026-09-22',
    weeks: ['15', '22', '29', '06', '13', '20', '27', '03', '10', '17', '24', '31', '07', '14', '21'],
    months: [{ label: 'Jun', weeks: 3 }, { label: 'Jul', weeks: 4 },
      { label: 'Aug', weeks: 5 }, { label: 'Sep', weeks: 3 }],
    milestones: [
      { date: '2026-07-20', label: '7/20\nTech Offsite', lane: 0, kind: 'meeting' },
      { date: '2026-08-04', end: '2026-08-07', label: '8/4–8/7\nGH & TCoB Chair Review', lane: 2, kind: 'review' },
      { date: '2026-08-12', label: '8/12\nCEO Sub.', lane: 0, kind: 'board' },
      { date: '2026-08-14', label: '8/14\nQMR', lane: 3, kind: 'meeting' },
      { date: '2026-08-18', label: '8/18\nBoD Sub.', lane: 0, kind: 'board' },
      { date: '2026-08-18', label: '8/18\nQBR', lane: 3, kind: 'meeting' },
      { date: '2026-08-24', label: '8/24\nTCoB & OpCo Posting', lane: 1, kind: 'board' },
      { date: '2026-08-26', label: '8/26\nOpCo Review', lane: 2, kind: 'review' },
      { date: '2026-09-02', end: '2026-09-04', label: '9/2–9/4\nGH Review', lane: 0, kind: 'review' },
      { date: '2026-09-08', label: '9/8\nOpCo Sub.', lane: 1, kind: 'board' },
      { date: '2026-09-10', label: '9/10\nOpCo Review', lane: 2, kind: 'review' },
      { date: '2026-09-14', label: '9/14\nBoD Sub.', lane: 0, kind: 'board' },
      { date: '2026-09-16', label: '9/16\nAug MMR', lane: 3, kind: 'meeting' },
      { date: '2026-09-22', label: '9/22\nBoD', lane: 0, kind: 'board' },
    ],
    availability: [
      { date: '2026-06-19', label: '6/19\nProj. Falcon: Business Cases' },
      { date: '2026-06-25', label: '6/25\nSIP Overview & 1st Envelope Preview' },
      { date: '2026-07-17', label: '7/17\nJune MMR' },
      { date: '2026-07-22', label: '7/22\nSIP Envelope Prioritization' },
      { date: '2026-08-26', end: '2026-08-27', label: '8/26–27\nFull Bank & Final SIP Envelope' },
    ],
    // Source labels contain #4 twice. Preserve rather than silently changing the reference.
    committees: [33, 37, 34, 38, 35].map((index, i) => ({ text: texts(21)[index],
      date: ['2026-07-06', '2026-07-15', '2026-07-27', '2026-08-25', '2026-09-04'][i] })),
    footnote: texts(21).find(t => t.startsWith('1. Corporate')),
  },
  38: {
    template: 'competitiveComparison', title: texts(38)[2], tags: ['MEXICO', 'INDUSTRY OVERVIEW'],
    rows: source[38].tables[0], banks: ['SBM', 'BBVA', 'BANORTE', 'Santander', 'Banamex', 'HSBC'],
    logos: ['assets/logo.svg', ...source[38].pictures.map(p => p.path)],
    footnote: texts(38)[1],
  },
  50: {
    template: 'strategicPillars', title: texts(50)[0], tags: ['MEXICO', 'ALL BANK'],
    mission: texts(50)[2], outcome: texts(50)[3],
    pillars: [
      { title: 'Grow in priority markets', icon: 'assets/source-50-geometry-4.svg' },
      { title: 'Build primary relationships with clients', icon: 'assets/source-50-geometry-2.svg' },
      { title: 'Make it easier to do business with us', icon: 'assets/source-50-geometry-3.svg' },
      { title: 'Win as one team', icon: 'assets/source-50-geometry-1.svg' },
    ],
  },
  64: {
    template: 'clientJourney', title: texts(64)[0], kicker: 'INBOUND CLIENT JOURNEY MAP',
    footnote: texts(64)[2], discussion: texts(64).at(-1),
    journeys: [
      { title: 'SIMPLE\nSALES & SERVICE', description: 'Low degree of info & short task duration',
        steps: [
          { title: 'RESEARCH', description: texts(64)[6], icon: 'assets/source-64-geometry-0.svg' },
          { title: 'SELF-SERVE', description: texts(64)[12], icon: 'assets/source-64-geometry-1.svg' },
          { title: 'SUPPORT REQUIRED', description: texts(64)[10], icon: 'assets/image358.svg' },
          { title: 'CHANNEL INTERSECTION', description: texts(64)[25], accent: true, icon: 'assets/source-64-geometry-8.svg' },
          { title: 'VIRTUAL / BRANCH', description: texts(64)[8], icon: 'assets/image361.svg' },
        ] },
      { title: 'COMPLEX\nSALES & SERVICE', description: 'High degree of info & long task duration',
        steps: [
          { title: 'RESEARCH', description: texts(64)[14], icon: 'assets/source-64-geometry-0.svg' },
          { title: 'CHANNEL INTERSECTION', description: texts(64)[27], accent: true, icon: 'assets/source-64-geometry-9.svg' },
          { title: 'VIRTUAL / BRANCH', description: texts(64)[16], icon: 'assets/image360.svg' },
        ] },
    ],
  },
  68: {
    template: 'executionDashboard', title: 'Q2 F26 Summary | Dashboard (1 of 2)',
    kicker: 'SCOTIATECH STRATEGY EXECUTION UPDATE – Q2 F26', hidden: true,
    pillars: [
      { title: 'A. RUN TECHNOLOGY AS A BUSINESS', health: [0, 2, 1, 1, 0],
        chart: source[68].charts[0],
        accomplishments: source[68].texts[13].paragraphs,
        concerns: source[68].texts[5].paragraphs },
      { title: 'B. DELIVER WITH EXCELLENCE', health: [0, 0, 5, 0, 0],
        chart: source[68].charts[1],
        accomplishments: source[68].texts[27].paragraphs,
        concerns: source[68].texts[19].paragraphs },
      { title: 'C. ENGINEER FOR SIMPLICITY', health: [0, 1, 6, 1, 0],
        chart: source[68].charts[2],
        accomplishments: source[68].texts[41].paragraphs,
        concerns: source[68].texts[33].paragraphs },
    ],
  },
};

// Preserve wording while removing positioning whitespace from the source's manual text layout.
for (const journey of contents[64].journeys)
  for (const step of journey.steps) step.description = step.description.replace(/\s+/g, ' ').trim();
