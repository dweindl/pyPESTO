"""Test the :class:`pypesto.Objective`."""

import copy
import numbers
from functools import partial

import numpy as np
import pytest
import sympy as sp

import pypesto

from ..util import CRProblem, poly_for_sensi, rosen_for_sensi


@pytest.fixture(params=[True, False])
def integrated(request):
    return request.param


@pytest.fixture(params=[2, 1, 0])
def max_sensi_order(request):
    return request.param


def test_evaluate(integrated):
    """
    Test if values are computed correctly.
    """
    for struct in [
        rosen_for_sensi(2, integrated, [0, 1]),
        poly_for_sensi(2, True, 0.5),
    ]:
        _test_evaluate(struct)


def _test_evaluate(struct):
    obj = struct["obj"]
    x = struct["x"]
    fval_true = struct["fval"]
    grad_true = struct["grad"]
    hess_true = struct["hess"]
    max_sensi_order = struct["max_sensi_order"]

    # check function values
    if max_sensi_order >= 2:
        fval, grad, hess = obj(x, (0, 1, 2))
        assert np.isclose(fval, fval_true)
        assert np.isclose(grad, grad_true).all()
        assert np.isclose(hess, hess_true).all()
    elif max_sensi_order >= 1:
        fval, grad = obj(x, (0, 1))
        assert np.isclose(fval, fval_true)
        assert np.isclose(grad, grad_true).all()
        obj(x, (0, 1, 2))

    # check default argument
    assert np.isclose(obj(x), fval_true)

    # check convenience functions
    assert np.isclose(obj.get_fval(x), fval_true)
    if max_sensi_order >= 1:
        assert np.isclose(obj.get_grad(x), grad_true).all()
    if max_sensi_order >= 2:
        assert np.isclose(obj.get_hess(x), hess_true).all()

    # check different calling types
    if max_sensi_order >= 2:
        grad, hess = obj(x, (1, 2))
        assert np.isclose(grad, grad_true).all()
        assert np.isclose(hess, hess_true).all()


def test_return_type(integrated, max_sensi_order):
    """
    Test if the output format is correct.
    """
    for struct in [
        rosen_for_sensi(max_sensi_order, integrated, [0, 1]),
        poly_for_sensi(max_sensi_order, integrated, 0),
    ]:
        _test_return_type(struct)


def _test_return_type(struct):
    obj = struct["obj"]
    x = struct["x"]
    max_sensi_order = struct["max_sensi_order"]

    ret = obj(x, (0,))
    assert isinstance(ret, numbers.Number)
    if max_sensi_order >= 1:
        ret = obj(x, (1,))
        assert isinstance(ret, np.ndarray)
    if max_sensi_order >= 2:
        ret = obj(x, (2,))
        assert isinstance(ret, np.ndarray)
    if max_sensi_order >= 1:
        ret = obj(x, (0, 1))
        assert isinstance(ret, tuple)
        assert len(ret) == 2


def test_sensis(integrated, max_sensi_order):
    """
    Test output when not all sensitivities can be computed.
    """
    for struct in [
        rosen_for_sensi(max_sensi_order, integrated, [0, 1]),
        poly_for_sensi(max_sensi_order, integrated, 0),
    ]:
        _test_sensis(struct)


def _test_sensis(struct):
    obj = struct["obj"]
    x = struct["x"]
    max_sensi_order = struct["max_sensi_order"]

    obj(x, (0,))
    if max_sensi_order >= 1:
        obj(x, (0, 1))
    else:
        with pytest.raises(ValueError):
            obj(x, (0, 1))
    if max_sensi_order >= 2:
        obj(x, (0, 1, 2))
    else:
        with pytest.raises(ValueError):
            obj(x, (0, 1, 2))


def test_finite_difference_checks():
    """
    Test the finite difference gradient check methods by expected relative
    error.
    """
    x = sp.Symbol("x")

    # Setup single-parameter objective function
    fun_expr = x**10
    grad_expr = fun_expr.diff()
    theta = 0.1

    fun = sp.lambdify(x, fun_expr)
    grad = sp.lambdify(x, grad_expr)

    objective = pypesto.Objective(fun=fun, grad=grad)

    def rel_err(eps_):
        """Expected relative error."""
        central_difference = (fun(theta + eps_) - fun(theta - eps_)) / (
            2 * eps_
        )
        return abs(
            (grad(theta) - central_difference) / (central_difference + eps_)
        )

    # Test the single step size `check_grad` method.
    eps = 1e-5
    result_single_eps = objective.check_grad(
        np.array([theta]), eps=eps, verbosity=False
    )
    np.testing.assert_almost_equal(
        result_single_eps["rel_err"].squeeze(),
        rel_err(eps),
    )

    # Test the multiple step size `check_grad_multi_eps` method.
    multi_eps = {1e-1, 1e-3, 1e-5, 1e-7, 1e-9}
    result_multi_eps = objective.check_grad_multi_eps(
        [theta], multi_eps=multi_eps, verbosity=False
    )

    np.testing.assert_almost_equal(
        result_multi_eps["rel_err"].squeeze(),
        min(rel_err(_eps) for _eps in multi_eps),
    )


