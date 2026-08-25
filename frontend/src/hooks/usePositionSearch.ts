import { useState } from "react";
import type { Department, Position, PositionSearchCondition } from "../types/position";

const initialCondition: PositionSearchCondition = {
  organizationName: "",
  positionName: "",
  jobGrade: "すべて",
  jobCategory: "すべて",
  organizationLevel: "department",
  keyword: "",
};

const organizationLevelLabels: Record<string, string> = {
  company: "全社",
  cxo: "CXO",
  bu: "BU",
  department: "部",
};

const includesText = (value: string, keyword: string): boolean =>
  value.toLocaleLowerCase("ja-JP").includes(keyword.toLocaleLowerCase("ja-JP"));

const matchesKeyword = (position: Position, keyword: string): boolean => {
  if (!keyword) {
    return true;
  }

  return [
    position.departmentName,
    position.businessUnitName,
    position.positionName,
    position.jobGrade,
    position.jobCategory,
  ].some((value) => includesText(value, keyword));
};

const matchesPosition = (position: Position, condition: PositionSearchCondition): boolean => {
  if (condition.organizationName && !includesText(position.departmentName, condition.organizationName)) {
    return false;
  }
  if (condition.positionName && !includesText(position.positionName, condition.positionName)) {
    return false;
  }
  if (condition.jobGrade !== "すべて" && position.jobGrade !== condition.jobGrade) {
    return false;
  }
  if (condition.jobCategory !== "すべて" && position.jobCategory !== condition.jobCategory) {
    return false;
  }
  if (condition.organizationLevel && position.organizationLevel !== condition.organizationLevel) {
    return false;
  }
  return matchesKeyword(position, condition.keyword);
};

const buildFilteredDepartments = (
  departments: Department[],
  condition: PositionSearchCondition,
): Department[] =>
  departments
    .map((department) => ({
      ...department,
      positions: department.positions.filter((position) => matchesPosition(position, condition)),
    }))
    .filter((department) => department.positions.length > 0);

export const usePositionSearch = (departments: Department[]) => {
  const [inputCondition, setInputCondition] = useState<PositionSearchCondition>(initialCondition);
  const [appliedCondition, setAppliedCondition] = useState<PositionSearchCondition>(initialCondition);

  const filteredDepartments = buildFilteredDepartments(departments, appliedCondition);
  const visiblePositionCount = filteredDepartments.reduce(
    (total, department) => total + department.positions.length,
    0,
  );
  const totalPositionCount = departments.reduce((total, department) => total + department.positions.length, 0);

  const setConditionValue = <Field extends keyof PositionSearchCondition>(
    field: Field,
    value: PositionSearchCondition[Field],
  ) => {
    setInputCondition((current) => ({ ...current, [field]: value }));
  };

  const applySearch = () => {
    setAppliedCondition(inputCondition);
  };

  const clearSearch = () => {
    setInputCondition(initialCondition);
    setAppliedCondition(initialCondition);
  };

  return {
    inputCondition,
    appliedCondition,
    filteredDepartments,
    visiblePositionCount,
    totalPositionCount,
    organizationLevelLabels,
    setConditionValue,
    applySearch,
    clearSearch,
  };
};