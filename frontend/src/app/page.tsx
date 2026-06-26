"use client";
import { useQuery } from "@tanstack/react-query";
import { firmwareApi } from "@/lib/api";
import { formatBytes, formatDate, getStatusColor } from "@/lib/utils";
import { Cpu, Upload, CheckCircle, AlertTriangle, Package } from "lucide-react";
import Link from "next/link";
import type { Firmware } from "@/types/firmware";

function StatCard({
  icon: Icon,
  label,
  value,
  color = "text-sage-400",
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="card glow-green">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
            {label}
          </p>
          <p className={`text-3xl font-bold ${color}`}>{value}</p>
        </div>
        <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center">
          <Icon className={`w-5 h-5 ${color}`} />
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["firmware", "list"],
    queryFn: () => firmwareApi.list(1, 100),
    refetchInterval: 10000,
  });

  const firmwares = data?.items ?? [];
  const total = data?.total ?? 0;
  const extracted = firmwares.filter((f) => f.status === "extracted").length;
  const invalid = firmwares.filter((f) => f.status === "invalid").length;
  const totalSize = firmwares.reduce((sum, f) => sum + f.file_size, 0);
  const recent = [...firmwares].slice(0, 8);

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">
          Firmware upload, extraction, and analysis overview
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard icon={Package} label="Total Firmware" value={total} />
        <StatCard
          icon={CheckCircle}
          label="Extracted"
          value={extracted}
          color="text-green-400"
        />
        <StatCard
          icon={AlertTriangle}
          label="Invalid"
          value={invalid}
          color="text-red-400"
        />
        <StatCard
          icon={Cpu}
          label="Total Size"
          value={formatBytes(totalSize)}
        />
      </div>

      {/* Recent uploads table */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-white">Recent Firmware</h2>
          <Link href="/upload" className="btn-primary text-sm py-1.5">
            <Upload className="w-3.5 h-3.5" />
            Upload New
          </Link>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="h-12 bg-white/5 rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : recent.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Package className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No firmware uploaded yet.</p>
            <Link
              href="/upload"
              className="text-sage-400 hover:underline text-sm mt-1 inline-block"
            >
              Upload your first firmware →
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 uppercase border-b border-white/5">
                  <th className="text-left pb-3 font-medium">Filename</th>
                  <th className="text-left pb-3 font-medium">Size</th>
                  <th className="text-left pb-3 font-medium">Type</th>
                  <th className="text-left pb-3 font-medium">Status</th>
                  <th className="text-left pb-3 font-medium">Uploaded</th>
                  <th className="text-left pb-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {recent.map((fw: Firmware) => (
                  <tr
                    key={fw.id}
                    className="hover:bg-white/3 transition-colors"
                  >
                    <td className="py-3 font-mono text-xs text-gray-200 max-w-[200px] truncate">
                      {fw.original_filename}
                    </td>
                    <td className="py-3 text-gray-400">
                      {formatBytes(fw.file_size)}
                    </td>
                    <td className="py-3">
                      <span className="font-mono text-xs bg-white/5 px-2 py-0.5 rounded">
                        {fw.file_extension}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className={`badge ${getStatusColor(fw.status)}`}>
                        {fw.status}
                      </span>
                    </td>
                    <td className="py-3 text-gray-500 text-xs">
                      {formatDate(fw.created_at)}
                    </td>
                    <td className="py-3">
                      <Link
                        href={`/firmware/${fw.id}`}
                        className="text-sage-400 hover:text-sage-300 text-xs"
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
