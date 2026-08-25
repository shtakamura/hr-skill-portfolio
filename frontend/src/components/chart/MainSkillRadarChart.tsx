import { Box } from "@mui/material";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { SkillLevel } from "../../types/skillProfile";

type MainSkillRadarChartProps = {
  skills: SkillLevel[];
};

type RadarData = {
  skillName: string;
  level: number;
  maxLevel: number;
};

const toRadarData = (skills: SkillLevel[]): RadarData[] =>
  skills.map((skill) => ({
    skillName: `${skill.skillName} ${skill.level}`,
    level: skill.level,
    maxLevel: skill.maxLevel,
  }));

export const MainSkillRadarChart = ({ skills }: MainSkillRadarChartProps) => (
  <Box aria-label="選択ポジションのスキルレベルレーダーチャート" sx={{ width: "100%", height: { xs: 320, md: 400 } }}>
    <ResponsiveContainer width="100%" height="100%">
      <RadarChart data={toRadarData(skills)} outerRadius="68%">
        <PolarGrid stroke="#d9dce1" />
        <PolarAngleAxis dataKey="skillName" tick={{ fill: "#d00000", fontSize: 11, fontWeight: 700 }} />
        <PolarRadiusAxis angle={90} domain={[0, 5]} tickCount={6} tick={{ fill: "#777", fontSize: 10 }} />
        <Radar name="レベル" dataKey="level" stroke="#d00000" fill="#d00000" fillOpacity={0.14} strokeWidth={2} />
        <Tooltip />
      </RadarChart>
    </ResponsiveContainer>
  </Box>
);