import { EditorWorkspace } from "@/components/editor-workspace";

export default async function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return (
    <EditorWorkspace key={projectId} projectId={projectId}>
      {children}
    </EditorWorkspace>
  );
}
