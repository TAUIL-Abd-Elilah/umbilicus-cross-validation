"""Tests for the Khartes operator-project generator.

The generator writes editor scaffolding a human then draws in, so the things
worth pinning are the ones a silent mistake would corrupt: the CT stream a
curve is drawn against, the fact that no automatic control is active in the
output fragment, the [x, z, y] view ordering Khartes uses, and the refusal to
clobber a project that may hold unexported work.
"""

import json
import pathlib

import pytest

import make_operator_project as mop
from scrolls import SCROLLS


@pytest.fixture
def seeds(tmp_path):
    d = tmp_path / "seeds"
    d.mkdir()
    for kind, base in (("seed", 100), ("estimated", 200)):
        pts = [
            {"x": base + i, "y": base + 2 * i, "z": 1000 + 500 * i, "score": 50}
            for i in range(4)
        ]
        (d / f"PHerc0191_umbilicus_{kind}.json").write_text(
            json.dumps({"control_points": pts}), encoding="utf8"
        )
    return d


def build(tmp_path, seeds, **kw):
    out = tmp_path / "projects"
    out.mkdir(exist_ok=True)
    return mop.build("PHerc0191", out, seeds, **kw)


def test_stream_url_matches_scrolls_table():
    url = mop.stream_url("PHerc0191")
    assert url.endswith(f"PHerc0191/volumes/{SCROLLS['PHerc0191']['ct']}")
    assert url.startswith("https://vesuvius-challenge-open-data.s3.amazonaws.com/")


def test_draw_project_layout_and_stream(tmp_path, seeds):
    path = build(tmp_path, seeds)
    assert path.name == "PHerc0191-manual.khprj"

    project = json.loads((path / "project.json").read_text(encoding="utf8"))
    assert project["name"] == "PHerc0191-manual"
    assert project["voxel_size_um"] == SCROLLS["PHerc0191"]["um"]
    assert project["version"] == 1.0

    volzarr = json.loads(
        (path / "volumes" / "PHerc0191.volzarr").read_text(encoding="utf8")
    )
    assert volzarr["zarr_dir"] == mop.stream_url("PHerc0191")
    assert volzarr["khartes_from_vc_render"] is False


def test_output_fragment_is_blank_and_guides_are_off(tmp_path, seeds):
    path = build(tmp_path, seeds)
    frags = {
        f["name"]: f
        for f in json.loads((path / "fragments" / "all.json").read_text(encoding="utf8"))
    }
    assert set(frags) == {
        "PHerc0191_guide_seed",
        "PHerc0191_guide_estimated",
        "PHerc0191_manual",
    }

    # The publishable curve is drawn from blank; neither automatic guide may
    # supply its controls.
    out = frags["PHerc0191_manual"]
    assert out["gpoints"] == [] and out["manual_points"] == []
    assert all(f["type"] == "U" for f in frags.values())

    views = json.loads((path / "views.json").read_text(encoding="utf8"))["fragments"]
    assert views["PHerc0191_manual"] == {
        "visible": True,
        "active": True,
        "mesh_visible": True,
    }
    for kind in ("seed", "estimated"):
        assert views[f"PHerc0191_guide_{kind}"]["active"] is False
        assert views[f"PHerc0191_guide_{kind}"]["visible"] is False


def test_guides_carry_canonical_controls_sorted_by_z(tmp_path, seeds):
    path = build(tmp_path, seeds)
    frags = {
        f["name"]: f
        for f in json.loads((path / "fragments" / "all.json").read_text(encoding="utf8"))
    }
    seed = frags["PHerc0191_guide_seed"]
    assert seed["gpoints"] == seed["manual_points"]
    assert seed["gpoints"][0] == [100.0, 100.0, 1000.0]
    assert [p[2] for p in seed["gpoints"]] == sorted(p[2] for p in seed["gpoints"])


