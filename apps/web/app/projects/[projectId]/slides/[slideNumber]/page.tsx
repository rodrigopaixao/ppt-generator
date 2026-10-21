import { SlideEditor } from "@/components/slide-editor";

export default async function SlidePage({
  params,
}: {
  params: Promise<{ slideNumber: string }>;
}) {
  const { slideNumber } = await params;
  return <SlideEditor key={slideNumber} slideNumber={Number(slideNumber)} />;
}
