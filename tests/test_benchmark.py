from ..eval.benchmark import builtin_benchmark_cases, run_benchmark


def test_builtin_benchmark_has_ten_cases():
    cases = builtin_benchmark_cases()
    assert len(cases) == 10
    assert all(case.commit_description for case in cases)


def test_builtin_benchmark_runs_all_cases():
    result = run_benchmark()
    assert result.total == 10
    assert result.passed == result.total
