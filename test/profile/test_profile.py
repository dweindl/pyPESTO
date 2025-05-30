"""
This is for testing profiling of the pypesto.Objective.
"""

import unittest
import warnings
from copy import deepcopy

import numpy as np
import pytest
from numpy.testing import assert_almost_equal

import pypesto
import pypesto.optimize as optimize
import pypesto.profile as profile
import pypesto.visualize as visualize
from pypesto import ObjectiveBase

from ..util import rosen_for_sensi
from ..visualize import close_fig


class ProfilerTest(unittest.TestCase):
    @classmethod
    def setUp(cls):
        cls.objective: ObjectiveBase = rosen_for_sensi(
            max_sensi_order=2, integrated=True
        )["obj"]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            (
                cls.problem,
                cls.result,
                cls.optimizer,
            ) = create_optimization_results(cls.objective)

    @close_fig
    def test_default_profiling(self):
        # loop over  methods for creating new initial guesses
        method_list = [
            "fixed_step",
            "adaptive_step_order_0",
            "adaptive_step_order_1",
            "adaptive_step_regression",
        ]
        for i_run, method in enumerate(method_list):
            # run profiling
            result = profile.parameter_profile(
                problem=self.problem,
                result=self.result,
                optimizer=self.optimizer,
                next_guess_method=method,
                progress_bar=False,
            )

            # check result
            self.assertTrue(
                isinstance(
                    result.profile_result.list[i_run][0],
                    pypesto.ProfilerResult,
                )
            )
            self.assertEqual(len(result.profile_result.list), i_run + 1)
            self.assertEqual(len(result.profile_result.list[i_run]), 2)

            # check whether profiling needed maybe too many steps
            steps = result.profile_result.list[i_run][0]["ratio_path"].size
            if method == "adaptive_step_regression":
                self.assertTrue(
                    steps < 100,
                    "Profiling with regression based "
                    "proposal needed too many steps.",
                )
                self.assertTrue(
                    steps > 1,
                    "Profiling with regression based "
                    "proposal needed not enough steps.",
                )
            elif method == "adaptive_step_order_1":
                self.assertTrue(
                    steps < 100,
                    "Profiling with 1st order based "
                    "proposal needed too many steps.",
                )
                self.assertTrue(
                    steps > 1,
                    "Profiling with 1st order based "
                    "proposal needed not enough steps.",
                )
            elif method == "adaptive_step_order_0":
                self.assertTrue(
                    steps < 300,
                    "Profiling with 0th order based "
                    "proposal needed too many steps.",
                )
                self.assertTrue(
                    steps > 1,
                    "Profiling with 0th order based "
                    "proposal needed not enough steps.",
                )

            # standard plotting
            visualize.profiles(result, profile_list_ids=i_run)
            visualize.profile_cis(result, profile_list=i_run)

    def test_engine_profiling(self):
        # loop over all possible engines
        # engine=None will be used for comparison
        engines = [
            None,
            pypesto.engine.SingleCoreEngine(),
            pypesto.engine.MultiProcessEngine(),
            pypesto.engine.MultiThreadEngine(),
        ]
        expected_warns = [
            pytest.warns(UserWarning, match="fun and hess as one func"),
            pytest.warns(UserWarning, match="fun and hess as one func"),
            warnings.catch_warnings(),  # No warnings
            warnings.catch_warnings(),  # No warnings
        ]
        for engine, expected_warn in zip(engines, expected_warns):
            # run profiling, profile results get appended
            # in self.result.profile_result
            with expected_warn:
                profile.parameter_profile(
                    problem=self.problem,
                    result=self.result,
                    optimizer=self.optimizer,
                    next_guess_method="fixed_step",
                    engine=engine,
                    progress_bar=False,
                )

        # check results
        for count, _engine in enumerate(engines[1:]):
            for j in range(len(self.result.profile_result.list[0])):
                assert_almost_equal(
                    self.result.profile_result.list[0][j]["x_path"],
                    self.result.profile_result.list[count][j]["x_path"],
                    err_msg="The values of the profiles for"
                    " the different engines do not match",
                )

    def test_selected_profiling(self):
        # create options in order to ensure a short computation time
        options = profile.ProfileOptions(
            default_step_size=0.02,
            min_step_size=0.005,
            max_step_size=1.0,
            step_size_factor=1.5,
            delta_ratio_max=0.2,
            ratio_min=0.3,
            reg_points=5,
            reg_order=2,
        )

        # 1st run of profiling, computing just one out of two profiles
        result = profile.parameter_profile(
            problem=self.problem,
            result=self.result,
            optimizer=self.optimizer,
            profile_index=np.array([1]),
            next_guess_method="fixed_step",
            result_index=1,
            profile_options=options,
            progress_bar=False,
        )

        self.assertIsInstance(
            result.profile_result.list[0][1], pypesto.ProfilerResult
        )
        self.assertIsNone(result.profile_result.list[0][0])

        # 2nd run of profiling, appending to an existing list of profiles
        # using another algorithm and another optimum
        result = profile.parameter_profile(
            problem=self.problem,
            result=result,
            optimizer=self.optimizer,
            profile_index=np.array([0]),
            result_index=2,
            profile_list=0,
            profile_options=options,
            progress_bar=False,
        )

        self.assertIsInstance(
            result.profile_result.list[0][0], pypesto.ProfilerResult
        )

        # 3rd run of profiling, opening a new list, using the default algorithm
        result = profile.parameter_profile(
            problem=self.problem,
            result=result,
            optimizer=self.optimizer,
            next_guess_method="fixed_step",
            profile_index=np.array([0]),
            profile_options=options,
            progress_bar=False,
        )
        # check result
        self.assertIsInstance(
            result.profile_result.list[1][0], pypesto.ProfilerResult
        )
        self.assertIsNone(result.profile_result.list[1][1])

    def test_extending_profiles(self):
        # run profiling
        result = profile.parameter_profile(
            problem=self.problem,
            result=self.result,
            optimizer=self.optimizer,
            next_guess_method="fixed_step",
            progress_bar=False,
        )

        # set new bounds (knowing that one parameter stopped at the bounds
        self.problem.lb_full = -4 * np.ones(2)
        self.problem.ub_full = 4 * np.ones(2)

        # re-run profiling using new bounds
        result = profile.parameter_profile(
            problem=self.problem,
            result=result,
            optimizer=self.optimizer,
            next_guess_method="fixed_step",
            profile_index=np.array([1]),
            profile_list=0,
            progress_bar=False,
        )
        # check result
        self.assertTrue(
            isinstance(
                result.profile_result.list[0][0], pypesto.ProfilerResult
            )
        )
        self.assertTrue(
            isinstance(
                result.profile_result.list[0][1], pypesto.ProfilerResult
            )
        )

    def test_approximate_profiles(self):
        """Test for the approximate profile function."""
        n_steps = 50
        assert self.result.optimize_result.list[0].hess is None
        result = profile.approximate_parameter_profile(
            problem=self.problem,
            result=self.result,
            profile_index=[1],
            n_steps=n_steps,
        )
        profile_list = result.profile_result.list[-1]
        assert profile_list[0] is None
        assert isinstance(profile_list[1], pypesto.ProfilerResult)
        assert np.isclose(profile_list[1].ratio_path.max(), 1)
        assert len(profile_list[1].ratio_path) == n_steps
        assert profile_list[1].x_path.shape == (2, n_steps)

        # with pre-defined hessian
        result = deepcopy(self.result)
        result.optimize_result.list[0].hess = np.array([[2, 0], [0, 1]])
        profile.approximate_parameter_profile(
            problem=self.problem,
            result=result,
            profile_index=[1],
            n_steps=n_steps,
        )


