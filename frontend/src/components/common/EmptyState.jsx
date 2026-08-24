import { Bot } from "lucide-react";

const suggestions = [
  "Design an AWS architecture",
  "Explain Amazon Bedrock",
  "Generate SQL query",
  "Review my code",
];

export default function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-8">

      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500">
        <Bot className="h-8 w-8 text-white" />
      </div>

      <h1 className="text-3xl font-semibold">
        Axiom Delivery AI
      </h1>

      <p className="mt-2 text-muted-foreground">
        How can I help you today?
      </p>

      <div className="mt-10 grid grid-cols-2 gap-3 max-w-2xl">

        {suggestions.map((item) => (
          <button
            key={item}
            className="
              rounded-xl
              border
              bg-card
              p-4
              text-left
              transition
              hover:bg-accent
            "
          >
            {item}
          </button>
        ))}

      </div>

    </div>
  );
}
