import { Box, Typography } from "@mui/material";

export const SearchChartFooter = () => (
  <Box
    sx={{
      mt: 2,
      display: "flex",
      justifyContent: "space-between",
      gap: 2,
      flexDirection: { xs: "column", md: "row" },
    }}
  >
    <Typography color="text.secondary" sx={{ fontSize: "0.82rem" }}>
      ※ 主な職務・必要知識・スキル・タスク内容から各スキルレベルを推定し、ポジション間の類似性を判定します。
    </Typography>
    <Typography color="primary" sx={{ fontSize: "0.82rem", fontWeight: 700 }}>
      ポジションを選択すると詳細画面へ遷移
    </Typography>
  </Box>
);