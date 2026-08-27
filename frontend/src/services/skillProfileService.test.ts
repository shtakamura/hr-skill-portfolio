import { afterEach, describe, expect, it, vi } from "vitest";
import { mockSkillLevels } from "../data/skillProfileMockData";
import type { Position } from "../types/position";
import {
  buildSimilarPositionsUrl,
  buildPositionSkillsUrl,
  getSimilarPositions,
  getPositionSkillProfile,
  mapSimilarPositionsResponse,
  mapApiResponseToProfile,
  sampleProfileForPosition,
} from "./skillProfileService";

const position: Position = {
  positionId: "P002-03",
  organizationId: "ORG001",
  positionName: "スペシャリスト",
  departmentName: "システム開発部",
  businessUnitName: "CTO・テクノロジーBU",
  jobGrade: "主任",
  jobCategory: "スペシャリスト",
  organizationLevel: "department",
};

const apiPosition: Position = {
  ...position,
  positionId: "POS00005648",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("skillProfileService", () => {
  it("always queries position skills by positionId", () => {
    expect(buildPositionSkillsUrl(apiPosition)).toBe("/position-skills?positionId=POS00005648");
    expect(buildPositionSkillsUrl(position)).toBe("/position-skills?positionId=P002-03");
  });

  it("queries similar positions by positionId", () => {
    expect(buildSimilarPositionsUrl("POS00005648")).toBe("/similar-positions?positionId=POS00005648");
  });

  it("maps API data to radar chart skills without changing Japanese names", () => {
    const profile = mapApiResponseToProfile(position, {
      dataFound: true,
      positionId: "POS00005648",
      organizationName: "システム開発部",
      positionName: "スペシャリスト（システム開発部）",
      skills: [
        { skillId: "s1", skillName: "業務改善・最適化", level: 5 },
        { skillId: "s2", skillName: "データ分析", level: 4 },
      ],
    });

    expect(profile.dataSource).toBe("api");
    expect(profile.positionId).toBe("POS00005648");
    expect(profile.skills).toEqual([
      { skillId: "s1", skillName: "業務改善・最適化", level: 5, maxLevel: 5 },
      { skillId: "s2", skillName: "データ分析", level: 4, maxLevel: 5 },
    ]);
  });

  it("keeps only top 10 API skills and excludes invalid levels", () => {
    const skills = Array.from({ length: 12 }, (_, index) => ({
      skillId: `s${index}`,
      skillName: `スキル${index}`,
      level: index % 6,
    }));
    const profile = mapApiResponseToProfile(position, {
      dataFound: true,
      positionId: "POS00005648",
      organizationName: "システム開発部",
      positionName: "スペシャリスト",
      skills: [...skills, { skillId: "bad", skillName: "不正", level: 9 }],
    });

    expect(profile.dataSource).toBe("api");
    expect(profile.skills).toHaveLength(10);
    expect(profile.skills.every((skill) => skill.level >= 0 && skill.level <= 5)).toBe(true);
  });

  it("falls back to sample data when API returns dataFound false", () => {
    const profile = mapApiResponseToProfile(position, {
      dataFound: false,
      positionId: null,
      organizationName: "システム開発部",
      positionName: "スペシャリスト",
      skills: [],
    });

    expect(profile).toEqual(sampleProfileForPosition(position));
    expect(profile.skills).toEqual(mockSkillLevels);
  });

  it("does not fall back when API data exists but no positive skill levels are returned", () => {
    const profile = mapApiResponseToProfile(position, {
      dataFound: true,
      positionId: "POS00005648",
      organizationName: "システム開発部",
      positionName: "スペシャリスト",
      skills: [{ skillId: "s1", skillName: "不要スキル", level: 0 }],
    });

    expect(profile.dataSource).toBe("api");
    expect(profile.skills).toEqual([]);
  });

  it("does not hide API errors with sample data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500 }),
    );

    await expect(getPositionSkillProfile(position)).rejects.toThrow("Failed to fetch position skill profile");
  });

  it("loads API data with fetch", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        dataFound: true,
        positionId: "POS00005648",
        organizationName: "システム開発部",
        positionName: "スペシャリスト",
        skills: [{ skillId: "s1", skillName: "データ分析", level: 4 }],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const profile = await getPositionSkillProfile(position);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(profile.dataSource).toBe("api");
    expect(profile.skills).toEqual([{ skillId: "s1", skillName: "データ分析", level: 4, maxLevel: 5 }]);
  });

  it("maps similar position rankings for the right side cards", () => {
    const positions = mapSimilarPositionsResponse({
      dataFound: true,
      selectedPositionId: "POS00005648",
      results: [
        { rank: 1, positionId: "POS00000001", positionName: "営業第一部マネージャー", similarityScore: 0.81 },
        { rank: 2, positionId: "POS00000002", positionName: "営業企画マネージャー", similarityScore: 0.74 },
      ],
    });

    expect(positions).toEqual([
      {
        rank: 1,
        positionId: "POS00000001",
        positionName: "営業第一部マネージャー",
        departmentName: "",
        businessUnitName: "",
        skills: [],
        similarityScore: 0.81,
      },
      {
        rank: 2,
        positionId: "POS00000002",
        positionName: "営業企画マネージャー",
        departmentName: "",
        businessUnitName: "",
        skills: [],
        similarityScore: 0.74,
      },
    ]);
  });

  it("returns no similar positions when API has no evaluated data", () => {
    expect(mapSimilarPositionsResponse({ dataFound: false, selectedPositionId: "POS", results: [] })).toEqual([]);
  });

  it("does not hide similar-position API errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));

    await expect(getSimilarPositions("POS00005648")).rejects.toThrow("Failed to fetch similar positions");
  });
});