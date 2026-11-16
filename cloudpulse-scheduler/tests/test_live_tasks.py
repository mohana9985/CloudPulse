import pytest

from live.tasks import (
    TASK_FUNCTIONS,
    estimate_seconds,
    generate_live_workload,
    live_workload_fingerprint,
    run_task,
    validate_task,
)


@pytest.mark.parametrize("name", sorted(TASK_FUNCTIONS))
def test_tasks_are_deterministic(name):
    assert run_task(name, 3000) == run_task(name, 3000)
    assert run_task(name, 3000)["checksum"] != run_task(name, 3001)["checksum"] or name == "prime_count"


def test_prime_count_known_value():
    # primes in [1_000_000, 1_000_100): 1000003, 1000033, 1000037, 1000039, 1000081, 1000099
    assert run_task("prime_count", 100)["primes_in_window"] == 6


def test_data_aggregation_counts_all_records():
    out = run_task("data_aggregation", 25_000)  # spans several chunks
    assert out["records"] == 25_000 and out["groups"] == 16


@pytest.mark.parametrize("bad", [("nope", 10), ("prime_count", 0), ("prime_count", 10**9), ("prime_count", 1.5)])
def test_validate_task_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        validate_task(*bad)


def test_estimate_is_linear_in_units():
    assert estimate_seconds("sha256_chain", 200_000) == pytest.approx(2 * estimate_seconds("sha256_chain", 100_000))


def test_live_workload_is_seeded_and_fingerprinted():
    a = generate_live_workload(50, seed=7, total_capacity=2.0)
    b = generate_live_workload(50, seed=7, total_capacity=2.0)
    c = generate_live_workload(50, seed=8, total_capacity=2.0)
    assert a == b and live_workload_fingerprint(a) == live_workload_fingerprint(b)
    assert live_workload_fingerprint(a) != live_workload_fingerprint(c)
    assert [s.offset for s in a] == sorted(s.offset for s in a) and a[0].offset == 0
    assert all(0.05 <= s.estimated_seconds <= 2.6 for s in a)


def test_live_workload_rejects_bad_args():
    with pytest.raises(ValueError):
        generate_live_workload(0, 1, 2.0)
    with pytest.raises(ValueError):
        generate_live_workload(5, 1, 0.0)
