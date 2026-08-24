import { Bot, User } from "lucide-react";

export default function Avatar({
  role = "assistant",
  size = "md",
}) {
  const sizes = {
    sm: {
      container: "h-8 w-8 rounded-xl",
      icon: "h-4 w-4",
    },
    md: {
      container: "h-10 w-10 rounded-2xl",
      icon: "h-5 w-5",
    },
    lg: {
      container: "h-12 w-12 rounded-2xl",
      icon: "h-6 w-6",
    },
  };

  const currentSize = sizes[size];

  if (role === "user") {
    return (
      <div
        className={`
          ${currentSize.container}
          flex
          shrink-0
          items-center
          justify-center
          bg-slate-700
          text-white
          shadow-sm
        `}
      >
        <User className={currentSize.icon} />
      </div>
    );
  }

  return (
    <div
      className={`
        ${currentSize.container}
        flex
        shrink-0
        items-center
        justify-center
        bg-emerald-600
        text-white
        shadow-sm
      `}
    >
      <Bot className={currentSize.icon} />
    </div>
  );
}