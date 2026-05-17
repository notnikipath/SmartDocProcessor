import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#0D6E6E",
      contrastText: "#F6F9F8",
    },
    secondary: {
      main: "#DD5D2A",
    },
    background: {
      default: "#F4F7F2",
      paper: "#FFFFFF",
    },
  },
  typography: {
    fontFamily: '"Outfit", "Segoe UI", sans-serif',
    h3: {
      fontFamily: '"Space Grotesk", "Outfit", sans-serif',
      fontWeight: 700,
      letterSpacing: "-0.02em",
    },
    h5: {
      fontFamily: '"Space Grotesk", "Outfit", sans-serif',
      fontWeight: 700,
    },
  },
  shape: {
    borderRadius: 18,
  },
});
