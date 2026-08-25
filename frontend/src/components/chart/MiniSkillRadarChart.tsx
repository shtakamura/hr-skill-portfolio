import { Box } from "@mui/material";
import { PolarGrid, Radar, RadarChart, ResponsiveContainer } from "recharts";
import type { SkillLevel } from "../../types/skillProfile";

type MiniSkillRadarChartProps = {
  skills: SkillLevel[];
};

export const MiniSkillRadarChart = ({ skills }: MiniSkillRadarChartProps) => (
  <Box aria-label="類似ポジションのスキルレベルミニレーダーチャート" sx={{ width: 88, height: 78 }}>
    <ResponsiveContainer width="100%" height="100%">
      <RadarChart data={skills} outerRadius="72%">
        <PolarGrid stroke="#d6d9de" />
        <Radar dataKey="level" stroke="#777" fill="#777" fillOpacity={0.08} strokeWidth={1.2} />
      </RadarChart>
    </ResponsiveContainer>
  </Box>
);