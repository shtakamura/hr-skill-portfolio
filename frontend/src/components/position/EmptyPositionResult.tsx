import { Box, Typography } from "@mui/material";

export const EmptyPositionResult = () => (
  <Box
    sx={{
      minHeight: 280,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      border: "1px solid #d8dadd",
      backgroundColor: "background.paper",
    }}
  >
    <Typography color="text.secondary">条件に一致するポジションがありません</Typography>
  </Box>
);