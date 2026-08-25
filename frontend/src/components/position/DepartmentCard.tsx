import { Box, Paper, Typography } from "@mui/material";
import { PositionButton } from "./PositionButton";
import type { Department, Position } from "../../types/position";

type DepartmentCardProps = {
  department: Department;
  selectedPositionId: string;
  onSelectPosition: (position: Position) => void;
};

export const DepartmentCard = ({ department, selectedPositionId, onSelectPosition }: DepartmentCardProps) => (
  <Paper
    variant="outlined"
    sx={{
      p: 1,
      borderColor: "#d8dadd",
      borderRadius: 0,
      backgroundColor: "background.paper",
      minHeight: 126,
    }}
  >
    <Typography variant="h2" sx={{ mb: 0.25, fontSize: "0.86rem" }}>
      {department.departmentName}（{department.positions.length}）
    </Typography>
    <Typography color="text.secondary" sx={{ mb: 1, fontSize: "0.68rem" }}>
      {department.businessUnitName}
    </Typography>
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "repeat(auto-fit, minmax(128px, 1fr))", sm: "repeat(2, minmax(0, 1fr))" },
        gap: 0.75,
      }}
    >
      {department.positions.map((position) => (
        <PositionButton
          key={position.positionId}
          position={position}
          selected={selectedPositionId === position.positionId}
          onSelect={onSelectPosition}
        />
      ))}
    </Box>
  </Paper>
);