import { positionMockDepartments } from "../data/positionMockData";
import type { Department, Position } from "../types/position";

export const getDepartments = async (): Promise<Department[]> => Promise.resolve(positionMockDepartments);

export const getPositionById = async (positionId: string): Promise<Position | undefined> => {
	const departments = await getDepartments();
	for (const department of departments) {
		const position = department.positions.find((candidate) => candidate.positionId === positionId);
		if (position) {
			return position;
		}
	}
	return undefined;
};