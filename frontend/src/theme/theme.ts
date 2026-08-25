import { createTheme } from "@mui/material/styles";

export const appTheme = createTheme({
  palette: {
    primary: {
      main: "#c90000",
      dark: "#9f0000",
      light: "#ffe9e9",
    },
    background: {
      default: "#f7f7f8",
      paper: "#ffffff",
    },
    text: {
      primary: "#202124",
      secondary: "#666a70",
    },
  },
  typography: {
    fontFamily: ["Noto Sans JP", "Yu Gothic", "Meiryo", "sans-serif"].join(","),
    fontSize: 13,
    h1: {
      fontSize: "1.55rem",
      fontWeight: 800,
      letterSpacing: 0,
    },
    h2: {
      fontSize: "1rem",
      fontWeight: 700,
      letterSpacing: 0,
    },
  },
  shape: {
    borderRadius: 6,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          boxShadow: "none",
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        size: "small",
      },
    },
    MuiSelect: {
      defaultProps: {
        size: "small",
      },
    },
  },
});