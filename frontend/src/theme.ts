import { createTheme } from "@mui/material/styles";
export const theme = createTheme({
  palette: { mode:"light", primary:{main:"#1d4ed8"}, secondary:{main:"#334155"},
    background:{default:"#f4f6fa",paper:"#ffffff"}, text:{primary:"#172033",secondary:"#526071"} },
  typography: { fontFamily:'"Segoe UI", system-ui, sans-serif',
    h3:{fontSize:"2rem",fontWeight:700,letterSpacing:"-.04em"}, h5:{fontSize:"1.25rem",fontWeight:650},
    button:{textTransform:"none",fontWeight:600} },
  shape:{borderRadius:10},
  components: {
    MuiPaper:{styleOverrides:{root:{backgroundImage:"none",boxShadow:"0 3px 12px rgb(15 23 42 / 4%)",border:"1px solid #d8e0e8"}}},
    MuiButton:{styleOverrides:{root:{minHeight:44,boxShadow:"none"}}},
    MuiTableCell:{styleOverrides:{head:{fontWeight:700,backgroundColor:"#f4f6fa"}}},
    MuiCard:{styleOverrides:{root:{borderRadius:10}}}
  }
});
