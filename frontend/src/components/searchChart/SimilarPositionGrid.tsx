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
      <Typography variant="h2">ポジションカバー度自動判定</Typography>
      <Typography color="text.secondary" sx={{ fontSize: "0.82rem" }}>
        カバー度の高い順 上位9件
      </Typography>
    </Box>
    <Box
      role="listbox"
      aria-label="カバー度の高いポジション候補"
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", xl: "repeat(3, minmax(0, 1fr))" },
        gap: 1.25,
      }}
    >
      {positions.length > 0 ? (
        positions.map((position) => (
          <SimilarPositionCard
            key={position.positionId}
            position={position}
            selected={selectedRank === position.rank}
            onSelect={onSelectRank}
          />
        ))
      ) : (
        <Typography color="text.secondary" sx={{ gridColumn: "1 / -1", py: 4, textAlign: "center", fontWeight: 700 }}>
          カバー度を表示できる評価済みデータがありません
        </Typography>
      )}
    </Box>
  </Box>
);