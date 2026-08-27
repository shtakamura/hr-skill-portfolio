import { mockSkillLevels } from "../data/skillProfileMockData";
import { getPositionById } from "./positionService";
import type { Position } from "../types/position";
import type { PositionSkillProfile, SimilarPosition } from "../types/skillProfile";

type PositionSkillsApiSkill = {
  skillId: string;
  skillName: string;
  level: number;
  category?: string;
  subcategory?: string;
};

type PositionSkillsApiResponse = {
  dataFound: boolean;
  positionId: string | null;
  organizationName: string | null;
  positionName: string | null;
  skills: PositionSkillsApiSkill[];
};

type SimilarPositionApiItem = {
  rank: number;
  positionId: string;
  positionName: string;
  organizationName: string;
  businessUnitName: string;
  coverageScore: number;
  coveredCoreSkillCount: number;
  selectedCoreSkillCount: number;
  chartValues: number[];
};

type SimilarPositionsApiResponse = {
  dataFound: boolean;
  selectedPositionId: string;
  selectedCoreSkillCount: number;
  chartAxis: Array<Pick<PositionSkillsApiSkill, "skillId" | "skillName">>;
  results: SimilarPositionApiItem[];
};

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const isValidLevel = (level: unknown): level is number =>
  typeof level === "number" && Number.isInteger(level) && level >= 0 && level <= 5;

const toCoverageScore = (value: unknown): number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1 ? value : 0;

export const buildPositionSkillsUrl = (position: Position): string => {
  const params = new URLSearchParams({ positionId: position.positionId });
  return `${apiBaseUrl}/position-skills?${params.toString()}`;
};

export const sampleProfileForPosition = (position: Position): PositionSkillProfile => ({
  positionId: position.positionId,
  positionName: position.positionName,
  departmentName: position.departmentName,
  businessUnitName: position.businessUnitName,
  skills: mockSkillLevels,
  dataSource: "sample",
});

export const mapApiResponseToProfile = (
  position: Position,
  response: PositionSkillsApiResponse,
): PositionSkillProfile => {
  const validSkills = response.skills
    .filter((skill) => skill.skillId && skill.skillName && isValidLevel(skill.level) && skill.level > 0)
    .slice(0, 10)
    .map((skill) => ({
      skillId: skill.skillId,
      skillName: skill.skillName,
      level: skill.level,
      maxLevel: 5,
      ...(skill.category ? { category: skill.category } : {}),
      ...(skill.subcategory ? { subcategory: skill.subcategory } : {}),
    }));

  if (!response.dataFound) {
    return sampleProfileForPosition(position);
  }

  return {
    positionId: response.positionId ?? position.positionId,
    positionName: response.positionName ?? position.positionName,
    departmentName: response.organizationName ?? position.departmentName,
    businessUnitName: position.businessUnitName,
    skills: validSkills,
    dataSource: "api",
  };
};

export const getPositionSkillProfile = async (position: Position): Promise<PositionSkillProfile> => {
  const response = await fetch(buildPositionSkillsUrl(position), {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error("Failed to fetch position skill profile");
  }

  const body = (await response.json()) as PositionSkillsApiResponse;
  return mapApiResponseToProfile(position, body);
};

export const getFallbackPositionSkillProfile = async (positionId: string): Promise<PositionSkillProfile> => {
  const position = await getPositionById(positionId);
  if (!position) {
    throw new Error("Position not found");
  }

  return {
    positionId: position.positionId,
    positionName: position.positionName,
    departmentName: position.departmentName,
    businessUnitName: position.businessUnitName,
    skills: mockSkillLevels,
    dataSource: "sample",
  };
};

export const buildSimilarPositionsUrl = (positionId: string): string => {
  const params = new URLSearchParams({ positionId });
  return `${apiBaseUrl}/similar-positions?${params.toString()}`;
};

export const mapSimilarPositionsResponse = (response: SimilarPositionsApiResponse): SimilarPosition[] => {
  if (!response.dataFound) {
    return [];
  }
  return response.results.slice(0, 9).map((position) => ({
    rank: position.rank,
    positionId: position.positionId,
    positionName: position.positionName,
    departmentName: position.organizationName,
    businessUnitName: position.businessUnitName,
    skills: response.chartAxis.slice(0, 10).map((axis, index) => {
      const level = position.chartValues[index] ?? 0;
      return {
        skillId: axis.skillId,
        skillName: axis.skillName,
        level: isValidLevel(level) ? level : 0,
        maxLevel: 5,
      };
    }),
    coverageScore: toCoverageScore(position.coverageScore),
    coveredCoreSkillCount: Number.isInteger(position.coveredCoreSkillCount) && position.coveredCoreSkillCount >= 0 ? position.coveredCoreSkillCount : 0,
    selectedCoreSkillCount: Number.isInteger(position.selectedCoreSkillCount) && position.selectedCoreSkillCount >= 0 ? position.selectedCoreSkillCount : response.selectedCoreSkillCount,
  }));
};

export const getSimilarPositions = async (positionId: string): Promise<SimilarPosition[]> => {
  const response = await fetch(buildSimilarPositionsUrl(positionId), {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error("Failed to fetch similar positions");
  }

  const body = (await response.json()) as SimilarPositionsApiResponse;
  return mapSimilarPositionsResponse(body);
};