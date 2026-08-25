import { Box, Typography } from "@mui/material";

type PositionListHeaderProps = {
  departmentCount: number;
  positionCount: number;
};

export const PositionListHeader = ({ departmentCount, positionCount }: PositionListHeaderProps) => (
  <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
    <Typography variant="h2">部署別ポジション一覧</Typography>
    <Typography color="text.secondary" sx={{ fontSize: "0.82rem" }}>
      {departmentCount}部署・{positionCount}件
    </Typography>
  </Box>
);