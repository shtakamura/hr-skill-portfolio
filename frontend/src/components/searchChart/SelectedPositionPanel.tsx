import { Box, Paper, Typography } from "@mui/material";
import { MainSkillRadarChart } from "../chart/MainSkillRadarChart";
import type { PositionSkillProfile } from "../../types/skillProfile";

type SelectedPositionPanelProps = {
  profile: PositionSkillProfile;
};

export const SelectedPositionPanel = ({ profile }: SelectedPositionPanelProps) => (
  <Box sx={{ display: "grid", gap: 1.5 }}>
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 0, borderColor: "#d8dadd" }}>
      <Box
        sx={{
          border: "2px solid #d00000",
          color: "#d00000",
          fontWeight: 800,
          textAlign: "center",
          py: 1,
          px: 1.5,
          mb: 1,
          backgroundColor: "#fff4f4",
        }}
      >
        {profile.positionName}（{profile.departmentName}）
      </Box>
      <Typography color="text.secondary" sx={{ textAlign: "center" }}>
        {profile.businessUnitName} ／ {profile.departmentName}
      </Typography>
      <Typography color="text.secondary" sx={{ mt: 0.75, textAlign: "center", fontSize: "0.78rem", fontWeight: 700 }}>
        {profile.dataSource === "api" ? "評価済みスキルデータを表示" : "サンプルデータを表示"}
      </Typography>
    </Paper>
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 0, borderColor: "#d8dadd", overflow: "hidden" }}>
      <MainSkillRadarChart skills={profile.skills} />
    </Paper>
  </Box>
);