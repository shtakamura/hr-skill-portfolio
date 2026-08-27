import { Box, Paper, Typography } from "@mui/material";
import type { SimilarPosition } from "../../types/skillProfile";

type SimilarPositionCardProps = {
  position: SimilarPosition;
  selected: boolean;
  onSelect: (rank: number) => void;
};

export const SimilarPositionCard = ({ position, selected, onSelect }: SimilarPositionCardProps) => {
  const similarityPercent = Math.round(position.similarityScore * 100);
  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(position.rank);
    }
  };

  return (
    <Paper
      variant="outlined"
      role="option"
      aria-selected={selected}
      tabIndex={0}
      onClick={() => onSelect(position.rank)}
      onKeyDown={handleKeyDown}
      sx={{
        position: "relative",
        minHeight: 116,
        p: 1.25,
        borderRadius: 1,
        borderColor: selected ? "#d00000" : "#d8dadd",
        borderWidth: selected ? 2 : 1,
        backgroundColor: selected ? "#fff4f4" : "background.paper",
        cursor: "pointer",
        outline: "none",
        "&:focus-visible": { boxShadow: "0 0 0 3px rgba(208, 0, 0, 0.22)" },
      }}
    >
      <Box
        sx={{
          position: "absolute",
          top: 8,
          left: 8,
          minWidth: 28,
          height: 18,
          px: 0.75,
          borderRadius: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: selected ? "#d00000" : "#777",
          color: "#fff",
          fontSize: "0.7rem",
          fontWeight: 800,
        }}
      >
        {position.rank}
      </Box>
      <Box sx={{ display: "grid", gridTemplateColumns: "92px 1fr", gap: 1, alignItems: "center", pt: 1.25 }}>
        <Box sx={{ minHeight: 72, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Typography sx={{ color: selected ? "#d00000" : "text.secondary", fontSize: "1.2rem", fontWeight: 800 }}>
            {similarityPercent}%
          </Typography>
        </Box>
        <Box sx={{ minHeight: 72, display: "grid", alignContent: "center", gap: 0.5 }}>
          <Typography sx={{ fontSize: "0.78rem", fontWeight: 800, lineHeight: 1.4 }}>
            {position.positionName || "未評価ポジション"}
          </Typography>
          <Typography color="text.secondary" sx={{ fontSize: "0.72rem", fontWeight: 700 }}>
            類似度: {similarityPercent}%
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
};