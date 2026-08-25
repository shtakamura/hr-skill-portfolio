import type { Department, OrganizationLevel, Position } from "../types/position";

type PositionSeed = {
  name: string;
  grade: string;
  category: string;
};

type DepartmentSeed = {
  id: string;
  name: string;
  businessUnit: string;
  positions: PositionSeed[];
};

const organizationLevel: OrganizationLevel = "department";

const positionPatterns: Record<string, PositionSeed[]> = {
  operation: [
    { name: "コーディネーター", grade: "担当", category: "管理" },
    { name: "コンサルタント", grade: "担当", category: "コンサルタント" },
    { name: "ストラテジスト", grade: "主任", category: "企画" },
    { name: "リーダー", grade: "主任", category: "マネジメント" },
    { name: "主任", grade: "主任", category: "管理" },
  ],
  technology: [
    { name: "エキスパート", grade: "課長", category: "スペシャリスト" },
    { name: "オフィサー", grade: "担当", category: "管理" },
    { name: "スペシャリスト", grade: "主任", category: "スペシャリスト" },
    { name: "ディレクター", grade: "ディレクター", category: "マネジメント" },
    { name: "課長", grade: "課長", category: "マネジメント" },
  ],
  planning: [
    { name: "アーキテクト", grade: "課長", category: "企画" },
    { name: "アナリスト", grade: "担当", category: "企画" },
    { name: "シニアスペシャリスト", grade: "主任", category: "スペシャリスト" },
    { name: "プランナー", grade: "担当", category: "企画" },
    { name: "副部長", grade: "副部長", category: "マネジメント" },
  ],
  business: [
    { name: "アドバイザー", grade: "主任", category: "コンサルタント" },
    { name: "エンジニア", grade: "担当", category: "エンジニア" },
    { name: "マネージャー", grade: "マネージャー", category: "マネジメント" },
    { name: "担当", grade: "担当", category: "営業" },
    { name: "部長", grade: "部長", category: "マネジメント" },
  ],
};

const departmentSeeds: DepartmentSeed[] = [
  { id: "customer-support", name: "カスタマーサポート部", businessUnit: "COO・オペレーションBU", positions: positionPatterns.operation },
  { id: "system-development", name: "システム開発部", businessUnit: "CTO・テクノロジーBU", positions: positionPatterns.technology },
  { id: "marketing", name: "マーケティング部", businessUnit: "CMO・マーケティングBU", positions: positionPatterns.planning },
  { id: "sales-first", name: "営業第一部", businessUnit: "COO・オペレーションBU", positions: positionPatterns.operation },
  { id: "sales-second", name: "営業第二部", businessUnit: "COO・オペレーションBU", positions: positionPatterns.business },
  { id: "corporate-planning", name: "経営企画部", businessUnit: "CEO直轄", positions: positionPatterns.business },
  { id: "accounting-finance", name: "経理財務部", businessUnit: "CFO・財務BU", positions: positionPatterns.technology },
  { id: "human-resources", name: "人事部", businessUnit: "CHRO・人事BU", positions: positionPatterns.planning },
  { id: "production-control", name: "生産管理部", businessUnit: "COO・オペレーションBU", positions: positionPatterns.technology },
  { id: "general-affairs", name: "総務部", businessUnit: "CEO直轄", positions: positionPatterns.business },
  { id: "quality-control", name: "品質管理部", businessUnit: "COO・オペレーションBU", positions: positionPatterns.operation },
  { id: "legal-compliance", name: "法務・コンプライアンス部", businessUnit: "CEO直轄", positions: positionPatterns.planning },
];

const createPosition = (department: DepartmentSeed, seed: PositionSeed, departmentIndex: number, positionIndex: number): Position => ({
  positionId: `P${String(departmentIndex + 1).padStart(3, "0")}-${String(positionIndex + 1).padStart(2, "0")}`,
  positionName: seed.name,
  departmentName: department.name,
  businessUnitName: department.businessUnit,
  jobGrade: seed.grade,
  jobCategory: seed.category,
  organizationLevel,
});

export const positionMockDepartments: Department[] = departmentSeeds.map((department) => ({
  departmentId: department.id,
  departmentName: department.name,
  businessUnitName: department.businessUnit,
  positions: department.positions.map((position, positionIndex) =>
    createPosition(department, position, departmentSeeds.indexOf(department), positionIndex),
  ),
}));