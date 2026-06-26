"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { firmwareApi } from "@/lib/api";
import {
  formatBytes,
  formatDate,
  getStatusColor,
  getExtensionIcon,
} from "@/lib/utils";
import { Upload, Trash2, Eye, Cpu, Search } from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";

export default function FirmwareListPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const PAGE_SIZE = 15;

  const { data, isLoading } = useQuery({
    queryKey: ["firmware", "list", page],
    queryFn: () => firmwareApi.list(page, PAGE_SIZE),
    refetchInterval: 15000,
  });

  const deleteMutation = useMutation({
    mutationFn: firmwareApi.delete,
    onSuccess: () => {
      toast.success("Firmware deleted");
      qc.invalidateQueries({ queryKey: ["firmware"] });
    },
    onError: () => toast.error("Delete failed"),
  });

  const filtered = (data?.items ?? []).filter((f) =>
    f.original_filename.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Firmware Library</h1>
          <p className="text-gray-500 text-sm mt-1">
            {data?.total ?? 0} total uploads
          </p>
        </div>
        <Link href="/upload" className="btn-primary">
          <Upload className="w-4 h-4" />
          Upload Firmware
        </Link>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
        <input
          type="text"
          placeholder="Search by filename…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input pl-10"
        />
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="p-8 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="h-14 bg-white/5 rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <Cpu className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No firmware found.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-white/3">
              <tr className="text-xs text-gray-500 uppercase">
                <th className="text-left px-6 py-3 font-medium">Filename</th>
                <th className="text-left px-4 py-3 font-medium">Size</th>
                <th className="text-left px-4 py-3 font-medium">Type</th>
                <th className="text-left px-4 py-3 font-medium">
                  Architecture
                </th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Uploaded</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filtered.map((fw) => (
                <tr
                  key={fw.id}
                  className="hover:bg-white/3 transition-colors group"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <span className="text-base">
                        {getExtensionIcon(fw.file_extension)}
                      </span>
                      <span className="font-mono text-xs text-gray-200 max-w-[180px] truncate">
                        {fw.original_filename}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-gray-400">
                    {formatBytes(fw.file_size)}
                  </td>
                  <td className="px-4 py-4">
                    <span className="font-mono text-xs bg-white/5 px-2 py-0.5 rounded">
                      {fw.file_extension}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-gray-400 text-xs">
                    {fw.architecture ?? "—"}
                  </td>
                  <td className="px-4 py-4">
                    <span className={`badge ${getStatusColor(fw.status)}`}>
                      {fw.status}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-gray-500 text-xs">
                    {formatDate(fw.created_at)}
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Link
                        href={`/firmware/${fw.id}`}
                        className="p-1.5 rounded hover:bg-white/10 text-gray-400 hover:text-sage-400 transition-colors"
                        title="View"
                      >
                        <Eye className="w-4 h-4" />
                      </Link>
                      <button
                        onClick={() => deleteMutation.mutate(fw.id)}
                        className="p-1.5 rounded hover:bg-red-500/10 text-gray-400 hover:text-red-400 transition-colors"
                        title="Delete"
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {(data?.total ?? 0) > PAGE_SIZE && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-ghost text-sm px-3 py-1.5"
          >
            ← Prev
          </button>
          <span className="text-gray-500 text-sm py-1.5">
            Page {page} of {Math.ceil((data?.total ?? 0) / PAGE_SIZE)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page * PAGE_SIZE >= (data?.total ?? 0)}
            className="btn-ghost text-sm px-3 py-1.5"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
