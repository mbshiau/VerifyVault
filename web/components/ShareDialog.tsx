"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Analysis, updateVisibility } from "@/lib/api";

type Visibility = "private" | "unlisted" | "public";

const VISIBILITY_COPY: Record<Visibility, { label: string; hint: string }> = {
  private: { label: "Private", hint: "Only you can view this." },
  unlisted: { label: "Unlisted", hint: "Anyone with the link can view it. Not searchable." },
  public: { label: "Public", hint: "Anyone with the link can view it, and it may appear in the public library." },
};

export function ShareDialog({
  analysis,
  open,
  onClose,
}: {
  analysis: Pick<Analysis, "id" | "visibility" | "share_token">;
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [copied, setCopied] = useState(false);

  const mutation = useMutation({
    mutationFn: (visibility: Visibility) => updateVisibility(analysis.id, visibility),
    onSuccess: (updated) => {
      queryClient.setQueryData(["analysis", analysis.id], updated);
      queryClient.invalidateQueries({ queryKey: ["analyses"] });
    },
  });

  if (!open) return null;

  const visibility = (mutation.data?.visibility ?? analysis.visibility) as Visibility;
  const shareToken = mutation.data?.share_token ?? analysis.share_token;
  const shareUrl = shareToken && typeof window !== "undefined" ? `${window.location.origin}/share/${shareToken}` : "";

  async function copyLink() {
    if (!shareUrl) return;
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-md bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <h2 className="text-base font-semibold text-neutral-900">Share this analysis</h2>

        <fieldset className="mt-4 space-y-2">
          {(Object.keys(VISIBILITY_COPY) as Visibility[]).map((v) => (
            <label
              key={v}
              className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 text-sm ${
                visibility === v ? "border-neutral-900 bg-neutral-50" : "border-neutral-200"
              }`}
            >
              <input
                type="radio"
                name="visibility"
                className="mt-0.5"
                checked={visibility === v}
                onChange={() => mutation.mutate(v)}
                disabled={mutation.isPending}
              />
              <span>
                <span className="block font-medium text-neutral-900">{VISIBILITY_COPY[v].label}</span>
                <span className="block text-xs text-neutral-500">{VISIBILITY_COPY[v].hint}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <div className="mt-4 border-t border-neutral-200 pt-4">
          <span className="block text-xs font-medium text-neutral-700">Share link</span>
          {visibility === "private" ? (
            <p className="mt-1.5 text-xs text-neutral-500">Change visibility to Unlisted or Public to get a link.</p>
          ) : (
            <div className="mt-1.5 flex gap-2">
              <input
                readOnly
                value={shareUrl}
                onFocus={(e) => e.currentTarget.select()}
                className="min-w-0 flex-1 rounded border border-neutral-300 bg-neutral-50 px-2 py-1.5 text-xs text-neutral-700"
              />
              <button
                type="button"
                onClick={copyLink}
                className="shrink-0 rounded-md border border-neutral-300 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-50"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
          )}
        </div>

        {mutation.isError && (
          <p className="mt-3 text-xs text-red-600">
            {mutation.error instanceof Error ? mutation.error.message : "Failed to update visibility."}
          </p>
        )}

        <div className="mt-5 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-sm border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
