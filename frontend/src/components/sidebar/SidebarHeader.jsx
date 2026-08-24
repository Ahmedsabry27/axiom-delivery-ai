import { Bot, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function SidebarHeader({ onNewChat }) {
  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500">
          <Bot className="h-5 w-5 text-white" />
        </div>

        <div>
          <h2 className="font-semibold">Axiom</h2>
          <p className="text-xs text-muted-foreground">
            Copilot
          </p>
        </div>
      </div>

      <Button
        className="w-full justify-start"
        onClick={onNewChat}
      >
        <Plus className="mr-2 h-4 w-4" />
        New Chat
      </Button>
    </div>
  );
}
