"use client";

import { useId, useRef, useState, type ReactNode } from "react";

type Annotation = {
  id: string;
  x: number;
  y: number;
  subject: string;
  text: string;
  minimized: boolean;
};

export function AnnotationLayer({ active, children }: { active: boolean; children: ReactNode }) {
  const zoneId = useId();
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const justDraggedRef = useRef<string | null>(null);

  // Runs in the capture phase so it can intercept a click before it reaches an
  // underlying link/button/claim-highlight - but only for the click event type,
  // so wheel/scroll on the two panels underneath is never touched. Capture fires
  // outermost-first, so if this click actually belongs to a more deeply nested
  // annotation zone (e.g. a scrollable panel nested inside a page-level zone),
  // this bails out and lets that inner zone's own capture handler claim it -
  // that's what anchors a note to the scrollable content it was placed on,
  // rather than to the outer page.
  function handleCreate(e: React.MouseEvent<HTMLDivElement>) {
    if (!active) return;
    const target = e.target as HTMLElement;
    if (target.closest("[data-annotation-note]")) return;
    const nearestZone = target.closest("[data-annotation-zone]");
    if (nearestZone !== wrapperRef.current) return;
    e.preventDefault();
    e.stopPropagation();
    const rect = wrapperRef.current!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const id = `note-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setAnnotations((prev) => [...prev, { id, x, y, subject: "", text: "", minimized: false }]);
  }

  function update(id: string, patch: Partial<Annotation>) {
    setAnnotations((prev) => prev.map((a) => (a.id === id ? { ...a, ...patch } : a)));
  }

  function remove(id: string) {
    setAnnotations((prev) => prev.filter((a) => a.id !== id));
  }

  function startDrag(e: React.MouseEvent, id: string, originX: number, originY: number) {
    if (!active) return;
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const startY = e.clientY;
    let moved = false;
    const prevUserSelect = document.body.style.userSelect;
    document.body.style.userSelect = "none";

    function onMove(ev: MouseEvent) {
      const dx = ev.clientX - startX;
      const dy = ev.clientY - startY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) moved = true;
      update(id, { x: originX + dx, y: originY + dy });
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.userSelect = prevUserSelect;
      if (moved) justDraggedRef.current = id;
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  return (
    <div
      ref={wrapperRef}
      data-annotation-zone={zoneId}
      onClickCapture={handleCreate}
      className={`relative ${active ? "cursor-crosshair" : ""}`}
    >
      {children}

      {annotations.map((a) =>
        a.minimized ? (
          <button
            key={a.id}
            type="button"
            data-annotation-note
            onMouseDown={(e) => startDrag(e, a.id, a.x, a.y)}
            onClick={(e) => {
              e.stopPropagation();
              if (justDraggedRef.current === a.id) {
                justDraggedRef.current = null;
                return;
              }
              update(a.id, { minimized: false });
            }}
            style={{ left: a.x, top: a.y }}
            className={`absolute z-40 -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded-full
                       border border-yellow-400 bg-yellow-200 px-2.5 py-1 text-xs font-medium text-neutral-800
                       shadow-md hover:bg-yellow-300 ${active ? "cursor-move" : "cursor-pointer"}`}
          >
            ✏️ {a.subject || "Note"}
          </button>
        ) : (
          <div
            key={a.id}
            data-annotation-note
            style={{ left: a.x, top: a.y }}
            className="absolute z-40 w-64 -translate-x-1/2 rounded-lg border border-yellow-300
                       bg-yellow-100 p-3 shadow-xl"
          >
            <div className="mb-2 flex items-center gap-1">
              <span
                onMouseDown={(e) => startDrag(e, a.id, a.x, a.y)}
                title="Drag to move"
                className={`flex-none select-none px-0.5 text-neutral-400 ${
                  active ? "cursor-move" : "cursor-default"
                }`}
              >
                ⠿
              </span>
              <input
                value={a.subject}
                onChange={(e) => update(a.id, { subject: e.target.value })}
                placeholder="Subject"
                autoFocus
                className="min-w-0 flex-1 border-b border-yellow-300 bg-transparent pb-1 text-sm font-semibold
                           text-neutral-900 outline-none placeholder:font-normal placeholder:text-neutral-400"
              />
              <button
                type="button"
                onClick={() => update(a.id, { minimized: true })}
                title="Minimize"
                className="flex-none rounded px-1.5 py-0.5 text-xs text-neutral-500 hover:bg-yellow-200"
              >
                –
              </button>
              <button
                type="button"
                onClick={() => remove(a.id)}
                title="Delete note"
                className="flex-none rounded px-1.5 py-0.5 text-xs text-neutral-500 hover:bg-yellow-200"
              >
                ×
              </button>
            </div>
            <textarea
              value={a.text}
              onChange={(e) => update(a.id, { text: e.target.value })}
              placeholder="Type a note..."
              rows={4}
              className="w-full resize-none bg-transparent text-sm text-neutral-800 outline-none
                         placeholder:text-neutral-400"
            />
          </div>
        )
      )}
    </div>
  );
}
