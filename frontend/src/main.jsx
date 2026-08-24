import ReactDOM from "react-dom/client";

import "./config/amplify";
import "./index.css";
import "./styles/axiom-legacy-bridge.css";

import { ThemeProvider, CssBaseline } from "@mui/material";
import { TooltipProvider } from "@/components/ui/tooltip";

import "@fontsource/inter";

import App from "./App";
import theme from "./theme";

import QueryProvider from "./providers/QueryProvider";

const rootElement = document.getElementById("root");
rootElement.dataset.buildId = import.meta.env.VITE_BUILD_ID || "local";

ReactDOM.createRoot(
  rootElement
).render(

  <ThemeProvider theme={theme}>

    <CssBaseline />


    <QueryProvider>

      <TooltipProvider>

        <App />

      </TooltipProvider>

    </QueryProvider>


  </ThemeProvider>

);
