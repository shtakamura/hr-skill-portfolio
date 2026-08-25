import { mockSimilarPositions, mockSkillLevels } from "../data/skillProfileMockData";
import { getPositionById } from "./positionService";
import type { PositionSkillProfile, SimilarPosition } from "../types/skillProfile";

export const getPositionSkillProfile = async (positionId: string): Promise<PositionSkillProfile> => {
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
  };
};

export const getSimilarPositions = async (_positionId: string): Promise<SimilarPosition[]> =>
  Promise.resolve(mockSimilarPositions);