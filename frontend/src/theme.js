import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    primary: {
      main: "#2563EB",
    },

    background: {
      default: "#F8FAFC",
      paper: "#FFFFFF",
    },
  },

  typography: {
    fontFamily: [
      "Inter",
      "system-ui",
      "-apple-system",
      "BlinkMacSystemFont",
      '"Segoe UI"',
      "Roboto",
      "Helvetica",
      "Arial",
      "sans-serif",
    ].join(","),

    h1: {
      fontSize: "2rem",
      fontWeight: 700,
    },

    h2: {
      fontSize: "1.75rem",
      fontWeight: 700,
    },

    h3: {
      fontSize: "1.5rem",
      fontWeight: 700,
    },

    h4: {
      fontSize: "1.25rem",
      fontWeight: 700,
    },

    body1: {
      fontSize: "15px",
      lineHeight: 1.7,
    },

    body2: {
      fontSize: "14px",
      lineHeight: 1.6,
    },

    button: {
      textTransform: "none",
      fontWeight: 600,
    },
  },

  shape: {
    borderRadius: 14,
  },
});

export default theme;