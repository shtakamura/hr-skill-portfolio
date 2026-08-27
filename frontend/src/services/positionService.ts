import { positionMockDepartments } from "../data/positionMockData";
import type { Department, Position } from "../types/position";

type OrganizationApiItem = {
	organizationId: string;
	organizationName: string;
	businessUnitName: string;
};

type PositionApiItem = {
	positionId: string;
	organizationId: string;
	positionName: string;
};

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export const getDepartments = async (): Promise<Department[]> => {
	const organizationResponse = await fetch(`${apiBaseUrl}/organizations`, {
		method: "GET",
		headers: { Accept: "application/json" },
	});
	if (!organizationResponse.ok) {
		throw new Error("Failed to fetch organizations");
	}

	const organizationBody = (await organizationResponse.json()) as { organizations: OrganizationApiItem[] };
	const departments = await Promise.all(
		organizationBody.organizations.map(async (organization) => {
			const positions = await getPositionsByOrganization(organization);
			return {
				departmentId: organization.organizationId,
				organizationId: organization.organizationId,
				departmentName: organization.organizationName,
				businessUnitName: organization.businessUnitName,
				positions,
			};
		}),
	);

	return departments.filter((department) => department.positions.length > 0);
};

export const getMockDepartments = async (): Promise<Department[]> => Promise.resolve(positionMockDepartments);

const getPositionsByOrganization = async (organization: OrganizationApiItem): Promise<Position[]> => {
	const params = new URLSearchParams({ organizationId: organization.organizationId });
	const positionResponse = await fetch(`${apiBaseUrl}/positions?${params.toString()}`, {
		method: "GET",
		headers: { Accept: "application/json" },
	});
	if (!positionResponse.ok) {
		throw new Error("Failed to fetch positions");
	}

	const positionBody = (await positionResponse.json()) as { positions: PositionApiItem[] };
	return positionBody.positions.map((position) => ({
		positionId: position.positionId,
		organizationId: position.organizationId,
		positionName: position.positionName,
		departmentName: organization.organizationName,
		businessUnitName: organization.businessUnitName,
		jobGrade: "",
		jobCategory: "",
		organizationLevel: "department",
	}));
};

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