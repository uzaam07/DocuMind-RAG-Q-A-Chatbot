import { FileUp } from 'lucide-react';

export default function DropOverlay() {
  return (
    <div className="drop" aria-hidden="true">
      <div className="drop__panel">
        <FileUp size={24} strokeWidth={1.5} />
        <p className="drop__title">Drop to upload</p>
        <p className="drop__sub">PDF, DOCX, XLSX, PPTX, HTML and images</p>
      </div>
    </div>
  );
}