@pytest.mark.parametrize("enable_x64", [True, False])
@pytest.mark.parametrize("fix_parameters", [True, False])
def test_jax(max_sensi_order, integrated, enable_x64, fix_parameters):
    """Test function composition and gradient computation via jax"""
    import jax
    import jax.numpy as jnp

    if max_sensi_order == 2:
        pytest.skip("Not Implemented")

    jax.config.update("jax_enable_x64", enable_x64)

    from pypesto.objective.jax import JaxObjective
    from pypesto.objective.pre_post_process import FixedParametersProcessor

    prob = rosen_for_sensi(max_sensi_order, integrated, [0, 1])

    x_ref = np.asarray(prob["x"])

    def jax_op_in(x: jnp.array) -> jnp.array:
        # pick a simple function here to avoid numerical issues
        return 3.0 * x

    def jax_op_out(x: jnp.array) -> jnp.array:
        # pick a simple function here to avoid numerical issues
        return 0.5 * x

    # compose rosenbrock function with sinh transformation
    obj = JaxObjective(prob["obj"])

    if fix_parameters:
        obj.pre_post_processor = FixedParametersProcessor(
            dim_full=2,
            x_free_indices=[0],
            x_fixed_indices=[1],
            x_fixed_vals=[0.0],
        )

    # evaluate for a couple of random points such that we can assess
    # compatibility with vmap
    xx = x_ref + np.random.randn(10, x_ref.shape[0])
    if fix_parameters:
        xx = xx[:, obj.pre_post_processor.x_free_indices]

    rvals_ref = [
        jax_op_out(
            prob["obj"](jax_op_in(xxi), sensi_orders=(max_sensi_order,))
        )
        for xxi in xx
    ]

    def _fun(y, pypesto_fun, jax_fun_in, jax_fun_out):
        return jax_fun_out(pypesto_fun(jax_fun_in(y)))

    assert obj.check_sensi_orders((max_sensi_order,), pypesto.C.MODE_FUN)
    assert not obj.check_sensi_orders((max_sensi_order,), pypesto.C.MODE_RES)

    for _obj in (obj, copy.deepcopy(obj)):
        fun = partial(
            _fun,
            pypesto_fun=_obj,
            jax_fun_in=jax_op_in,
            jax_fun_out=jax_op_out,
        )

        if max_sensi_order == 1:
            fun = jax.grad(fun)

        # check compatibility with vmap and jit
        vmapped_fun = jax.vmap(fun)
        rvals_jax = vmapped_fun(xx)
        atol = 0
        # also need to account for roundoff errors in input, so we
        # can't use rtol = 1e-8 for 32bit
        rtol = 1e-16 if enable_x64 else 1e-4
        for x, rref, rj in zip(xx, rvals_ref, rvals_jax):
            assert isinstance(rj, jnp.ndarray)
            if max_sensi_order == 0:
                np.testing.assert_allclose(
                    rref, float(rj), atol=atol, rtol=rtol
                )
            if max_sensi_order == 1:
                # g(x) = b(c(x)) => g'(x) = b'(c(x))) * c'(x)
                # f(x) = a(g(x)) => f'(x) = a'(g(x)) * g'(x)
                # c: jax_op_in, b: prob["obj"], a: jax_op_out
                # g(x) = b(c(x))
                g = prob["obj"](jax_op_in(x))
                # g'(x) = b'(c(x))) * c'(x)
                g_prime = prob["obj"](
                    jax_op_in(x), sensi_orders=(1,)
                ) @ jax.jacfwd(jax_op_in)(x)
                # f'(x) = a'(g(x)) * g'(x)
                f_prime = jax.jacfwd(jax_op_out)(g) * g_prime
                np.testing.assert_allclose(
                    f_prime, np.asarray(rj), atol=atol, rtol=rtol
                )


@pytest.fixture(
    params=[pypesto.FD.CENTRAL, pypesto.FD.FORWARD, pypesto.FD.BACKWARD]
)
def fd_method(request) -> str:
    """Finite difference method."""
    return request.param


@pytest.fixture(
    params=[
        1e-6,
        pypesto.FDDelta.CONSTANT,
        pypesto.FDDelta.DISTANCE,
        pypesto.FDDelta.STEPS,
        pypesto.FDDelta.ALWAYS,
    ]
)
def fd_delta(request):
    """Finite difference step size method."""
    return request.param


