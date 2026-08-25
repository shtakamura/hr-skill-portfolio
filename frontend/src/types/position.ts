export type OrganizationLevel = "company" | "cxo" | "bu" | "department";

export type Position = {
  positionId: string;
  positionName: string;
  departmentName: string;
  businessUnitName: string;
  jobGrade: string;
  jobCategory: string;
  organizationLevel: OrganizationLevel;
};

export type Department = {
  departmentId: string;
  departmentName: string;
  businessUnitName: string;
  positions: Position[];
};

export type PositionSearchCondition = {
  organizationName: string;
  positionName: string;
  jobGrade: string;
  jobCategory: string;
  organizationLevel: string;
  keyword: string;
};