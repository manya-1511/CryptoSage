import { Suspense } from "react";
import Navbar from "@/components/Navbar";
import FloatingParticles from "@/components/FloatingParticles";
import ReportChat from "@/components/chat/ReportChat";
import { Loader2Icon } from "lucide-react";

function AssistantContent({ searchParams }: { searchParams: { firmwareId?: string } }) {
  const initialFirmwareId = searchParams.firmwareId ? Number(searchParams.firmwareId) : undefined;
  return <ReportChat initialFirmwareId={initialFirmwareId} />;
}

export default function AssistantPage({
  searchParams,
}: {
  searchParams: { firmwareId?: string };
}) {
  return (
    <div className="flex min-h-screen w-full bg-white dark:bg-black overflow-hidden">
      <div className="w-56 shrink-0 hidden md:block" />

      <div className="flex flex-col flex-1 min-w-0 relative">
        <Navbar />
        <FloatingParticles />

        <div className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,rgba(139,92,246,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.08)_1px,transparent_1px)] dark:bg-[linear-gradient(to_right,rgba(139,92,246,0.1)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.1)_1px,transparent_1px)] bg-[size:48px_48px]" />

        <div className="relative z-10 w-full px-4 sm:px-6 md:px-10 pt-20 md:pt-8 pb-8 space-y-6">
          <div className="max-w-3xl mx-auto w-full">
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
              Report Assistant
            </h1>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 mb-6">
              Ask questions about any completed firmware analysis
            </p>
          </div>

          <Suspense
            fallback={
              <div className="flex items-center justify-center py-20">
                <Loader2Icon className="h-8 w-8 text-violet-500 animate-spin" />
              </div>
            }
          >
            <AssistantContent searchParams={searchParams} />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
