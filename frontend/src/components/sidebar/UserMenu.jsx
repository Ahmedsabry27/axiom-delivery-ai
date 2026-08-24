console.log("New UserMenu loaded");
import {
  ChevronUp,
  LogOut,
  Settings,
  User,
  Moon,
  Circle,
} from "lucide-react";

import useAuth from "@/hooks/useAuth";

import { Button } from "@/components/ui/button";

import {
  Avatar,
  AvatarFallback,
  AvatarBadge,
} from "@/components/ui/avatar";

import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";

export default function UserMenu() {
  const { user, logout } = useAuth();

  const initials =
    user?.initials ||
    user?.name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase() ||
    user?.email?.charAt(0).toUpperCase() ||
    "U";

  const displayName =
    user?.name ||
    user?.givenName ||
    user?.username ||
    "User";

  async function handleLogout() {
    try {
      await logout();
    } catch (error) {
      console.error(error);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="
            h-auto
            w-full
            justify-between
            rounded-2xl
            border
            border-transparent
            p-3
            transition-all
            hover:border-border
            hover:bg-accent
            hover:shadow-sm
          "
        >
          <div className="flex items-center gap-3">

            <Avatar size="lg">
              <AvatarFallback className="bg-emerald-600 font-semibold text-white">
                {initials}
              </AvatarFallback>

              <AvatarBadge className="bg-emerald-500 ring-2 ring-background">
                <Circle className="h-2 w-2 fill-current" />
              </AvatarBadge>
            </Avatar>

            <div className="min-w-0 text-left">

              <p className="truncate font-semibold">
                {displayName}
              </p>

              <p className="truncate text-xs text-muted-foreground">
                {user?.email}
              </p>

            </div>

          </div>

          <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        side="top"
        align="start"
        className="w-80 rounded-2xl"
      >
        <DropdownMenuLabel className="p-5">

          <div className="flex items-center gap-4">

            <Avatar size="lg">
              <AvatarFallback className="bg-emerald-600 font-semibold text-white">
                {initials}
              </AvatarFallback>

              <AvatarBadge className="bg-emerald-500 ring-2 ring-background">
                <Circle className="h-2 w-2 fill-current" />
              </AvatarBadge>
            </Avatar>

            <div className="min-w-0">

              <p className="truncate text-base font-semibold">
                {displayName}
              </p>

              <p className="truncate text-sm text-muted-foreground">
                {user?.email}
              </p>

            </div>

          </div>

        </DropdownMenuLabel>

        <DropdownMenuSeparator />

        <DropdownMenuItem className="cursor-pointer">
          <User className="mr-2 h-4 w-4" />
          Profile
        </DropdownMenuItem>

        <DropdownMenuItem className="cursor-pointer">
          <Settings className="mr-2 h-4 w-4" />
          Settings
        </DropdownMenuItem>

        <DropdownMenuItem className="cursor-pointer">
          <Moon className="mr-2 h-4 w-4" />
          Appearance
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuItem
          onClick={handleLogout}
          className="
            cursor-pointer
            text-red-600
            focus:bg-red-50
            focus:text-red-600
            dark:focus:bg-red-950/40
          "
        >
          <LogOut className="mr-2 h-4 w-4" />
          Log out
        </DropdownMenuItem>

      </DropdownMenuContent>
    </DropdownMenu>
  );
}