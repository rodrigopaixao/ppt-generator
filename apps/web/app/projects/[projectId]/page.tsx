"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useEditor } from "@/components/editor-workspace";

export default function ProjectPage() {
  const { project, slides } = useEditor();
  const router = useRouter();
  useEffect(() => {
    router.replace(`/projects/${project.id}/slides/${slides[0].number}`);
  }, [project.id, slides, router]);
  return <p className="loading-state">Opening presentation…</p>;
}
