"""Fresh-topic pipeline regression tests.

A deterministic (no-LLM) fresh-topic build must produce a plan that passes the
editorial quality gate: readable text, no montage stalls, structured chapters.
The GPS pack below stands in for a real 79KB research pack — its sentences are
realistic journalistic lengths, including long ones that used to fail QA.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GPS_SOURCES: list[dict] = [
    {"title": "US Space Force GPS sustainment", "url": "https://www.spaceforce.mil/gps",
     "snippet": "", "text": "The GPS constellation broadcasts precise timing signals from a chain of satellites in medium Earth orbit. Each satellite carries several atomic clocks running on rubidium and cesium standards. The control segment monitors every satellite through a global network of ground antennas."},
    {"title": "GPS satellite overview", "url": "https://www.gps.gov/satellites/",
     "snippet": "", "text": "The current generation of GPS satellites uses signals across several frequency bands to correct atmospheric delay. Engineers have continued launching replacements since the system entered full operational service in 1995. Modern spacecraft weigh roughly two thousand kilograms at launch."},
    {"title": "How GPS timing works", "url": "https://www.navtech.edu/timing",
     "snippet": "", "text": "A navigation receiver estimates its position by measuring how long radio signals take to travel from four or more satellites. A one nanosecond error in the receiver clock translates into roughly thirty centimeters of position error. The satellites themselves carry clocks accurate to several nanoseconds per day."},
    {"title": "Ground segment study", "url": "https://aerospace.org/reports/ground",
     "snippet": "", "text": "Ground control stations monitor the health of every satellite and periodically upload new navigation messages to the constellation. Each station connects to the satellite network over redundant communication links to keep coverage alive. The monitoring sites are positioned around the globe so that every satellite passes over at least two stations each day."},
    {"title": "L-band frequency report", "url": "https://www.ntia.doc.gov/policy/l-band",
     "snippet": "", "text": "GPS relies on radio frequencies in the L-band that are shared with other navigation and timing services. Regulators coordinate frequency assignments through international agreements to prevent harmful interference between systems. The signal is weak by the time it reaches the ground, about one tenth of a typical mobile phone transmission."},
    {"title": "Receiver manufacturing profile", "url": "https://www.congress.gov/crs/gps-receivers",
     "snippet": "", "text": "Modern receivers combine the positioning engine with maps and sensors to estimate where a device is pointing. The majority of global receivers are built into consumer phones rather than dedicated navigation devices. Cellular companies use the same timing source to keep base stations synchronized with one another."},
    {"title": "Aviation dependence", "url": "https://www.faa.gov/gps/aviation",
     "snippet": "", "text": "Airlines use the timing from satellites to sequence arrivals at congested airports without relying on older ground beacons. The aviation community backs up the space signals with ground-based augmentation to reach safety-critical accuracy. Shipping fleets rely on satellite navigation to route vessels through narrow straits and harbors."},
    {"title": "Carrier phase measurement", "url": "https://www.gpsworld.com/carrier-phase",
     "snippet": "", "text": "Surveying receivers measure the carrier wave itself to achieve centimeter-level positioning over short baselines. The technique compares the phase of the received signal against a reference generated inside the receiver. Differential corrections turn ordinary receivers into instruments exact enough to map fault lines."},
    {"title": "Electric grid time distribution", "url": "https://www.nist.gov/sync-holdover",
     "snippet": "", "text": "Power utilities use the satellite time signal to synchronize sampling across distant substations and detect faults within microseconds. Financial networks timestamp transactions against the same atomic reference to keep exchange order consistent. The dependence is so widespread that the engineering community now studies what happens when the signal goes dark."},
    {"title": "Interference report", "url": "https://www.rtklib.cn/jamming",
     "snippet": "", "text": "Because the space signal arrives with very low power, jamming devices only a few watts can overwhelm receivers across an entire urban block. The industry responds with antennas that reject signals arriving from below the horizon. In contested areas pilots still navigate on the assumption that the signal cannot be trusted."},
    {"title": "Constellation replenishment", "url": "https://www.usaspending.gov/gps-replacements",
     "snippet": "", "text": "The United States fields backup satellites on orbit as spares ready to switch on if an active unit degrades. Each replacement launch adds spacecraft that broadcast for two decades or more. Procurement documents describe smaller, faster arrays of satellites planned for the coming years."},
    {"title": "Global adoption metrics", "url": "https://www.rand.org/gps-adoption",
     "snippet": "", "text": "More than four billion receivers were in service worldwide by the end of the previous decade. The positioning service costs nothing to the end user, which is why the engineering world built so much on top of it. Economic studies estimate that losing the signal for just a single month could disrupt shipping, finance, and power distribution at once."},
]

VISUAL_TAGS = {"stat", "geography", "timeline", "company", "person"}


def _research(*, topic: str = "The Hidden Infrastructure Behind GPS") -> dict:
    return {"topic": topic, "sources": [dict(s) for s in GPS_SOURCES]}


def _planned_project(research: dict) -> dict:
    from engine.grounding import extract
    from engine.story import StoryPack, save_project
    from engine.editorial import add_shots
    from engine.transitions import assign_transitions
    from engine.editorial_gate import raise_if_invalid
    from engine.project import Project

    pack = extract(research)
    with tempfile.TemporaryDirectory() as td:
        pack_path = Path(td) / "evidence.json"
        pack_path.write_text(json.dumps(pack), encoding="utf-8")
        project_path = save_project(StoryPack.load(pack_path), Path(td) / "project.json")
        project = Project.load(project_path)
        add_shots(project.beats)
        assign_transitions(project.beats)
        raise_if_invalid(project.beats, fps=project.fps)
        from dataclasses import asdict
        return {"pack": pack, "beats": [asdict(b) for b in project.beats]}


class FreshTopicDeterministicTests(unittest.TestCase):
    def test_editorial_qa_passes_on_fresh_topic(self):
        from engine import editorial_quality
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            project = _planned_project(_research())
            beats_path = td / "beats.json"
            beats_path.write_text(json.dumps({"fps": 30, "beats": project["beats"]}),
                                  encoding="utf-8")
            report = editorial_quality.analyze(beats_path)
            self.assertTrue(report["ok"], msg="\n".join(report["fails"]))

    def test_claims_stay_verbatim_and_bounded(self):
        from engine.grounding import extract
        pack = extract(_research(), max_claim_chars=240)
        materials = {s["url"]: s["text"] + " " + s["snippet"] for s in GPS_SOURCES}
        for item in pack["evidence"]:
            self.assertIn(item["claim"].rstrip(" ,;.") + ("'" if item["claim"].endswith("'") else ""),
                          materials[item["source"]])
            self.assertLessEqual(len(item["claim"]), 240)
            self.assertLessEqual(len(item["claim"]), len(materials[item["source"]]))
            self.assertIn(item["source"], {s["url"] for s in GPS_SOURCES})

    def test_tags_only_from_content_signals(self):
        from engine.grounding import extract
        pack = extract(_research())
        for item in pack["evidence"]:
            self.assertTrue(set(item["tags"]) <= VISUAL_TAGS,
                            msg=f"bad tags {item['tags']} for {item['claim'][:40]}")
        tagged = [item for item in pack["evidence"] if item["tags"]]
        self.assertTrue(tagged, "no evidence carried a content-supported tag")

    def test_claims_grouped_into_sections(self):
        from engine.grounding import extract
        pack = extract(_research(), section_size=4)
        chapters = [item["chapter"] for item in pack["evidence"]]
        self.assertEqual(chapters, [1] * 4 + [2] * 4 + [3] * 4)
        self.assertTrue(all(item["chapter_title"] == f"Part {item['chapter']}"
                            for item in pack["evidence"]))

    def test_long_sentence_clipped_at_clause_boundary(self):
        from engine.grounding import extract
        long_text = ("The synchronized clock in the power grid is the hidden backbone of "
                     "the timing network, and the engineering teams that stabilize the grid "
                     "now hang their timing on satellite signals with nanosecond precision, "
                     "which is why regulators track the timing source in every region year "
                     "after year.")
        research = {"topic": "Power grid timing", "sources": [
            {"title": "x", "url": "https://resilience.test/x", "snippet": "", "text": long_text}]}
        pack = extract(research, max_claim_chars=120)
        claim = pack["evidence"][0]["claim"]
        self.assertLessEqual(len(claim), 120)
        self.assertIn(claim, long_text)
        self.assertIn(claim[-1], ".,;:—–(")

    def test_visual_run_never_reaches_four_same_beats(self):
        from engine.grounding import extract
        from engine.story import StoryPack, build_beats
        pack = extract(_research())
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "e.json"
            pack_path.write_text(json.dumps(pack), encoding="utf-8")
            beats = build_beats(StoryPack.load(pack_path))
        visuals = [b["visual"] for b in beats]
        longest = run = 1
        for i in range(1, len(visuals)):
            run = run + 1 if visuals[i] == visuals[i - 1] else 1
            longest = max(longest, run)
        self.assertLess(longest, 4, msg=f"visual run of {longest}: {list(zip(visuals, range(len(visuals))))}")


if __name__ == "__main__":
    unittest.main()