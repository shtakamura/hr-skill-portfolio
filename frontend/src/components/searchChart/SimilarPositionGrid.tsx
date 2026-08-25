import { Box, Typography } from "@mui/material";
import { SimilarPositionCard } from "./SimilarPositionCard";
import type { SimilarPosition } from "../../types/skillProfile";

type SimilarPositionGridProps = {
  positions: SimilarPosition[];
  selectedRank: number;
  onSelectRank: (rank: number) => void;
};

export const SimilarPositionGrid = ({ positions, selectedRank, onSelectRank }: SimilarPositionGridProps) => (
  <Box>
    <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 2, mb: 1.25 }}>
      <Typography variant="h2">類似ポジション自動判定</Typography>
      <Typography color="text.secondary" sx={{ fontSize: "0.82rem" }}>
        類似度の高い順 上位20件
      </Typography>
    </Box>
    <Box
      role="listbox"
      aria-label="類似ポジション候補"
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", xl: "repeat(4, minmax(0, 1fr))" },
        gap: 1,
      }}
    >
      {positions.map((position) => (
        <SimilarPositionCard
          key={position.rank}
          position={position}
          selected={selectedRank === position.rank}
          onSelect={onSelectRank}
        />
      ))}
    </Box>
  </Box>
);