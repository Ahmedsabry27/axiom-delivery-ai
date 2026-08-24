import { X } from "lucide-react";
export default function DetailDrawer({ open, title, children, onClose }) {
  if (!open) return null;
  return <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40" role="presentation" onMouseDown={(e)=>{if(e.target===e.currentTarget)onClose();}}><section role="dialog" aria-modal="true" aria-labelledby="detail-drawer-title" className="h-full w-full max-w-lg overflow-y-auto bg-white p-6 text-slate-900 shadow-2xl"><div className="flex items-start justify-between gap-4"><h2 id="detail-drawer-title" className="text-xl font-semibold">{title}</h2><button autoFocus type="button" onClick={onClose} aria-label="Close details" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-600"><X className="h-5 w-5"/></button></div>{children}</section></div>;
}
