export type SkillLevel = {
  skillId: string;
  skillName: string;
  level: number;
  maxLevel: number;
  category?: string;
  subcategory?: string;
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
  positionId: string;
  positionName: string;
  departmentName: string;
  businessUnitName: string;
  skills: SkillLevel[];
  coverageScore: number;
  coveredCoreSkillCount: number;
  selectedCoreSkillCount: number;
};

export type SimilaritySearchResult = {
  selectedPosition: PositionSkillProfile;
  similarPositions: SimilarPosition[];
};