# dont make this a class method such that we dont optimize twice
def test_profile_with_history():
    objective = rosen_for_sensi(max_sensi_order=2, integrated=False)["obj"]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        (problem, result, optimizer) = create_optimization_results(
            objective, dim_full=5
        )

    profile_options = profile.ProfileOptions(
        min_step_size=0.0005,
        delta_ratio_max=0.05,
        default_step_size=0.005,
        ratio_min=0.03,
    )

    problem.fix_parameters(
        [0, 3],
        [
            result.optimize_result.list[0].x[0],
            result.optimize_result.list[0].x[3],
        ],
    )
    problem.objective.history = pypesto.MemoryHistory({"trace_record": True})
    profile.parameter_profile(
        problem=problem,
        result=result,
        optimizer=optimizer,
        profile_index=np.array([0, 2, 4]),
        result_index=0,
        profile_options=profile_options,
        progress_bar=False,
    )


@close_fig
def test_profile_with_fixed_parameters():
    """Test using profiles with fixed parameters."""
    obj = rosen_for_sensi(max_sensi_order=1)["obj"]

    lb = -2 * np.ones(5)
    ub = 2 * np.ones(5)
    problem = pypesto.Problem(
        objective=obj,
        lb=lb,
        ub=ub,
        x_fixed_vals=[0.5, -1.8],
        x_fixed_indices=[0, 3],
    )

    optimizer = optimize.ScipyOptimizer(options={"maxiter": 50})
    result = optimize.minimize(
        problem=problem,
        optimizer=optimizer,
        n_starts=2,
        progress_bar=False,
    )

    for i_method, next_guess_method in enumerate(
        [
            "fixed_step",
            "adaptive_step_order_0",
            "adaptive_step_order_1",
            "adaptive_step_regression",
        ]
    ):
        print(next_guess_method)
        profile.parameter_profile(
            problem=problem,
            result=result,
            optimizer=optimizer,
            next_guess_method=next_guess_method,
            progress_bar=False,
        )

        # standard plotting
        axes = visualize.profiles(result, profile_list_ids=i_method)
        assert len(axes) == 3
        visualize.profile_cis(result, profile_list=i_method)

    # test profiling with all parameters fixed but one
    problem.fix_parameters([2, 3, 4], result.optimize_result.list[0]["x"][2:5])
    profile.parameter_profile(
        problem=problem,
        result=result,
        optimizer=optimizer,
        next_guess_method="adaptive_step_regression",
        progress_bar=False,
    )


