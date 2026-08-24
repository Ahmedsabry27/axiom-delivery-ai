import { useState } from "react";
import { Copy, Check } from "lucide-react";

export default function CopyButton({
  text,
  className = "",
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);

      setCopied(true);

      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch (error) {
      console.error("Failed to copy text:", error);
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? "Copied" : "Copy"}
      className={`
        inline-flex
        items-center
        gap-2
        rounded-lg
        border
        border-border
        bg-background
        px-3
        py-2
        text-sm
        text-muted-foreground
        transition-all
        duration-200
        hover:bg-muted
        hover:text-foreground
        ${className}
      `}
    >
      {copied ? (
        <>
          <Check className="h-4 w-4 text-emerald-600" />
          <span>Copied</span>
        </>
      ) : (
        <>
          <Copy className="h-4 w-4" />
          <span>Copy</span>
        </>
      )}
    </button>
  );
}