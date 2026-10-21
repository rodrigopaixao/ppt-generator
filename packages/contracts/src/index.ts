export type BuildMode = "fidelity" | "responsive";
export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}
export interface TextStyle {
  fontFamily: string;
  fontSize: number;
  lineHeight?: number;
  color: string;
  bold: boolean;
  italic: boolean;
  align: "left" | "center" | "right" | "justify";
  vertical: "top" | "middle" | "bottom";
  margins: [number, number, number, number];
  underline?: boolean;
  strike?: boolean;
  baseline?: number;
}
export interface TextParagraph {
  runs: { text: string; style: TextStyle }[];
  style: TextStyle;
  bullet?: string;
  marginLeft?: number;
  indent?: number;
  spaceAfter?: number;
}
export interface TextTarget {
  kind: "shape" | "tableCell" | "chartText";
  ownerId: string;
  nativeId: string;
  layer?: "slide" | "layout" | "master";
  row?: number;
  column?: number;
  chartBox?: Box;
}
export interface TextElement {
  id: string;
  name: string;
  text: string;
  originalText: string;
  box: Box;
  rotation: number;
  role: "title" | "paragraph";
  editable: boolean;
  style: TextStyle;
  target?: TextTarget;
  paragraphs?: TextParagraph[];
  transform?: [number, number, number, number];
}
export interface SlideSummary {
  number: number;
  title: string;
  hidden: boolean;
  titleElementId?: string;
}
export interface SlideScene extends SlideSummary {
  width: number;
  height: number;
  elements: TextElement[];
  layoutError?: string;
  schemaVersion?: number;
  charts?: { id: string; box: Box }[];
  chartTextError?: string;
}
export interface EditOperation {
  slideNumber: number;
  elementId: string;
  before: string;
  after: string;
}
export interface Project {
  id: string;
  name: string;
  mode: BuildMode;
  revision: number;
  createdAt: string;
  updatedAt: string;
  overrides: Record<string, string>;
  history: EditOperation[];
  cursor: number;
}
export type ProjectSummary = Pick<
  Project,
  "id" | "name" | "mode" | "revision" | "updatedAt"
>;
export interface ProjectDocument {
  project: Project;
  slides: SlideSummary[];
}
export interface ExportJob {
  id: string;
  projectId: string;
  revision: number;
  status: "queued" | "running" | "complete" | "failed";
  error?: string;
}