def create_optimization_results(objective, dim_full=2):
    # create optimizer, pypesto problem and options
    options = {"maxiter": 200}
    optimizer = optimize.ScipyOptimizer(method="l-bfgs-b", options=options)

    lb = -2 * np.ones(dim_full)
    ub = 2 * np.ones(dim_full)
    problem = pypesto.Problem(objective, lb, ub)

    optimize_options = optimize.OptimizeOptions(allow_failed_starts=True)

    # run optimization
    result = optimize.minimize(
        problem=problem,
        optimizer=optimizer,
        n_starts=5,
        startpoint_method=pypesto.startpoint.uniform,
        options=optimize_options,
        progress_bar=False,
    )

    return problem, result, optimizer


def test_chi2_quantile_to_ratio():
    """Tests the chi2 quantile to ratio convenience function."""
    ratio = profile.chi2_quantile_to_ratio()
    assert np.isclose(ratio, 0.1465)


def test_approximate_ci():
    xs = np.array([-3, -1, 1, 3, 5, 7, 9])

    ratios = np.array([0.2, 0.3, 1, 0.27, 0.15, 0.15, 0.1])

    lb, ub = profile.calculate_approximate_ci(
        xs=xs, ratios=ratios, confidence_ratio=0.27
    )

    # correct interpolation
    assert np.isclose(lb, -3 + (-1 - (-3)) * 0.7)

    # exact pick
    assert np.isclose(ub, 3)

    lb, ub = profile.calculate_approximate_ci(
        xs=xs, ratios=ratios, confidence_ratio=0.15
    )

    # double value
    assert np.isclose(ub, 7)

    lb, ub = profile.calculate_approximate_ci(
        xs=xs, ratios=ratios, confidence_ratio=0.1
    )

    # bound value
    assert np.isclose(lb, -3)
    assert np.isclose(ub, 9)


def test_options_valid():
    """Test ProfileOptions validity checks."""
    # default settings are valid
    profile.ProfileOptions()

    # try to set invalid values
    with pytest.raises(ValueError):
        profile.ProfileOptions(default_step_size=-1)
    with pytest.raises(ValueError):
        profile.ProfileOptions(default_step_size=1, min_step_size=2)
    with pytest.raises(ValueError):
        profile.ProfileOptions(
            default_step_size=2,
            min_step_size=1,
        )
    with pytest.raises(ValueError):
        profile.ProfileOptions(
            min_step_size=2,
            max_step_size=1,
        )


@pytest.mark.parametrize(
    "lb,ub",
    [(6 * np.ones(5), 10 * np.ones(5)), (-4 * np.ones(5), 1 * np.ones(5))],
)
def test_gh1165(lb, ub):
    """Regression test for https://github.com/ICB-DCM/pyPESTO/issues/1165

    Check profiles with non-symmetric bounds and whole_path=True span the full parameter domain.
    """
    obj = rosen_for_sensi(max_sensi_order=1)["obj"]

    problem = pypesto.Problem(
        objective=obj,
        lb=lb,
        ub=ub,
    )

    optimizer = optimize.ScipyOptimizer(options={"maxiter": 10})
    result = optimize.minimize(
        problem=problem,
        optimizer=optimizer,
        n_starts=2,
        progress_bar=False,
    )
    # just any parameter
    par_idx = 1
    profile.parameter_profile(
        problem=problem,
        result=result,
        optimizer=optimizer,
        next_guess_method="fixed_step",
        profile_index=[par_idx],
        progress_bar=False,
        profile_options=profile.ProfileOptions(
            min_step_size=0.1,
            max_step_size=1.0,
            delta_ratio_max=0.05,
            default_step_size=0.5,
            ratio_min=0.01,
            whole_path=True,
        ),
    )
    # parameter value of the profiled parameter
    x_path = result.profile_result.list[0][par_idx]["x_path"][par_idx, :]
    # ensure we cover lb..ub
    assert x_path[0] == lb[par_idx], (x_path.min(), lb[par_idx])
    assert x_path[-1] == ub[par_idx], (x_path.max(), ub[par_idx])
