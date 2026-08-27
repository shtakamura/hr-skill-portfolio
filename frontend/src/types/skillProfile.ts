export type SkillLevel = {
  skillId: string;
  skillName: string;
  level: number;
  maxLevel: number;
};

export type SkillProfileDataSource = "api" | "sample";

export type PositionSkillProfile = {
  positionId: string;
  positionName: string;
  departmentName: string;
  businessUnitName: string;
  skills: SkillLevel[];
  dataSource: SkillProfileDataSource;
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