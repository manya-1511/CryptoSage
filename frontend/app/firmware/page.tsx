import Navbar from "@/components/Navbar";
import FloatingParticles from "@/components/FloatingParticles";
import FirmwareList from "@/components/firmware/FirmwareList";

export default function FirmwarePage() {
  return (
    <div className="flex min-h-screen w-full bg-white dark:bg-black overflow-hidden">
      <div className="w-56 shrink-0 hidden md:block" />

      <div className="flex flex-col flex-1 min-w-0 relative">
        <Navbar />
        <FloatingParticles />

        <div className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,rgba(139,92,246,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.08)_1px,transparent_1px)] dark:bg-[linear-gradient(to_right,rgba(139,92,246,0.1)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.1)_1px,transparent_1px)] bg-[size:48px_48px]" />
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_center,rgba(139,92,246,0.05),transparent_70%)] dark:bg-[radial-gradient(circle_at_center,rgba(139,92,246,0.1),transparent_70%)]" />

        <div className="relative z-10 w-full px-4 sm:px-6 md:px-10 pt-20 md:pt-8 pb-8 space-y-6">
          <FirmwareList />
        </div>
      </div>
    </div>
  );
}
