import { Box, Paper } from "@mui/material";
import { MiniSkillRadarChart } from "../chart/MiniSkillRadarChart";
import type { SimilarPosition } from "../../types/skillProfile";

type SimilarPositionCardProps = {
  position: SimilarPosition;
  selected: boolean;
  onSelect: (rank: number) => void;
};

export const SimilarPositionCard = ({ position, selected, onSelect }: SimilarPositionCardProps) => {
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
        <MiniSkillRadarChart skills={position.skills} />
        <Box sx={{ minHeight: 72 }}>
          <Box sx={{ height: 18, mb: 1 }} />
          <Box sx={{ height: 14, mb: 0.75 }} />
          <Box sx={{ height: 14 }} />
        </Box>
      </Box>
    </Paper>
  );
};