def test_view_is_parked_on_first_control_in_xzy_order(tmp_path, seeds):
    path = build(tmp_path, seeds)
    views = json.loads((path / "views.json").read_text(encoding="utf8"))
    vol = views["volumes"]["PHerc0191"]
    assert vol["direction"] == 1
    # Khartes stores the transposed cursor as [x, z, y]; the estimate guide is
    # the anchor, so this is its lowest-z control.
    assert vol["ijktf"] == [200.0, 1000.0, 200.0]
    assert views["project"]["cur_volume"] == "PHerc0191"


def test_refuses_to_overwrite_without_force(tmp_path, seeds):
    build(tmp_path, seeds)
    with pytest.raises(SystemExit):
        build(tmp_path, seeds)
    path = build(tmp_path, seeds, force=True)
    assert path.is_dir()


def test_unknown_scroll_is_rejected(tmp_path, seeds):
    out = tmp_path / "projects"
    out.mkdir()
    with pytest.raises(SystemExit):
        mop.build("PHerc9999", out, seeds)


def test_missing_guide_is_rejected(tmp_path, seeds):
    (seeds / "PHerc0191_umbilicus_estimated.json").unlink()
    with pytest.raises(SystemExit):
        build(tmp_path, seeds)


def test_roundtrip_project_holds_only_the_candidate_inactive(tmp_path, seeds):
    cand = tmp_path / "PHerc0191_umbilicus.candidate.json"
    cand.write_text(
        json.dumps(
            {
                "control_points": [
                    {"x": 11, "y": 22, "z": 3000, "score": 100},
                    {"x": 33, "y": 44, "z": 1500, "score": 100},
                ]
            }
        ),
        encoding="utf8",
    )
    path = build(tmp_path, seeds, candidate=cand)
    assert path.name == "PHerc0191-roundtrip.khprj"

    frags = json.loads((path / "fragments" / "all.json").read_text(encoding="utf8"))
    assert [f["name"] for f in frags] == ["PHerc0191_candidate"]
    # Sorted by z, so the QC view opens on the true start of the curve.
    assert frags[0]["manual_points"] == [[33.0, 44.0, 1500.0], [11.0, 22.0, 3000.0]]

    views = json.loads((path / "views.json").read_text(encoding="utf8"))
    assert views["fragments"]["PHerc0191_candidate"]["active"] is False
    assert views["volumes"]["PHerc0191"]["ijktf"] == [33.0, 1500.0, 44.0]


def test_empty_candidate_is_rejected(tmp_path, seeds):
    cand = tmp_path / "empty.json"
    cand.write_text(json.dumps({"control_points": []}), encoding="utf8")
    with pytest.raises(ValueError):
        build(tmp_path, seeds, candidate=cand)


def test_timestamp_shape_matches_khartes(tmp_path):
    ts = mop.timestamp()
    assert ts.endswith("Z") and "T" in ts
    date, rest = ts.split("T")
    assert len(date.split("-")) == 3
    assert len(rest.rstrip("Z").split(".")[1]) == 2


def test_cli_writes_project(tmp_path, seeds, capsys):
    out = tmp_path / "cli"
    rc = mop.main(
        ["PHerc0191", "--out", str(out), "--seeds", str(seeds)]
    )
    assert rc == 0
    assert (out / "PHerc0191-manual.khprj" / "project.json").is_file()
    assert "PHerc0191_umbilicus.candidate.json" in capsys.readouterr().out


def test_every_queued_scroll_can_be_built(tmp_path):
    """The nine remaining scrolls all have both guides on disk."""
    real_seeds = pathlib.Path(__file__).resolve().parent / "seeds"
    out = tmp_path / "all"
    out.mkdir()
    queue = [
        "PHerc0191",
        "PHerc0257",
        "PHerc0268",
        "PHerc0358",
        "PHerc0800",
        "PHerc0813",
        "PHerc1218",
        "PHerc1447",
        "PHerc1545",
    ]
    for scroll in queue:
        path = mop.build(scroll, out, real_seeds)
        volzarr = json.loads(
            (path / "volumes" / f"{scroll}.volzarr").read_text(encoding="utf8")
        )
        assert volzarr["zarr_dir"] == mop.stream_url(scroll)
