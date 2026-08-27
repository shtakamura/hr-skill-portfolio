import type { SimilarPosition, SkillLevel } from "../types/skillProfile";

export const mockSkillLevels: SkillLevel[] = [
  { skillId: "strategy", skillName: "戦略立案", level: 3, maxLevel: 5 },
  { skillId: "improvement", skillName: "業務改善", level: 4, maxLevel: 5 },
  { skillId: "communication", skillName: "コミュニケーション・調整", level: 3, maxLevel: 5 },
  { skillId: "analytics", skillName: "データ分析・可視化", level: 4, maxLevel: 5 },
  { skillId: "system", skillName: "システム開発・運用", level: 5, maxLevel: 5 },
  { skillId: "expertise", skillName: "専門知識活用", level: 4, maxLevel: 5 },
];

export const mockSimilarPositions: SimilarPosition[] = Array.from({ length: 20 }, (_, index) => ({
  rank: index + 1,
  positionId: `sample-${index + 1}`,
  positionName: "",
  departmentName: "",
  businessUnitName: "",
  skills: mockSkillLevels,
  similarityScore: 0,
}));