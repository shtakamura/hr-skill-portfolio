import { Button } from "@mui/material";
import type { Position } from "../../types/position";

type PositionButtonProps = {
  position: Position;
  selected: boolean;
  onSelect: (position: Position) => void;
};

export const PositionButton = ({ position, selected, onSelect }: PositionButtonProps) => (
  <Button
    type="button"
    variant="outlined"
    aria-label={`${position.departmentName} ${position.positionName}を選択`}
    aria-pressed={selected}
    onClick={() => onSelect(position)}
    title={position.positionName}
    sx={{
      minWidth: 0,
      width: "100%",
      height: 28,
      px: 1,
      fontSize: "0.76rem",
      lineHeight: 1.2,
      color: selected ? "primary.main" : "text.primary",
      backgroundColor: selected ? "primary.light" : "background.paper",
      borderColor: selected ? "primary.main" : "#d6d8dc",
      borderWidth: selected ? 2 : 1,
      fontWeight: selected ? 700 : 500,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
      "&:hover": {
        backgroundColor: selected ? "#ffdcdc" : "#f2f3f5",
        borderColor: selected ? "primary.dark" : "#c8ccd2",
        borderWidth: selected ? 2 : 1,
      },
    }}
  >
    {position.positionName}
  </Button>
);