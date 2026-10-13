import { AppFrame } from "./AppFrame";
import React from "react";
import ReactDOM from "react-dom/client";
import { ThemeProvider } from "@mui/material/styles";
import { CssBaseline } from "@mui/material";

import App from "./App";
import { theme } from "./theme";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppFrame><App /></AppFrame>
    </ThemeProvider>
  </React.StrictMode>
);
