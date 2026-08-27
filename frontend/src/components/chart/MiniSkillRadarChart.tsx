import { Box } from "@mui/material";
import { PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from "recharts";
import type { SkillLevel } from "../../types/skillProfile";

type MiniSkillRadarChartProps = {
  skills: SkillLevel[];
};

export const MiniSkillRadarChart = ({ skills }: MiniSkillRadarChartProps) => (
  <Box aria-label="類似ポジションのスキルレベルミニレーダーチャート" sx={{ width: 148, height: 136 }}>
    <ResponsiveContainer width="100%" height="100%">
      <RadarChart data={skills} outerRadius="72%" margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
        <PolarGrid stroke="#d6d9de" />
        <PolarRadiusAxis domain={[0, 5]} tick={false} axisLine={false} tickCount={6} />
        <Radar dataKey="level" stroke="#d00000" fill="#d00000" fillOpacity={0.12} strokeWidth={1.4} />
        <Tooltip formatter={(value, _name, item) => [`${value}`, item.payload.skillName]} />
      </RadarChart>
    </ResponsiveContainer>
  </Box>
);