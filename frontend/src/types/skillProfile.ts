export type SkillLevel = {
  skillId: string;
  skillName: string;
  level: number;
  maxLevel: number;
};

export type PositionSkillProfile = {
  positionId: string;
  positionName: string;
  departmentName: string;
  businessUnitName: string;
  skills: SkillLevel[];
};

export type SimilarPosition = {
  rank: number;
  positionId: string | null;
  positionName: string;
  departmentName: string;
  businessUnitName: string;
  skills: SkillLevel[];
};

export type SimilaritySearchResult = {
  selectedPosition: PositionSkillProfile;
  similarPositions: SimilarPosition[];
};