# add a fixture for fixed and unfixed parameters
@pytest.mark.parametrize("fixed", [True, False])
def test_fds(fd_method, fd_delta, fixed):
    """Test finite differences."""
    problem = CRProblem()

    if fixed:
        fixed_problem = problem.get_problem()
        fixed_problem.fix_parameters([1], problem.p_true[1])
        obj = fixed_problem.objective
        p = problem.p_true[0]
    else:
        obj = problem.get_objective()
        p = problem.p_true

    # FDs for everything
    obj_fd = pypesto.FD(
        obj,
        grad=True,
        hess=True,
        sres=True,
        method=fd_method,
        delta_fun=fd_delta,
        delta_grad=fd_delta,
        delta_res=fd_delta,
    )
    # bases Hessian on gradients
    obj_fd_grad = pypesto.FD(
        obj,
        grad=True,
        hess=True,
        sres=True,
        hess_via_fval=False,
        method=fd_method,
        delta_fun=fd_delta,
        delta_grad=fd_delta,
        delta_res=fd_delta,
    )
    # does not actually use FDs
    obj_fd_fake = pypesto.FD(
        obj,
        grad=None,
        hess=None,
        sres=None,
        method=fd_method,
        delta_fun=fd_delta,
        delta_grad=fd_delta,
        delta_res=fd_delta,
    )
    # limited outputs, no derivatives
    obj_fd_limited = pypesto.FD(
        obj,
        grad=False,
        hess=False,
        sres=False,
        method=fd_method,
        delta_fun=fd_delta,
        delta_grad=fd_delta,
        delta_res=fd_delta,
    )

    # check that function values coincide (call delegated)
    for attr in ["fval", "res"]:
        val = getattr(obj, f"get_{attr}")(p)
        val_fd = getattr(obj_fd, f"get_{attr}")(p)
        val_fd_grad = getattr(obj_fd_grad, f"get_{attr}")(p)
        val_fd_fake = getattr(obj_fd_fake, f"get_{attr}")(p)
        val_fd_limited = getattr(obj_fd_limited, f"get_{attr}")(p)
        assert (
            (val == val_fd).all()
            and (val == val_fd_grad).all()
            and (val == val_fd_fake).all()
            and (val == val_fd_limited).all()
        ), attr

    # check that derivatives are close
    if fd_method == pypesto.FD.CENTRAL:
        atol = rtol = 1e-4
    else:
        atol = rtol = 1e-2
    for attr in ["grad", "hess", "sres"]:
        val = getattr(obj, f"get_{attr}")(p)
        val_fd = getattr(obj_fd, f"get_{attr}")(p)
        val_fd_grad = getattr(obj_fd_grad, f"get_{attr}")(p)
        val_fd_fake = getattr(obj_fd_fake, f"get_{attr}")(p)

        assert np.allclose(val, val_fd, atol=atol, rtol=rtol), attr
        # cannot completely coincide
        assert (val != val_fd).any(), attr

        assert np.allclose(val, val_fd_grad, atol=atol, rtol=rtol), attr
        # cannot completely coincide
        assert (val != val_fd_grad).any(), attr

        if attr == "hess":
            assert (val_fd != val_fd_grad).any(), attr
        # should use available actual functionality
        assert (val == val_fd_fake).all(), attr

        # cannot be called
        with pytest.raises(ValueError):
            getattr(obj_fd_limited, f"get_{attr}")(p)

    # evaluate a couple times and assert number of update steps is as expected
    for i in range(31):
        obj_fd(10 * i * p, sensi_orders=(0, 1))
    if fd_delta == pypesto.FDDelta.CONSTANT:
        assert obj_fd.delta_fun.updates == 1
    elif isinstance(fd_delta, (float, np.ndarray)):
        assert obj_fd.delta_fun.updates == 0
    else:
        assert obj_fd.delta_fun.updates > 1


def test_call_unprocessed_return_dict():
    class Objective0(pypesto.objective.ObjectiveBase):
        def call_unprocessed(self, *args, **kwargs):
            return {"fval": 0, "return_dict": "return_dict" in kwargs}

        def check_sensi_orders(self, *args, **kwargs):
            return True

    class Objective1(Objective0):
        def call_unprocessed(self, *args, return_dict: bool, **kwargs):
            return {"fval": 0, "return_dict": return_dict}

    objective0 = Objective0()
    objective1 = Objective1()

    with pytest.warns(DeprecationWarning, match="Please add `return_dict`"):
        result0 = objective0([0], return_dict=True)

    result1 = objective1([0], return_dict=True)

    # `return_dict` is not shared with `call_unprocessed` by default,
    assert not result0["return_dict"]
    # but is shared if the `call_unprocessed` signature supports it.
    assert result1["return_dict"]
