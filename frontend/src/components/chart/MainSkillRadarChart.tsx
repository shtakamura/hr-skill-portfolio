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
  displayName: string;
  level: number;
  maxLevel: number;
};

const formatAxisLabel = (value: string): string => (value.length > 12 ? `${value.slice(0, 11)}…` : value);

const toRadarData = (skills: SkillLevel[]): RadarData[] =>
  skills.map((skill) => ({
    skillName: skill.skillName,
    displayName: `${skill.skillName}: ${skill.level}`,
    level: skill.level,
    maxLevel: skill.maxLevel,
  }));

export const MainSkillRadarChart = ({ skills }: MainSkillRadarChartProps) => (
  <Box aria-label="選択ポジションのスキルレベルレーダーチャート" sx={{ width: "100%", height: { xs: 340, md: 420 } }}>
    <ResponsiveContainer width="100%" height="100%">
      <RadarChart data={toRadarData(skills)} outerRadius="62%" margin={{ top: 24, right: 36, bottom: 24, left: 36 }}>
        <PolarGrid stroke="#d9dce1" />
        <PolarAngleAxis dataKey="skillName" tickFormatter={formatAxisLabel} tick={{ fill: "#d00000", fontSize: 10, fontWeight: 700 }} />
        <PolarRadiusAxis angle={90} domain={[0, 5]} tickCount={6} tick={{ fill: "#777", fontSize: 10 }} />
        <Radar name="レベル" dataKey="level" stroke="#d00000" fill="#d00000" fillOpacity={0.14} strokeWidth={2} />
        <Tooltip labelFormatter={(_, payload) => payload?.[0]?.payload?.displayName ?? ""} />
      </RadarChart>
    </ResponsiveContainer>
  </Box>
);