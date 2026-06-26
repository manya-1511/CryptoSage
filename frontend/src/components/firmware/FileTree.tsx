"use client";
import { useState } from "react";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileText,
} from "lucide-react";
import { formatBytes } from "@/lib/utils";
import type { FileTreeNode } from "@/types/firmware";

function TreeNode({ node, depth = 0 }: { node: FileTreeNode; depth?: number }) {
  const [open, setOpen] = useState(depth < 2);
  const isDir = node.type === "directory";

  return (
    <div>
      <button
        onClick={() => isDir && setOpen((o) => !o)}
        className="flex items-center gap-1.5 w-full text-left hover:bg-white/5 rounded px-2 py-0.5 group transition-colors"
        style={{ paddingLeft: `${8 + depth * 16}px` }}
      >
        {isDir ? (
          <>
            <span className="text-gray-600 w-3">
              {open ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
            </span>
            {open ? (
              <FolderOpen className="w-3.5 h-3.5 text-yellow-400 shrink-0" />
            ) : (
              <Folder className="w-3.5 h-3.5 text-yellow-500 shrink-0" />
            )}
          </>
        ) : (
          <>
            <span className="w-3" />
            <FileText className="w-3.5 h-3.5 text-gray-400 shrink-0" />
          </>
        )}
        <span className="font-mono text-xs text-gray-300 truncate flex-1">
          {node.name}
        </span>
        {node.size !== undefined && (
          <span className="text-xs text-gray-600 ml-2 opacity-0 group-hover:opacity-100">
            {formatBytes(node.size)}
          </span>
        )}
      </button>
      {isDir && open && node.children && (
        <div>
          {node.children.map((child, i) => (
            <TreeNode
              key={`${child.name}-${i}`}
              node={child}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileTree({ tree }: { tree: FileTreeNode }) {
  return (
    <div className="font-mono text-sm overflow-auto max-h-96 pr-2">
      <TreeNode node={tree} />
    </div>
  );
}
