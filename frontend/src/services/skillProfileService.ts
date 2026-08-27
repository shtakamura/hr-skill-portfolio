import { mockSimilarPositions, mockSkillLevels } from "../data/skillProfileMockData";
import { getPositionById } from "./positionService";
import type { Position } from "../types/position";
import type { PositionSkillProfile, SimilarPosition } from "../types/skillProfile";

type PositionSkillsApiSkill = {
  skillId: string;
  skillName: string;
  level: number;
};

type PositionSkillsApiResponse = {
  dataFound: boolean;
  positionId: string | null;
  organizationName: string | null;
  positionName: string | null;
  skills: PositionSkillsApiSkill[];
};

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const isValidLevel = (level: unknown): level is number =>
  typeof level === "number" && Number.isInteger(level) && level >= 0 && level <= 5;

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

export const getSimilarPositions = async (_positionId: string): Promise<SimilarPosition[]> =>
  Promise.resolve(mockSimilarPositions);