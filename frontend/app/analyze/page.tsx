import { Suspense } from "react";
import Navbar from "@/components/Navbar";
import AnalysisIntro from "@/components/analysis/AnalysisIntro";
import FeatureCards from "@/components/analysis/FeatureCards";
import FirmwareUploadWidget from "@/components/analysis/FirmwareUploadWidget";
import FloatingParticles from "@/components/FloatingParticles";
import { Loader2Icon } from "lucide-react";

export default function AnalyzePage() {
  return (
    <div className="flex min-h-screen w-full bg-white dark:bg-black overflow-hidden">
      <div className="w-56 shrink-0 hidden md:block" />

      <div className="flex flex-col flex-1 min-w-0 relative min-h-screen">
        <div className="absolute inset-0 pointer-events-none">
          <FloatingParticles />
        </div>

        <div
          className="
            absolute inset-0 -z-10
            bg-[linear-gradient(to_right,rgba(139,92,246,0.08)_1px,transparent_1px),
               linear-gradient(to_bottom,rgba(139,92,246,0.08)_1px,transparent_1px)]
            dark:bg-[linear-gradient(to_right,rgba(139,92,246,0.1)_1px,transparent_1px),
                     linear-gradient(to_bottom,rgba(139,92,246,0.1)_1px,transparent_1px)]
            bg-[size:48px_48px]
          "
        />

        <Navbar />

        <main className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 pt-20 md:pt-8 pb-2 space-y-2 w-full">
          <AnalysisIntro />
          <FeatureCards />
        </main>

        <div className="flex-1 flex items-center justify-center">
          <Suspense
            fallback={
              <div className="flex items-center justify-center py-20">
                <Loader2Icon className="h-8 w-8 text-violet-500 animate-spin" />
              </div>
            }
          >
            <FirmwareUploadWidget />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
