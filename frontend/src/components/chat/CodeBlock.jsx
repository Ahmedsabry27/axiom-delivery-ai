import { useState } from "react";
import { Copy, Check } from "lucide-react";

import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

export default function CodeBlock({
  language = "text",
  code,
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code);

      setCopied(true);

      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch (error) {
      console.error("Copy failed", error);
    }
  }

  return (
    <div className="my-6 overflow-hidden rounded-2xl border border-border shadow-sm">

      {/* Header */}

      <div className="flex items-center justify-between border-b bg-slate-800 px-4 py-3">

        <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
          {language}
        </span>

        <button
          onClick={handleCopy}
          className="
            flex
            items-center
            gap-2
            rounded-lg
            px-3
            py-2
            text-xs
            text-slate-300
            transition-colors
            hover:bg-slate-700
            hover:text-white
          "
        >
          {copied ? (
            <>
              <Check className="h-4 w-4 text-emerald-400" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-4 w-4" />
              Copy
            </>
          )}
        </button>
      </div>

      {/* Code */}

      <SyntaxHighlighter
        language={language}
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          fontSize: "14px",
          padding: "20px",
          background: "#0f172a",
        }}
        wrapLongLines={false}
        showLineNumbers={false}
      >
        {code}
      </SyntaxHighlighter>

    </div>
  );
}