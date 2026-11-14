import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { SessionProvider } from "./api/session";
import { Console } from "./Console";
import "@fontsource-variable/source-sans-3";
import "@fontsource-variable/source-code-pro";
import "./styles/app.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, refetchOnWindowFocus: false, retry: 1 } },
});

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <SessionProvider>
          <Console />
        </SessionProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
}
