import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { Box, Button, Typography } from "@mui/material";
import type { PositionSkillProfile } from "../../types/skillProfile";

type SearchChartHeaderProps = {
  selectedPosition: PositionSkillProfile | undefined;
  onBack: () => void;
};

export const SearchChartHeader = ({ selectedPosition, onBack }: SearchChartHeaderProps) => (
  <Box component="header" sx={{ backgroundColor: "background.paper", borderBottom: "3px solid #d00000" }}>
    <Box
      sx={{
        maxWidth: 1600,
        mx: "auto",
        px: { xs: 2, md: 4 },
        py: 1.5,
        display: "flex",
        alignItems: { xs: "flex-start", md: "center" },
        justifyContent: "space-between",
        gap: 2,
        flexDirection: { xs: "column", md: "row" },
      }}
    >
      <Typography component="h1" variant="h1" sx={{ fontSize: "1.25rem" }}>
        人材サーチャート
      </Typography>
      <Typography sx={{ fontWeight: 700 }}>
        {selectedPosition
          ? `選択ポジション：${selectedPosition.positionName}（${selectedPosition.departmentName}）`
          : "選択ポジション："}
      </Typography>
      <Button variant="outlined" color="inherit" startIcon={<ArrowBackIcon />} aria-label="前画面に戻る" onClick={onBack}>
        前画面に戻る
      </Button>
    </Box>
  </Box>
);