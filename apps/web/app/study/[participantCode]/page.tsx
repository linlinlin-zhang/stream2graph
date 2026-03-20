import { StudyWorkbench } from "@/components/study-workbench";

export default async function StudyPage({
  params,
}: {
  params: Promise<{ participantCode: string }>;
}) {
  const { participantCode } = await params;
  return <StudyWorkbench participantCode={participantCode} />;
}
