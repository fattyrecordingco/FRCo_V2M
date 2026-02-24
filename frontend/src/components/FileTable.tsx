import { FileEntry } from "../lib/types";
import { fileUrl } from "../lib/api";

interface Props {
  title: string;
  files: FileEntry[];
  selectedPath: string | null;
  onSelect: (file: FileEntry) => void;
  onRename: (file: FileEntry) => void;
}

export default function FileTable({ title, files, selectedPath, onSelect, onRename }: Props) {
  const visibleFiles = files.slice(0, 6);

  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold">{title}</div>
      <div className="file-table-shell">
        {files.length === 0 && <div className="p-2 text-xs text-slate-500">No files yet.</div>}
        {visibleFiles.map((file) => {
          const selected = selectedPath === file.relative_path;
          const absoluteUrl = fileUrl(file.url);
          return (
            <div
              key={`${file.relative_path}-${file.run_id}`}
              className={`file-row ${selected ? "is-selected" : ""}`}
              draggable
              onDragStart={(event) => {
                event.dataTransfer.setData("text/uri-list", absoluteUrl);
                event.dataTransfer.setData("DownloadURL", `${file.mime_type}:${file.name}:${absoluteUrl}`);
              }}
              onDoubleClick={() => onSelect(file)}
            >
              <button type="button" className="min-w-0 flex-1 truncate text-left font-medium" onClick={() => onSelect(file)}>
                {file.name}
              </button>
              <span className="run-badge">{file.run_id}</span>
              <a className="btn btn-secondary table-btn" href={absoluteUrl} download>
                Download
              </a>
              <button type="button" className="btn btn-secondary table-btn" onClick={() => onRename(file)}>
                Rename
              </button>
              <span className={`sel-indicator ${selected ? "is-visible" : ""}`}>Selected</span>
            </div>
          );
        })}
        {files.length > visibleFiles.length && (
          <div className="p-2 text-[11px] text-slate-500">+{files.length - visibleFiles.length} more files in archive</div>
        )}
      </div>
    </div>
  );
}
