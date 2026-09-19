"use client";

import {
  HomeIcon,
  ScanLineIcon,
  HistoryIcon,
  MessageSquareIcon,
  MoonIcon,
  SunIcon,
  LogOutIcon,
  MenuIcon,
  XIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { UserButton, useUser, useClerk } from "@clerk/nextjs";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { LogoMark, LogoWordmark } from "@/components/logo";

const NAV = [
  { href: "/dashboard", icon: HomeIcon, label: "Dashboard" },
  { href: "/analyze", icon: ScanLineIcon, label: "Analyze" },
  { href: "/firmware", icon: HistoryIcon, label: "Firmware History" },
  { href: "/assistant", icon: MessageSquareIcon, label: "Report Assistant" },
];

export default function Navbar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const { user } = useUser();
  const { signOut } = useClerk();
  const [mounted, setMounted] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => setMounted(true), []);

  const navItem = (path: string) =>
    cn(
      "relative flex items-center gap-3 px-3 py-3 rounded-xl text-[14px] font-medium transition-all duration-150 border overflow-hidden",
      pathname === path
        ? "font-semibold border dark:text-violet-300 dark:bg-violet-500/[0.12] dark:border-violet-500/25 text-violet-800 bg-violet-100 border-violet-300"
        : "border-transparent dark:text-gray-200 dark:hover:text-violet-300 dark:hover:bg-violet-500/[0.08] dark:hover:border-violet-500/15 text-gray-700 hover:text-violet-800 hover:bg-violet-50 hover:border-violet-200"
    );

  const SidebarContent = () => (
    <>
      <div className="pointer-events-none absolute bottom-0 right-0 w-40 h-40 rounded-full bg-violet-500/[0.06] blur-2xl hidden dark:block" />
      <div className="pointer-events-none absolute top-0 left-0 w-40 h-40 rounded-full bg-fuchsia-500/[0.04] blur-3xl hidden dark:block" />

      <div className="px-5 pt-7 pb-5 flex items-center gap-3">
        <div className="w-[42px] h-[42px] rounded-xl flex items-center justify-center flex-shrink-0 bg-violet-100 border border-violet-300 dark:bg-violet-500/10 dark:border-violet-500/40 shadow-[0_0_15px_rgba(139,92,246,0.2)]">
          <LogoMark className="w-6 h-6" />
        </div>
        <LogoWordmark className="text-[22px] tracking-tight" />
      </div>

      <div className="mx-3 mb-5">
        <div className="flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 bg-violet-50 border border-violet-200 hover:border-violet-300 hover:bg-violet-100/60 dark:bg-violet-500/[0.08] dark:border-violet-500/[0.2] dark:hover:border-violet-500/30 dark:hover:bg-violet-500/[0.12]">
          {mounted && user ? (
            <UserButton appearance={{ elements: { avatarBox: "h-10 w-10" } }} />
          ) : (
            <div className="h-10 w-10 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 bg-violet-100 border border-violet-300 text-violet-800 dark:bg-violet-500/20 dark:border-violet-400/60 dark:text-violet-300">
              {user?.firstName?.[0] ?? "U"}
            </div>
          )}
          <div className="overflow-hidden">
            <p className="text-[13px] font-bold text-gray-900 dark:text-gray-100 truncate">
              {user?.fullName ?? "User"}
            </p>
            <p className="text-[11px] text-gray-500 dark:text-gray-400 truncate">
              {user?.primaryEmailAddress?.emailAddress ?? ""}
            </p>
          </div>
        </div>
      </div>

      <div className="mx-3.5 mb-3 h-px bg-violet-500/15 dark:bg-violet-500/15" />
      <p className="px-5 mb-2.5 text-[10px] uppercase tracking-[0.14em] font-bold text-gray-500 dark:text-gray-400">
        Navigation
      </p>

      <nav className="flex-1 px-2 flex flex-col gap-1">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = pathname === href;
          return (
            <Link key={href} href={href} className={navItem(href)} onClick={() => setMobileOpen(false)}>
              {active && (
                <span className="absolute left-0 top-[20%] bottom-[20%] w-[3px] rounded-r-full bg-violet-700 shadow-[0_0_6px_rgba(124,58,237,0.5)] dark:bg-violet-400 dark:shadow-[0_0_8px_rgba(167,139,250,0.9)]" />
              )}
              <Icon
                className={cn(
                  "h-[16px] w-[16px] flex-shrink-0",
                  active ? "text-violet-700 dark:text-violet-300" : "text-gray-500 dark:text-gray-400"
                )}
              />
              <span className={active ? "text-violet-800 dark:text-violet-300" : "text-gray-700 dark:text-gray-200"}>
                {label}
              </span>
              {active && (
                <motion.span
                  className="ml-auto w-[6px] h-[6px] rounded-full bg-violet-600 dark:bg-violet-400"
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ duration: 1.8, repeat: Infinity }}
                />
              )}
            </Link>
          );
        })}
      </nav>

      <div className="px-2 pb-6 pt-3 flex flex-col gap-1.5 mt-2 border-t border-violet-500/15 dark:border-violet-500/15">
        {mounted && (
          <div className="flex items-center justify-between px-3 py-2.5 rounded-xl bg-violet-50 border border-violet-200 dark:bg-violet-500/[0.06] dark:border-violet-500/[0.15]">
            <div className="flex items-center gap-2 text-[13px] font-semibold text-gray-700 dark:text-gray-200">
              {theme === "dark" ? (
                <MoonIcon className="h-3.5 w-3.5 text-violet-400" />
              ) : (
                <SunIcon className="h-3.5 w-3.5 text-amber-500" />
              )}
              {theme === "dark" ? "Dark" : "Light"}
            </div>
            <button
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className={cn(
                "relative w-10 h-[20px] rounded-full transition-all duration-300",
                theme === "dark"
                  ? "bg-gradient-to-r from-violet-700 to-fuchsia-500 shadow-[0_0_10px_rgba(139,92,246,0.4)]"
                  : "bg-gray-300"
              )}
            >
              <motion.span
                layout
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
                className={cn(
                  "absolute top-[2.5px] w-[15px] h-[15px] rounded-full bg-white shadow",
                  theme === "dark" ? "left-[22px]" : "left-[2px]"
                )}
              />
            </button>
          </div>
        )}

        <button
          onClick={() => signOut()}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13.5px] font-semibold w-full text-left transition-all border border-transparent text-red-500 hover:text-red-700 hover:bg-red-50 hover:border-red-100 dark:text-red-400 dark:hover:text-red-300 dark:hover:bg-red-500/[0.08] dark:hover:border-red-500/15"
        >
          <LogOutIcon className="h-[15px] w-[15px] flex-shrink-0" />
          Log out
        </button>
      </div>
    </>
  );

  return (
    <>
      <aside className="fixed top-0 left-0 h-full w-56 z-50 flex-col overflow-hidden hidden md:flex bg-white dark:bg-black border-r border-violet-500/20 dark:border-violet-500/10 shadow-[4px_0_24px_rgba(0,0,0,0.06)] dark:shadow-[4px_0_40px_rgba(0,0,0,0.6),1px_0_0_rgba(139,92,246,0.08)]">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(to_right,rgba(139,92,246,0.04)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.04)_1px,transparent_1px)] dark:bg-[linear-gradient(to_right,rgba(139,92,246,0.06)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.06)_1px,transparent_1px)] bg-[size:48px_48px]" />
        <SidebarContent />
      </aside>

      <div className="fixed top-0 left-0 right-0 z-50 flex md:hidden items-center justify-between px-4 py-3 bg-white/95 dark:bg-black/95 backdrop-blur-md border-b border-violet-500/20 dark:border-violet-500/10">
        <div className="flex items-center gap-2">
          <LogoMark className="w-6 h-6" />
          <LogoWordmark className="text-base" />
        </div>
        <button
          onClick={() => setMobileOpen(true)}
          className="p-2 rounded-lg text-gray-700 dark:text-gray-200 hover:bg-violet-50 dark:hover:bg-violet-500/10"
        >
          <MenuIcon className="h-5 w-5" />
        </button>
      </div>

      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm md:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.div
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="fixed top-0 left-0 h-full w-64 z-50 flex flex-col overflow-hidden md:hidden bg-white dark:bg-black border-r border-violet-500/20 dark:border-violet-500/10 shadow-[4px_0_40px_rgba(0,0,0,0.3)]"
            >
              <button
                onClick={() => setMobileOpen(false)}
                className="absolute top-4 right-4 p-1.5 rounded-lg text-gray-500 hover:bg-violet-50 dark:hover:bg-violet-500/10 z-10"
              >
                <XIcon className="h-5 w-5" />
              </button>
              <SidebarContent />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
