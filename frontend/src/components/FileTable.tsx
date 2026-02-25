import { FileEntry } from "../lib/types";
import { fileUrl } from "../lib/api";

interface Props {
  title: string;
  files: FileEntry[];
  selectedPath: string | null;
  onSelect: (file: FileEntry) => void;
  onRename: (file: FileEntry) => void;
}

function IconDownload() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M12 3a1 1 0 0 1 1 1v8.58l2.3-2.29a1 1 0 1 1 1.4 1.42l-4 3.97a1 1 0 0 1-1.4 0l-4-3.97a1 1 0 1 1 1.4-1.42L11 12.58V4a1 1 0 0 1 1-1Z" />
      <path d="M5 15a1 1 0 0 1 1 1v3h12v-3a1 1 0 1 1 2 0v4a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1Z" />
    </svg>
  );
}

export default function FileTable({ title, files, selectedPath, onSelect, onRename }: Props) {
  return (
    <div className="file-section">
      <div className="file-section-title">{title}</div>
      <div className="file-table-shell scroll-region">
        {files.length === 0 && <div className="file-empty">No files yet.</div>}
        {files.map((file) => {
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
              onDoubleClick={() => onRename(file)}
            >
              <button type="button" className="file-name-btn" onClick={() => onSelect(file)}>
                {file.name}
              </button>
              <span className="run-badge">{file.run_id}</span>
              <a className="btn btn-secondary table-btn icon-only" href={absoluteUrl} download title="Download file">
                <span className="btn-icon">
                  <IconDownload />
                </span>
              </a>
            </div>
          );
        })}
      </div>
    </div>
  );
}
