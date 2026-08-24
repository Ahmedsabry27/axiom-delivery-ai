import { Button } from "@/components/ui/button";
import { login } from "@/services/auth";
import { productConfig } from "@/config/product";

export default function LoginPage() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="rounded-xl border p-10 shadow-lg text-center">
        <h1 className="text-3xl font-bold">
          {productConfig.name}
        </h1>

        <p className="mt-4 text-muted-foreground">
          {productConfig.tagline}
        </p>
        <p className="mt-2 text-sm text-muted-foreground">Turn fragmented delivery data into evidence-backed decisions.</p>

        <Button
          className="mt-8"
          onClick={login}
        >
          Sign in
        </Button>
      </div>
    </div>
  );
}
