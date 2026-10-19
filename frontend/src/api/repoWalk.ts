/**
 * Repo snapshot ingestion: walk a user-selected directory (File System API
 * directory picker) and produce the payload for POST /tasks/{id}/repo.
 */

const SKIP_DIRS = new Set([
  'node_modules', '.git', '.venv', 'venv', 'dist', 'build', '.next',
  '.cache', '__pycache__', '.idea', '.vscode', 'coverage', '.wrangler',
]);

const MAX_FILES = 500;
const MAX_FILE_SIZE = 512 * 1024; // 512 KiB per file

export interface RepoFilePayload {
  path: string;
  language?: string;
  size: number;
  content: string;
}

const LANG_BY_EXT: Record<string, string> = {
  '.ts': 'typescript', '.tsx': 'typescript', '.js': 'javascript', '.jsx': 'javascript',
  '.py': 'python', '.go': 'go', '.rs': 'rust', '.java': 'java', '.c': 'c', '.cpp': 'cpp',
  '.cs': 'csharp', '.rb': 'ruby', '.php': 'php', '.html': 'html', '.css': 'css',
  '.scss': 'scss', '.json': 'json', '.toml': 'toml', '.yaml': 'yaml', '.yml': 'yaml',
  '.sql': 'sql', '.md': 'markdown', '.sh': 'shell', '.kt': 'kotlin', '.swift': 'swift',
};

export function guessLanguage(name: string): string | undefined {
  const idx = name.lastIndexOf('.');
  if (idx === -1) return undefined;
  return LANG_BY_EXT[name.slice(idx).toLowerCase()];
}

export async function walkRepoFiles(files: File[]): Promise<RepoFilePayload[]> {
  const out: RepoFilePayload[] = [];
  let count = 0;
  for (const file of files) {
    if (count >= MAX_FILES) break;
    const parts = (file.webkitRelativePath || file.name).split('/');
    if (parts.some((p) => SKIP_DIRS.has(p))) continue;
    if (file.size > MAX_FILE_SIZE) continue;
    const content = await file.text();
    out.push({
      path: parts.slice(1).join('/') || file.name,
      language: guessLanguage(file.name),
      size: file.size,
      content,
    });
    count += 1;
  }
  return out;
}

export function openDirectoryPicker(): Promise<File[]> {
  return new Promise((resolve, reject) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.setAttribute('webkitdirectory', '');
    input.setAttribute('multiple', '');
    input.onchange = () => resolve(Array.from(input.files ?? []));
    input.onerror = () => reject(new Error('directory picker failed'));
    input.click();
  });
}