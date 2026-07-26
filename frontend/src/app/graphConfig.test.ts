import { describe, expect, it } from "vitest";
import { buildPersonGraph } from "./graphConfig";
import type { PersonDetail } from "../lib/graphApi";

/** A victim who is named on two cases — one with a crime_no (FIR), one without. */
function samplePerson(): PersonDetail {
  return {
    role: "victim",
    record_id: "99",
    name: "Asha",
    age: 30,
    gender: "F",
    district_id: "44",
    district_name: "Bengaluru City",
    case_count: 2,
    cases: [
      {
        case_id: "7231",
        crime_no: "123/2024",
        subhead_name: "Theft",
        district_name: "Bengaluru City",
        registered_date: null,
        status: null,
      },
      {
        case_id: "8100",
        crime_no: null,
        subhead_name: "Assault",
        district_name: "Mysuru",
        registered_date: null,
        status: null,
      },
    ],
  };
}

describe("buildPersonGraph — case node labels (Issue 1)", () => {
  it("labels every case node by case number, never the FIR crime_no", () => {
    const { nodes } = buildPersonGraph(samplePerson());

    // The case WITH a crime_no must still read as its case number, matching
    // every other CASE node the backend engine labels "Case {CaseMasterID}".
    expect(nodes.get("CASE:7231")?.label).toBe("Case 7231");
    // The case WITHOUT a crime_no must not fall through to the crime type name.
    expect(nodes.get("CASE:8100")?.label).toBe("Case 8100");
  });

  it("never uses the FIR number or crime subhead as a case node label", () => {
    const { nodes } = buildPersonGraph(samplePerson());
    const labels = [...nodes.values()]
      .filter((n) => n.node_type === "CASE")
      .map((n) => n.label);
    expect(labels).not.toContain("123/2024"); // FIR crime_no
    expect(labels).not.toContain("Theft"); // subhead_name
    expect(labels).not.toContain("Assault");
  });

  it("centers the graph on the person and links one edge per case", () => {
    const { nodes, edges, centerId } = buildPersonGraph(samplePerson());
    expect(centerId).toBe("VICTIM_RECORD:99");
    expect(nodes.get(centerId)?.label).toBe("Asha");
    expect(edges.size).toBe(2);
  });
});
