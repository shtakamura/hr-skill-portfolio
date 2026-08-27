import { afterEach, describe, expect, it, vi } from "vitest";
import { getDepartments, getPositionById } from "./positionService";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("positionService", () => {
  it("builds department cards from OrganizationMaster and PositionMaster APIs", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          organizations: [
            {
              organizationId: "ORG001",
              organizationName: "システム開発部",
              businessUnitName: "CTO・テクノロジーBU",
            },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          positions: [
            {
              positionId: "POS00005648",
              organizationId: "ORG001",
              positionName: "スペシャリスト",
            },
          ],
        }),
      });
    vi.stubGlobal("fetch", fetchMock);

    const departments = await getDepartments();

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/organizations", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/positions?organizationId=ORG001", expect.any(Object));
    expect(departments).toEqual([
      {
        departmentId: "ORG001",
        organizationId: "ORG001",
        departmentName: "システム開発部",
        businessUnitName: "CTO・テクノロジーBU",
        positions: [
          {
            positionId: "POS00005648",
            organizationId: "ORG001",
            positionName: "スペシャリスト",
            departmentName: "システム開発部",
            businessUnitName: "CTO・テクノロジーBU",
            jobGrade: "",
            jobCategory: "",
            organizationLevel: "department",
          },
        ],
      },
    ]);
  });

  it("restores a selected position by positionId after reload", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            organizations: [{ organizationId: "ORG001", organizationName: "人事部", businessUnitName: "CHRO・人事BU" }],
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ positions: [{ positionId: "POS00003260", organizationId: "ORG001", positionName: "HRマネージャー" }] }),
        }),
    );

    const position = await getPositionById("POS00003260");

    expect(position?.positionId).toBe("POS00003260");
    expect(position?.organizationId).toBe("ORG001");
  });
});