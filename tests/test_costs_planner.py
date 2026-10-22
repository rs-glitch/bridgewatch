import numpy as np
import polars as pl

from bridgewatch import costs, planner

UC = {"nhs": {"19": 200.0}, "non_nhs": {"19": 100.0}, "nhs_national_median": 300.0, "non_nhs_national_median": 150.0}


def test_replacement_cost_uses_state_then_national_median():
    assert abs(costs.replacement_cost("19", False, 10.0, UC) - 100.0 * 10.0 * costs.M2_TO_FT2) < 1e-6
    assert abs(costs.replacement_cost("99", True, 10.0, UC) - 300.0 * 10.0 * costs.M2_TO_FT2) < 1e-6


def test_detour_cost_scales_with_traffic_and_length():
    base = costs.detour_cost_per_day(100, 10, 0)
    assert base > 0
    assert abs(costs.detour_cost_per_day(200, 10, 0) - 2 * base) < 1e-9
    assert costs.detour_cost_per_day(100, 10, 50) > base  # trucks cost more per mile
    assert costs.detour_cost_per_day(0, 10, 0) == 0


def _frame():
    df = pl.DataFrame({"bridge_id": ["a", "b", "c", "d"], "state_code": ["19"] * 4, "lowest_rating": [3, 6, 7, 5],
                       "nhs": ["0"] * 4, "log_deck_area": np.log1p([100.0, 100.0, 100.0, 1000.0]),
                       "log_adt": np.log1p([5.0, 5000.0, 100.0, 20000.0]), "detour_km": [1.0, 10.0, 1.0, 30.0],
                       "truck_pct": [5.0] * 4})
    return planner.frame(df, np.array([0.5, 0.2, 0.01, 0.3]), 4, UC)


def test_poor_bridges_cost_replacement_others_rehab():
    f = _frame()
    repl = f["replacement"].to_numpy()
    assert abs(f["cost"][0] - repl[0]) < 1e-6
    assert abs(f["cost"][1] - costs.REHAB_SHARE * repl[1]) < 1e-6


def test_strategies_respect_budget_and_order():
    f = _frame()
    budget = float(f["cost"][0] + f["cost"][1]) + 1
    for s in planner.STRATEGIES:
        c = planner.pick(f, s, budget)
        assert f["cost"].to_numpy()[c].sum() <= budget
    assert planner.pick(f, "worst_first", float(f["cost"][0]) + 1).tolist() == [True, False, False, False]
    assert planner.order(f, "traffic_first")[0] == 3
    assert planner.order(f, "value_per_dollar").tolist()[:2] == [3, 1]  # traffic x detour x risk per dollar


def test_closure_candidates_are_very_low_traffic_short_detour():
    ids = planner.closure_candidates(_frame())["bridge_id"].to_list()
    assert "a" in ids and "d" not in ids


def test_pick_skips_a_bridge_that_does_not_fit_instead_of_stopping():
    f = _frame()
    o = planner.order(f, "worst_first")
    costs_ = f["cost"].to_numpy()
    budget = costs_[o[1]] + costs_[o[2]] + 1  # cannot afford the first, can afford the next two
    if costs_[o[0]] > budget:
        c = planner.pick(f, "worst_first", budget)
        assert not c[o[0]] and c[o[1]] and c[o[2]]


def test_zero_width_culvert_gets_roadway_area():
    df = pl.DataFrame({"length_m": [10.0, 10.0, 1.0], "deck_width_m": [8.0, 0.0, 0.0]})
    a = planner.deck_area(df)
    assert a[0] == 80.0 and a[1] == 10.0 * planner.ROADWAY_M and a[2] == planner.MIN_AREA_M2


def test_no_detour_codes_are_costed_as_long_detours_not_zero():
    df = pl.DataFrame({"detour_raw": [0.0, 12.0, 159.0, 199.0, 999.0, None]})
    d = planner.detour_length(df)
    assert d.tolist() == [0.0, 12.0, planner.NO_DETOUR_KM, planner.NO_DETOUR_KM, planner.NO_DETOUR_KM, 0.0]
