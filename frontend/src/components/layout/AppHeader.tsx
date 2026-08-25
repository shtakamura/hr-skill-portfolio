import { Box, Typography } from "@mui/material";

type AppHeaderProps = {
  visiblePositionCount: number;
};

export const AppHeader = ({ visiblePositionCount }: AppHeaderProps) => (
  <Box component="header" sx={{ backgroundColor: "background.paper", borderBottom: "3px solid #d00000" }}>
    <Box
      sx={{
        maxWidth: 1440,
        mx: "auto",
        px: { xs: 2, md: 4 },
        py: 2,
        display: "flex",
        alignItems: { xs: "flex-start", sm: "center" },
        justifyContent: "space-between",
        gap: 2,
        flexDirection: { xs: "column", sm: "row" },
      }}
    >
      <Box sx={{ display: "flex", alignItems: "baseline", gap: 3 }}>
        <Typography component="h1" variant="h1">
          ポジション一覧
        </Typography>
        <Typography color="text.secondary">全{visiblePositionCount}件を表示中</Typography>
      </Box>
      <Typography color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
        人材ポートフォリオ ＞ ポジション一覧
      </Typography>
    </Box>
  </Box>
);