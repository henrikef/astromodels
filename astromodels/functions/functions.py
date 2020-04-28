from __future__ import division

import math
import warnings

import astropy.units as astropy_units
import numpy as np
import six
from past.utils import old_div
from scipy.special import erfcinv, gamma, gammaincc

import astromodels.functions.numba_functions as nb_func
from astromodels.core.units import get_units
from astromodels.functions.function import (Function1D, FunctionMeta,
                                            ModelAssertionViolation)

__author__ = 'giacomov'
# DMFitFunction and DMSpectra add by Andrea Albert (aalbert@slac.stanford.edu) Oct 26, 2016






class GSLNotAvailable(ImportWarning):
    pass


class NaimaNotAvailable(ImportWarning):
    pass


class EBLTableNotAvailable(ImportWarning):
    pass


class InvalidUsageForFunction(Exception):
    pass


# Now let's try and import optional dependencies

try:

    # Naima is for numerical computation of Synch. and Inverse compton spectra in randomly oriented
    # magnetic fields

    import naima
    import astropy.units as u

except ImportError:

    warnings.warn("The naima package is not available. Models that depend on it will not be available",
                  NaimaNotAvailable)

    has_naima = False

else:

    has_naima = True

try:

    # GSL is the GNU Scientific Library. Pygsl is the python wrapper for it. It is used by some
    # functions for faster computation

    from pygsl.testing.sf import gamma_inc

except ImportError:

    warnings.warn("The GSL library or the pygsl wrapper cannot be loaded. Models that depend on it will not be "
                  "available.", GSLNotAvailable)

    has_gsl = False

else:

    has_gsl = True


try:

    # ebltable is a Python packages to read in and interpolate tables for the photon density of
    # the Extragalactic Background Light (EBL) and the resulting opacity for high energy gamma
    # rays.

    import ebltable.tau_from_model as ebltau


except ImportError:

    warnings.warn("The ebltable package is not available. Models that depend on it will not be available",
                  EBLTableNotAvailable)

    has_ebltable = False

else:

    has_ebltable = True


# noinspection PyPep8Naming
@six.add_metaclass(FunctionMeta)
class Powerlaw_lognorm(Function1D):
    r"""
    description :

        A simple power-law

    latex : $ K~\frac{x}{piv}^{index} $

    parameters :

        K :

            desc : Normalization (log of differential flux at the pivot value)
            initial value : 1.0
            is_normalization : True
            transformation : log10

        piv :

            desc : Pivot value
            initial value : 1
            fix : yes

        index :

            desc : Photon index
            initial value : -2
            min : -10
            max : 10

    """

    def _set_units(self, x_unit, y_unit):

        warnings.warn("The Powerlaw_lognorm function is deprecated. Use the normal Powerlaw function which "
                      "has the same functionality", DeprecationWarning)

        # The index is always dimensionless
        self.index.unit = astropy_units.dimensionless_unscaled

        # The pivot energy has always the same dimension as the x variable
        self.piv.unit = x_unit

        # The normalization has the same units as the y

        self.K.unit = y_unit

    # noinspection PyPep8Naming
    def evaluate(self, x, K, piv, index):

        xx = np.divide(x, piv)

        return K * np.power(xx, index)


@six.add_metaclass(FunctionMeta)
class Powerlaw(Function1D):
    r"""
    description :

        A simple power-law

    latex : $ K~\frac{x}{piv}^{index} $

    parameters :

        K :

            desc : Normalization (differential flux at the pivot value)
            initial value : 1.0
            is_normalization : True
            transformation : log10
            min : 1e-30
            max : 1e3
            delta : 0.1

        piv :

            desc : Pivot value
            initial value : 1
            fix : yes

        index :

            desc : Photon index
            initial value : -2
            min : -10
            max : 10

    tests :
        - { x : 10, function value: 0.01, tolerance: 1e-20}
        - { x : 100, function value: 0.0001, tolerance: 1e-20}

    """

    def _set_units(self, x_unit, y_unit):
        # The index is always dimensionless
        self.index.unit = astropy_units.dimensionless_unscaled

        # The pivot energy has always the same dimension as the x variable
        self.piv.unit = x_unit

        # The normalization has the same units as the y

        self.K.unit = y_unit

    # noinspection PyPep8Naming
    def evaluate(self, x, K, piv, index):

        if isinstance(x, astropy_units.Quantity):
            index_ = index.value
            K_ = K.value
            piv_ = piv.value
            x_ = np.atleast_1d(x.value)

            unit_ = self.y_unit

        else:
            unit_ = 1.0
            K_, piv_, x_, index_ = K, piv, x, index
        
        result = nb_func.plaw_eval(x_, K_, index_, piv_)

               
        return result * unit_


# noinspection PyPep8Naming
@six.add_metaclass(FunctionMeta)
class Powerlaw_flux(Function1D):
    r"""
        description :

            A simple power-law with the photon flux in a band used as normalization. This will reduce the correlation
            between the index and the normalization.

        latex : $ \frac{F(\gamma+1)} {b^{\gamma+1} - a^{\gamma+1}} (x)^{\gamma}$

        parameters :

            F :

                desc : Integral between a and b
                initial value : 1
                is_normalization : True
                transformation : log10
                min : 1e-30
                max : 1e3
                delta : 0.1

            index :

                desc : Photon index
                initial value : -2
                min : -10
                max : 10

            a :

                desc : lower bound for the band in which computing the integral F
                initial value : 1.0
                fix : yes

            b :

                desc : upper bound for the band in which computing the integral F
                initial value : 100.0
                fix : yes

            piv :
    
                 desc : Pivot value
                 initial value : 1
                 fix : yes


        """

    def _set_units(self, x_unit, y_unit):
        # The flux is the integral over x, so:
        self.F.unit = y_unit * x_unit

        # The index is always dimensionless
        self.index.unit = astropy_units.dimensionless_unscaled

        # a and b have the same units as x

        self.piv.unit = y_unit
        
        self.a.unit = x_unit
        self.b.unit = x_unit

    # noinspection PyPep8Naming
    def evaluate(self, x, F, index, a, b, piv):
        gp1 = index + 1

        if isinstance(x, astropy_units.Quantity):
            index_ = index.value
            F_ = F.value
            piv_ = piv.value
            x_ = np.atleast_1d(x.value)

            unit_ = self.y_unit * self.x_unit

        else:
            unit_ = 1.0
            F_, piv_, x_, index_ = F, piv, x, index
        
        plaw = nb_func.plaw_eval(x_, F_, index_, piv_)


        
        return gp1 / ((b/piv) ** gp1 - (apiv) ** gp1) * plaw * unit_


@six.add_metaclass(FunctionMeta)
class Cutoff_powerlaw(Function1D):
    r"""
    description :

        A power law multiplied by an exponential cutoff

    latex : $ K~\frac{x}{piv}^{index}~\exp{-x/xc} $

    parameters :

        K :

            desc : Normalization (differential flux at the pivot value)
            initial value : 1.0
            is_normalization : True
            transformation : log10
            min : 1e-30
            max : 1e3
            delta : 0.1

        piv :

            desc : Pivot value
            initial value : 1
            fix : yes

        index :

            desc : Photon index
            initial value : -2
            min : -10
            max : 10

        xc :

            desc : Cutoff energy
            initial value : 10.0
            transformation : log10

    """

    def _set_units(self, x_unit, y_unit):
        # The index is always dimensionless
        self.index.unit = astropy_units.dimensionless_unscaled

        # The pivot energy has always the same dimension as the x variable
        self.piv.unit = x_unit

        self.xc.unit = x_unit

        # The normalization has the same units as the y

        self.K.unit = y_unit

    # noinspection PyPep8Naming
    def evaluate(self, x, K, piv, index, xc):


        if isinstance(x, astropy_units.Quantity):
            index_ = index.value
            K_ = K.value
            piv_ = piv.value
            xc_ = xc.value
            x_ = np.atleast_1d(x.value)

            unit_ = self.y_unit

        else:
            unit_ = 1.0
            K_, piv_, x_, index_, xc_ = K, piv, x, index, xc_
        
        result = nb_func.cplaw_eval(x_, K_, xc_ ,index_, piv_)
        
        return result * unit_

@six.add_metaclass(FunctionMeta)
class Inverse_cutoff_powerlaw(Function1D):
    r"""
    description :
        A power law multiplied by an exponential cutoff [Note: instead of cutoff energy energy parameter xc, b = 1/xc is used]
    latex : $ K~\frac{x}{piv}^{index}~\exp{-x~\b} $
    parameters :
        K :
            desc : Normalization (differential flux at the pivot value)
            initial value : 1.0
            is_normalization : True
            transformation : log10
            min : 1e-30
            max : 1e3
            delta : 0.1
        piv :
            desc : Pivot value
            initial value : 1
            fix : yes
        index :
            desc : Photon index
            initial value : -2
            min : -10
            max : 10
        b :
            desc : inverse cutoff energy i.e 1/xc
            initial value : 1
    """



    def _set_units(self, x_unit, y_unit):
        # The index is always dimensionless
        self.index.unit = astropy_units.dimensionless_unscaled

        # The pivot energy has always the same dimension as the x variable
        self.piv.unit = x_unit

        self.b.unit = 1/x_unit

        # The normalization has the same units as the y

        self.K.unit = y_unit

    # noinspection PyPep8Naming
    def evaluate(self, x, K, piv, index, b):

        
        if isinstance(x, astropy_units.Quantity):
            index_ = index.value
            K_ = K.value
            piv_ = piv.value
            b_ = b.value
            x_ = np.atleast_1d(x.value)

            unit_ = self.y_unit

        else:
            unit_ = 1.0
            K_, piv_, x_, index_, b_ = K, piv, x, index, b_
        
        result = nb_func.cplaw_index_eval(x_, K_, b_ ,index_, piv_)
        
        return result * unit_


        


@six.add_metaclass(FunctionMeta)
class Super_cutoff_powerlaw(Function1D):
    r"""
    description :

        A power law with a super-exponential cutoff

    latex : $ K~\frac{x}{piv}^{index}~\exp{(-x/xc)^{\gamma}} $

    parameters :

        K :

            desc : Normalization (differential flux at the pivot value)
            initial value : 1.0
            is_normalization : True

        piv :

            desc : Pivot value
            initial value : 1
            fix : yes

        index :

            desc : Photon index
            initial value : -2
            min : -10
            max : 10

        xc :

            desc : Photon index
            initial value : 10.0
            min : 1.0

        gamma :

            desc : Index of the super-exponential cutoff
            initial value : 1.0
            min : 0.1
            max : 10.0

    """

    def _set_units(self, x_unit, y_unit):
        # The index is always dimensionless
        self.index.unit = astropy_units.dimensionless_unscaled
        self.gamma.unit = astropy_units.dimensionless_unscaled

        # The pivot energy has always the same dimension as the x variable
        self.piv.unit = x_unit

        # The cutoff has the same dimensions as x
        self.xc.unit = x_unit

        # The normalization has the same units as the y

        self.K.unit = y_unit

    # noinspection PyPep8Naming
    def evaluate(self, x, K, piv, index, xc, gamma):
        return K * np.power(np.divide(x, piv), index) * np.exp(-1 * np.divide(x, xc)**gamma)


@six.add_metaclass(FunctionMeta)
class SmoothlyBrokenPowerLaw(Function1D):
    r"""
    description :

        A Smoothly Broken Power Law

    latex : $  $

    parameters :

        K :

            desc : normalization
            initial value : 1
            min : 0
            is_normalization : True


        alpha :

            desc : power law index below the break
            initial value : -1
            min : -1.5
            max : 2

        break_energy:

            desc: location of the peak
            initial value : 300
            fix : no
            min : 10

        break_scale :

            desc: smoothness of the break
            initial value : 0.5
            min : 0.
            max : 10.
            fix : yes

        beta:

            desc : power law index above the break
            initial value : -2.
            min : -5.0
            max : -1.6

        pivot:

            desc: where the spectrum is normalized
            initial value : 100.
            fix: yes


    """

    def _set_units(self, x_unit, y_unit):

        # norm has same unit as energy
        self.K.unit = y_unit

        self.break_energy.unit = x_unit

        self.pivot.unit = x_unit

        self.alpha.unit = astropy_units.dimensionless_unscaled
        self.beta.unit = astropy_units.dimensionless_unscaled
        self.break_scale.unit = astropy_units.dimensionless_unscaled

    def evaluate(self, x, K, alpha, break_energy, break_scale, beta, pivot):

        B = old_div((alpha + beta), 2.0)
        M = old_div((beta - alpha), 2.0)

        arg_piv = old_div(np.log10(old_div(pivot, break_energy)), break_scale)

        if arg_piv < -6.0:
            pcosh_piv = M * break_scale * (-arg_piv - np.log(2.0))
        elif arg_piv > 4.0:

            pcosh_piv = M * break_scale * (arg_piv - np.log(2.0))
        else:
            pcosh_piv = M * break_scale * \
                (np.log(old_div((np.exp(arg_piv) + np.exp(-arg_piv)), 2.0)))

        arg = old_div(np.log10(old_div(x, break_energy)), break_scale)
        idx1 = arg < -6.0
        idx2 = arg > 4.0
        idx3 = ~np.logical_or(idx1, idx2)

        # The K * 0 part is a trick so that out will have the right units (if the input
        # has units)

        pcosh = np.zeros(x.shape)

        pcosh[idx1] = M * break_scale * (-arg[idx1] - np.log(2.0))
        pcosh[idx2] = M * break_scale * (arg[idx2] - np.log(2.0))
        pcosh[idx3] = M * break_scale * \
            (np.log(old_div((np.exp(arg[idx3]) + np.exp(-arg[idx3])), 2.0)))

        return K * (old_div(x, pivot)) ** B * 10. ** (pcosh - pcosh_piv)


@six.add_metaclass(FunctionMeta)
class Broken_powerlaw(Function1D):
    r"""
    description :

        A broken power law function

    latex : $ f(x)= K~\begin{cases}\left( \frac{x}{x_{b}} \right)^{\alpha} & x < x_{b} \\ \left( \frac{x}{x_{b}} \right)^{\beta} & x \ge x_{b} \end{cases} $

    parameters :

        K :

            desc : Normalization (differential flux at x_b)
            initial value : 1.0
            is_normalization : True

        xb :

            desc : Break point
            initial value : 10
            min : 1.0

        alpha :

            desc : Index before the break xb
            initial value : -1.5
            min : -10
            max : 10

        beta :

            desc : Index after the break xb
            initial value : -2.5
            min : -10
            max : 10

        piv :

            desc : Pivot energy
            initial value : 1.0
            fix : yes

    """

    def _set_units(self, x_unit, y_unit):
        # The normalization has the same units as y
        self.K.unit = y_unit

        # The break point has always the same dimension as the x variable
        self.xb.unit = x_unit

        # alpha and beta are dimensionless
        self.alpha.unit = astropy_units.dimensionless_unscaled
        self.beta.unit = astropy_units.dimensionless_unscaled

        self.piv.unit = x_unit

    # noinspection PyPep8Naming
    def evaluate(self, x, K, xb, alpha, beta, piv):
        # The K * 0 is to keep the units right. If the input has unit, this will make a result
        # array with the same units as K. If the input has no units, this will have no
        # effect whatsoever

        if isinstance(x, astropy_units.Quantity):
            alpha_ = alpha.value
            beta_ = alpha.value
            K_ = K.value
            xb_ = xb.value
            piv_ = piv.value
            x_ = np.atleast_1d(x.value)

            unit_ = self.y_unit

        else:
            unit_ = 1.0
            alpha_, beta_, K_, piv_, x_, xb_ = alpha, beta, K, piv, x, xb
        
        result = nb_func.bplaw_eval(x_, K_, xb_, alpha_, beta_, piv_)
            
        return result * unit_


@six.add_metaclass(FunctionMeta)
class StepFunction(Function1D):
    r"""
        description :

            A function which is constant on the interval lower_bound - upper_bound and 0 outside the interval. The
            extremes of the interval are counted as part of the interval.

        latex : $ f(x)=\begin{cases}0 & x < \text{lower_bound} \\\text{value} & \text{lower_bound} \le x \le \text{upper_bound} \\ 0 & x > \text{upper_bound} \end{cases}$

        parameters :

            lower_bound :

                desc : Lower bound for the interval
                initial value : 0

            upper_bound :

                desc : Upper bound for the interval
                initial value : 1

            value :

                desc : Value in the interval
                initial value : 1.0

        tests :
            - { x : 0.5, function value: 1.0, tolerance: 1e-20}
            - { x : -0.5, function value: 0, tolerance: 1e-20}

        """

    def _set_units(self, x_unit, y_unit):
        # Lower and upper bound has the same unit as x
        self.lower_bound.unit = x_unit
        self.upper_bound.unit = x_unit

        # value has the same unit as y
        self.value.unit = y_unit

    def evaluate(self, x, lower_bound, upper_bound, value):
        # The value * 0 is to keep the units right

        result = np.zeros(x.shape) * value * 0

        idx = (x >= lower_bound) & (x <= upper_bound)
        result[idx] = value

        return result


@six.add_metaclass(FunctionMeta)
class StepFunctionUpper(Function1D):
    r"""
        description :

            A function which is constant on the interval lower_bound - upper_bound and 0 outside the interval. The
            upper interval is open.

        latex : $ f(x)=\begin{cases}0 & x < \text{lower_bound} \\\text{value} & \text{lower_bound} \le x \le \text{upper_bound} \\ 0 & x > \text{upper_bound} \end{cases}$

        parameters :

            lower_bound :

                desc : Lower bound for the interval
                initial value : 0
                fix : yes

            upper_bound :

                desc : Upper bound for the interval
                initial value : 1
                fix : yes

            value :

                desc : Value in the interval
                initial value : 1.0

        tests :
            - { x : 0.5, function value: 1.0, tolerance: 1e-20}
            - { x : -0.5, function value: 0, tolerance: 1e-20}

        """

    def _set_units(self, x_unit, y_unit):
        # Lower and upper bound has the same unit as x
        self.lower_bound.unit = x_unit
        self.upper_bound.unit = x_unit

        # value has the same unit as y
        self.value.unit = y_unit

    def evaluate(self, x, lower_bound, upper_bound, value):
        # The value * 0 is to keep the units right

        result = np.zeros(x.shape) * value * 0

        idx = (x >= lower_bound) & (x < upper_bound)
        result[idx] = value

        return result


# noinspection PyPep8Naming
@six.add_metaclass(FunctionMeta)
class Blackbody(Function1D):
    r"""

    description :
        A blackbody function

    latex : $f(x) = K \frac{x^2}{\exp(\frac{x}{kT}) -1}  $

    parameters :
        K :
            desc :
            initial value : 1e-4
            min : 0.
            is_normalization : True

        kT :
            desc : temperature of the blackbody
            initial value : 30.0
            min: 0.
    """

    def _set_units(self, x_unit, y_unit):
        # The normalization has the same units as y
        self.K.unit = old_div(y_unit, (x_unit ** 2))

        # The break point has always the same dimension as the x variable
        self.kT.unit = x_unit

    def evaluate(self, x, K, kT):

        arg = np.divide(x, kT)

        # get rid of overflow
        idx = arg <= 700.

        # The K * 0 part is a trick so that out will have the right units (if the input
        # has units)

        out = np.zeros(x.shape) * K * x * x * 0

        out[idx] = np.divide(K * x[idx] * x[idx], np.expm1(arg[idx]))
        #out[~idx] = 0. * K

        return out


# noinspection PyPep8Naming
@six.add_metaclass(FunctionMeta)
class Sin(Function1D):
    r"""
    description :

        A sinusodial function

    latex : $ K~\sin{(2\pi f x + \phi)} $

    parameters :

        K :

            desc : Normalization
            initial value : 1
            is_normalization : True

        f :

            desc : frequency
            initial value : 1.0 / (2 * np.pi)
            min : 0

        phi :

            desc : phase
            initial value : 0
            min : -np.pi
            max : +np.pi
            unit: rad

    tests :
        - { x : 0.0, function value: 0.0, tolerance: 1e-10}
        - { x : 1.5707963267948966, function value: 1.0, tolerance: 1e-10}

    """

    def _set_units(self, x_unit, y_unit):
        # The normalization has the same unit of y
        self.K.unit = y_unit

        # The unit of f is 1 / [x] because fx must be a pure number. However,
        # np.pi of course doesn't have units, so we add a rad
        self.f.unit = x_unit ** (-1) * astropy_units.rad

        # The unit of phi is always the same (radians)

        self.phi.unit = astropy_units.rad

    # noinspection PyPep8Naming
    def evaluate(self, x, K, f, phi):
        return K * np.sin(2 * np.pi * f * x + phi)


@six.add_metaclass(FunctionMeta)
class Line(Function1D):
    r"""
    description :

        A linear function

    latex : $ a * x + b $

    parameters :

        a :

            desc : linear coefficient
            initial value : 1

        b :

            desc : intercept
            initial value : 0

    """

    def _set_units(self, x_unit, y_unit):
        # a has units of y_unit / x_unit, so that a*x has units of y_unit
        self.a.unit = old_div(y_unit, x_unit)

        # b has units of y
        self.b.unit = y_unit

    def evaluate(self, x, a, b):
        return a * x + b


@six.add_metaclass(FunctionMeta)
class Constant(Function1D):
    r"""
        description :

            Return k

        latex : $ k $

        parameters :

            k :

                desc : Constant value
                initial value : 0

        """

    def _set_units(self, x_unit, y_unit):
        self.k.unit = y_unit

    def evaluate(self, x, k):
        return k


@six.add_metaclass(FunctionMeta)
class DiracDelta(Function1D):
    r"""
        description :

            return  at zero_point

        latex : $ value $

        parameters :

            value :

                desc : Constant value
                initial value : 0

            zero_point:

                 desc: value at which function is non-zero
                 initial value : 0
                 fix : yes


        """

    def _set_units(self, x_unit, y_unit):

        self.value.unit = y_unit
        self.zero_point.unit = x_unit

    def evaluate(self, x, value, zero_point):

        out = np.zeros(x.shape) * value * 0

        out[x == zero_point] = value

        return out


if has_naima:
    @six.add_metaclass(FunctionMeta)
    class Synchrotron(Function1D):
        r"""
        description :
            Synchrotron spectrum from an input particle distribution, using Naima (naima.readthedocs.org)
        latex: not available
        parameters :
            B :
                desc : magnetic field
                initial value : 3.24e-6
                unit: Gauss
            distance :
                desc : distance of the source
                initial value : 1.0
                unit : kpc
            emin :
                desc : minimum energy for the particle distribution
                initial value : 1
                fix : yes
                unit: GeV
            emax :
                desc : maximum energy for the particle distribution
                initial value : 510e3
                fix : yes
                unit: GeV
            need:
                desc: number of points per decade in which to evaluate the function
                initial value : 10
                min : 2
                max : 100
                fix : yes
        """

        def _set_units(self, x_unit, y_unit):

            # This function can only be used as a spectrum,
            # so let's check that x_unit is a energy and y_unit is
            # differential flux

            if hasattr(x_unit, "physical_type") and x_unit.physical_type == 'energy':

                # Now check that y is a differential flux
                current_units = get_units()
                should_be_unitless = y_unit * \
                    (current_units.energy * current_units.time * current_units.area)

                if not hasattr(should_be_unitless, 'physical_type') or \
                        should_be_unitless.decompose().physical_type != 'dimensionless':
                    # y is not a differential flux
                    raise InvalidUsageForFunction("Unit for y is not differential flux. The function synchrotron "
                                                  "can only be used as a spectrum.")
            else:

                raise InvalidUsageForFunction("Unit for x is not an energy. The function synchrotron can only be used "
                                              "as a spectrum")

                # we actually don't need to do anything as the units are already set up

        def set_particle_distribution(self, function):

            self._particle_distribution = function

            # Now set the units for the function

            current_units = get_units()

            self._particle_distribution.set_units(
                current_units.energy, current_units.energy ** (-1))

            # Naima wants a function which accepts a quantity as x (in units of eV) and returns an astropy quantity,
            # so we need to create a wrapper which will remove the unit from x and add the unit to the return
            # value

            self._particle_distribution_wrapper = lambda x: old_div(
                function(x.value), current_units.energy)

        def get_particle_distribution(self):

            return self._particle_distribution

        particle_distribution = property(get_particle_distribution, set_particle_distribution,
                                         doc="""Get/set particle distribution for electrons""")

        def fix_units(self, x, B, distance, emin, emax):

            if isinstance(x, u.Quantity):
                return True, x.to(get_units().energy), B.to(u.Gauss), distance.to(u.kpc), emin.to(u.GeV), emax.to(u.GeV)
            else:
                return False, x*(get_units().energy), B*(u.Gauss), distance*(u.kpc), emin*(u.GeV), emax*(u.GeV)

        # noinspection PyPep8Naming
        def evaluate(self, x, B, distance, emin, emax, need):

            has_units, x, B, distance, emin, emax = self.fix_units(
                x, B, distance, emin, emax)

            _synch = naima.models.Synchrotron(self._particle_distribution_wrapper, B,
                                              Eemin=emin, Eemax=emax, nEed=need)

            if has_units:
                return _synch.flux(x, distance=distance)
            else:
                return _synch.flux(x, distance=distance).value

        def to_dict(self, minimal=False):

            data = super(Function1D, self).to_dict(minimal)

            if not minimal:
                data['extra_setup'] = {
                    'particle_distribution': self.particle_distribution.path}

            return data


@six.add_metaclass(FunctionMeta)
class _ComplexTestFunction(Function1D):
    r"""
    description :
        A useless function to be used during automatic tests

    latex: not available

    parameters :
        A :
            desc : none
            initial value : 3.24e-6
            min : 1e-6
            max : 1e-5

        B :
            desc : none
            initial value : -10
            min : -100
            max : 100
            delta : 0.1
    """

    def _set_units(self, x_unit, y_unit):

        self.A.unit = y_unit
        self.B.unit = old_div(y_unit, x_unit)

    def set_particle_distribution(self, function):

        self._particle_distribution = function

    def get_particle_distribution(self):

        return self._particle_distribution

    particle_distribution = property(get_particle_distribution, set_particle_distribution,
                                     doc="""Get/set particle distribution for electrons""")

    # noinspection PyPep8Naming
    def evaluate(self, x, A, B):

        return A + B * x

    def to_dict(self, minimal=False):

        data = super(Function1D, self).to_dict(minimal)

        if not minimal:

            data['extra_setup'] = {
                'particle_distribution': self.particle_distribution.path}

        return data


@six.add_metaclass(FunctionMeta)
class Band(Function1D):
    r"""
    description :

        Band model from Band et al., 1993, parametrized with the peak energy

    latex : $  $

    parameters :

        K :

            desc : Differential flux at the pivot energy
            initial value : 1e-4
            is_normalization : True

        alpha :

            desc : low-energy photon index
            initial value : -1.0
            min : -1.5
            max : 3

        xp :

            desc : peak in the x * x * N (nuFnu if x is a energy)
            initial value : 500
            min : 10

        beta :

            desc : high-energy photon index
            initial value : -2.0
            min : -5.0
            max : -1.6

        piv :

            desc : pivot energy
            initial value : 100.0
            fix : yes
    """

    def _set_units(self, x_unit, y_unit):
        # The normalization has the same units as y
        self.K.unit = y_unit

        # The break point has always the same dimension as the x variable
        self.xp.unit = x_unit

        self.piv.unit = x_unit

        # alpha and beta are dimensionless
        self.alpha.unit = astropy_units.dimensionless_unscaled
        self.beta.unit = astropy_units.dimensionless_unscaled

    def evaluate(self, x, K, alpha, xp, beta, piv):
        E0 = old_div(xp, (2 + alpha))

        if (alpha < beta):
            raise ModelAssertionViolation("Alpha cannot be less than beta")

        if isinstance(x, astropy_units.Quantity):
            alpha_ = alpha.value
            beta_ = alpha.value
            K_ = K.value
            E0_ = E0.value
            piv_ = piv.value
            x_ = np.atleast_1d(x.value)

            unit_ = self.y_unit

        else:
            unit_ = 1.0
            alpha_, beta_, K_, piv_, x_, E0_ = alpha, beta, K, piv, x, E0

        return nb_func.band_eval(x_, K_, alpha_, beta_, E0_, piv_) * unit_


@six.add_metaclass(FunctionMeta)
class Band_grbm(Function1D):
    r"""
    description :

        Band model from Band et al., 1993, parametrized with the cutoff energy

    latex : $  $

    parameters :

        K :

            desc : Differential flux at the pivot energy
            initial value : 1e-4
            is_normalization : True

        alpha :

            desc : low-energy photon index
            initial value : -1.0
            min : -1.5
            max : 3

        xc :

            desc : cutoff of exp
            initial value : 500
            min : 10

        beta :

            desc : high-energy photon index
            initial value : -2.0
            min : -5.0
            max : -1.6

        piv :

            desc : pivot energy
            initial value : 100.0
            fix : yes
    """

    def _set_units(self, x_unit, y_unit):
        # The normalization has the same units as y
        self.K.unit = y_unit

        # The break point has always the same dimension as the x variable
        self.xc.unit = x_unit

        self.piv.unit = x_unit

        # alpha and beta are dimensionless
        self.alpha.unit = astropy_units.dimensionless_unscaled
        self.beta.unit = astropy_units.dimensionless_unscaled

    def evaluate(self, x, K, alpha, xc, beta, piv):

        if (alpha < beta):
            raise ModelAssertionViolation("Alpha cannot be less than beta")

        idx = x < (alpha - beta) * xc

        # The K * 0 part is a trick so that out will have the right units (if the input
        # has units)

        out = np.zeros(x.shape) * K * 0

        out[idx] = K * np.power(old_div(x[idx], piv),
                                alpha) * np.exp(old_div(-x[idx], xc))
        out[~idx] = K * np.power((alpha - beta) * xc / piv, alpha - beta) * np.exp(beta - alpha) * \
            np.power(old_div(x[~idx], piv), beta)

        return out


@six.add_metaclass(FunctionMeta)
class Band_Calderone(Function1D):
    r"""
    description :

        The Band model from Band et al. 1993, implemented however in a way which reduces the covariances between
        the parameters (Calderone et al., MNRAS, 448, 403C, 2015)

    latex : $ \text{(Calderone et al., MNRAS, 448, 403C, 2015)} $

    parameters :

        alpha :
            desc : The index for x smaller than the x peak
            initial value : -1
            min : -10
            max : 10

        beta :

            desc : index for x greater than the x peak (only if opt=1, i.e., for the
                   Band model)
            initial value : -2.2
            min : -7
            max : -1

        xp :

            desc : position of the peak in the x*x*f(x) space (if x is energy, this is the nuFnu or SED space)
            initial value : 200.0
            min : 0

        F :

            desc : integral in the band defined by a and b
            initial value : 1e-6
            is_normalization : True

        a:

            desc : lower limit of the band in which the integral will be computed
            initial value : 1.0
            min : 0
            fix : yes

        b:

            desc : upper limit of the band in which the integral will be computed
            initial value : 10000.0
            min : 0
            fix : yes

        opt :

            desc : option to select the spectral model (0 corresponds to a cutoff power law, 1 to the Band model)
            initial value : 1
            min : 0
            max : 1
            fix : yes

    """

    def _set_units(self, x_unit, y_unit):

        # alpha and beta are always unitless

        self.alpha.unit = astropy_units.dimensionless_unscaled
        self.beta.unit = astropy_units.dimensionless_unscaled

        # xp has the same dimension as x
        self.xp.unit = x_unit

        # F is the integral over x, so it has dimensions y_unit * x_unit
        self.F.unit = y_unit * x_unit

        # a and b have the same units of x
        self.a.unit = x_unit
        self.b.unit = x_unit

        # opt is just a flag, and has no units
        self.opt.unit = astropy_units.dimensionless_unscaled

    @staticmethod
    def ggrb_int_cpl(a, Ec, Emin, Emax):

        # Gammaincc does not support quantities
        i1 = gammaincc(2 + a, old_div(Emin, Ec)) * gamma(2 + a)
        i2 = gammaincc(2 + a, old_div(Emax, Ec)) * gamma(2 + a)

        return -Ec * Ec * (i2 - i1)

    @staticmethod
    def ggrb_int_pl(a, b, Ec, Emin, Emax):

        pre = pow(a - b, a - b) * math.exp(b - a) / pow(Ec, b)

        if b != -2:

            return pre / (2 + b) * (pow(Emax, 2 + b) - pow(Emin, 2 + b))

        else:

            return pre * math.log(old_div(Emax, Emin))

    def evaluate(self, x, alpha, beta, xp, F, a, b, opt):

        assert opt == 0 or opt == 1, "Opt must be either 0 or 1"

        if alpha < beta:
            raise ModelAssertionViolation("Alpha cannot be smaller than beta")

        if alpha < -2:
            raise ModelAssertionViolation("Alpha cannot be smaller than -2")

        # Cutoff energy

        if alpha == -2:

            Ec = old_div(xp, 0.0001)  # TRICK: avoid a=-2

        else:

            Ec = old_div(xp, (2 + alpha))

        # Split energy

        Esplit = (alpha - beta) * Ec

        # Evaluate model integrated flux and normalization

        if isinstance(alpha, astropy_units.Quantity):

            # The following functions do not allow the use of units
            alpha_ = alpha.value
            Ec_ = Ec.value
            a_ = a.value
            b_ = b.value
            Esplit_ = Esplit.value
            beta_ = beta.value

            unit_ = self.x_unit

        else:

            alpha_, Ec_, a_, b_, Esplit_, beta_ = alpha, Ec, a, b, Esplit, beta
            unit_ = 1.0

        if opt == 0:

            # Cutoff power law

            intflux = self.ggrb_int_cpl(alpha_, Ec_, a_, b_)

        else:

            # Band model

            if a <= Esplit and Esplit <= b:

                intflux = (self.ggrb_int_cpl(alpha_, Ec_, a_, Esplit_) +
                           self.ggrb_int_pl(alpha_, beta_, Ec_, Esplit_, b_))

            else:

                if Esplit < a:

                    intflux = self.ggrb_int_pl(alpha_, beta_, Ec_, a_, b_)

                else:

                    raise RuntimeError("Esplit > emax!")

        erg2keV = 6.24151e8

        norm = F * erg2keV / (intflux * unit_)

        if opt == 0:

            # Cutoff power law

            flux = norm * np.power(old_div(x, Ec), alpha) * \
                np.exp(old_div(- x, Ec))

        else:

            # The norm * 0 is to keep the units right

            flux = np.zeros(x.shape) * norm * 0

            idx = x < Esplit

            flux[idx] = norm * \
                np.power(old_div(x[idx], Ec), alpha) * \
                np.exp(old_div(-x[idx], Ec))
            flux[~idx] = norm * pow(alpha - beta, alpha - beta) * \
                math.exp(beta - alpha) * np.power(old_div(x[~idx], Ec), beta)

        return flux


@six.add_metaclass(FunctionMeta)
class Log_parabola(Function1D):
    r"""
    description :

        A log-parabolic function. NOTE that we use the high-energy convention of using the natural log in place of the
        base-10 logarithm. This means that beta is a factor 1 / log10(e) larger than what returned by those software
        using the other convention.

    latex : $ K \left( \frac{x}{piv} \right)^{\alpha -\beta \log{\left( \frac{x}{piv} \right)}} $

    parameters :

        K :

            desc : Normalization
            initial value : 1.0
            is_normalization : True
            transformation : log10
            min : 1e-30
            max : 1e5

        piv :
            desc : Pivot (keep this fixed)
            initial value : 1
            fix : yes

        alpha :

            desc : index
            initial value : -2.0

        beta :

            desc : curvature (positive is concave, negative is convex)
            initial value : 1.0

    """

    def _set_units(self, x_unit, y_unit):

        # K has units of y

        self.K.unit = y_unit

        # piv has the same dimension as x
        self.piv.unit = x_unit

        # alpha and beta are dimensionless
        self.alpha.unit = astropy_units.dimensionless_unscaled
        self.beta.unit = astropy_units.dimensionless_unscaled

    def evaluate(self, x, K, piv, alpha, beta):

        #print("Receiving %s" % ([K, piv, alpha, beta]))

        xx = np.divide(x, piv)

        try:

            return K * xx ** (alpha - beta * np.log(xx))

        except ValueError:

            # The current version of astropy (1.1.x) has a bug for which quantities that have become
            # dimensionless because of a division (like xx here) are not recognized as such by the power
            # operator, which throws an exception: ValueError: Quantities and Units may only be raised to a scalar power
            # This is a quick fix, waiting for astropy 1.2 which will fix this

            xx = xx.to('')

            return K * xx ** (alpha - beta * np.log(xx))

    @property
    def peak_energy(self):
        """
        Returns the peak energy in the nuFnu spectrum

        :return: peak energy in keV
        """

        # Eq. 6 in Massaro et al. 2004
        # (http://adsabs.harvard.edu/abs/2004A%26A...413..489M)

        return self.piv.value * pow(10, old_div(((2 + self.alpha.value) * np.log(10)), (2 * self.beta.value)))


if has_gsl:
    @six.add_metaclass(FunctionMeta)
    class Cutoff_powerlaw_flux(Function1D):
        r"""
            description :

                A cutoff power law having the flux as normalization, which should reduce the correlation among
                parameters.

            latex : $ \frac{F}{T(b)-T(a)} ~x^{index}~\exp{(-x/x_{c})}~\text{with}~T(x)=-x_{c}^{index+1} \Gamma(index+1, x/C)~\text{(}\Gamma\text{ is the incomplete gamma function)} $

            parameters :

                F :

                    desc : Integral between a and b
                    initial value : 1e-5
                    is_normalization : True

                index :

                    desc : photon index
                    initial value : -2.0

                xc :

                    desc : cutoff position
                    initial value : 50.0

                a :

                    desc : lower bound for the band in which computing the integral F
                    initial value : 1.0
                    fix : yes

                b :

                    desc : upper bound for the band in which computing the integral F
                    initial value : 100.0
                    fix : yes
            """

        def _set_units(self, x_unit, y_unit):
            # K has units of y * x
            self.F.unit = y_unit * x_unit

            # alpha is dimensionless
            self.index.unit = astropy_units.dimensionless_unscaled

            # xc, a and b have the same dimension as x
            self.xc.unit = x_unit
            self.a.unit = x_unit
            self.b.unit = x_unit

        @staticmethod
        def _integral(a, b, index, ec):
            ap1 = index + 1

            def integrand(x): return -pow(ec, ap1) * \
                gamma_inc(ap1, old_div(x, ec))

            return integrand(b) - integrand(a)

        def evaluate(self, x, F, index, xc, a, b):
            this_integral = self._integral(a, b, index, xc)

            return F / this_integral * np.power(x, index) * np.exp(-1 * np.divide(x, xc))


@six.add_metaclass(FunctionMeta)
class Exponential_cutoff(Function1D):
    r"""
        description :

            An exponential cutoff

        latex : $ K \exp{(-x/xc)} $

        parameters :

            K :

                desc : Normalization
                initial value : 1.0
                fix : no
                is_normalization : True

            xc :
                desc : cutoff
                initial value : 100
                min : 1
        """

    def _set_units(self, x_unit, y_unit):
        # K has units of y

        self.K.unit = y_unit

        # piv has the same dimension as x
        self.xc.unit = x_unit

    def evaluate(self, x, K, xc):
        return K * np.exp(np.divide(x, -xc))


if has_ebltable:
    @six.add_metaclass(FunctionMeta)
    class EBLattenuation(Function1D):
        r"""
        description :
            Attenuation factor for absorption in the extragalactic background light (EBL) ,
            to be used for extragalactic source spectra. Based on package "ebltable" by
            Manuel Meyer, https://github.com/me-manu/ebltable .

        latex: not available

        parameters :

          redshift :
                desc : redshift of the source
                initial value : 1.0
                fix : yes
        """

        def _setup(self):

            # define EBL model, use dominguez as default
            self._tau = ebltau.OptDepth.readmodel(model='dominguez')

        def set_ebl_model(self, modelname):

            # passing modelname to ebltable, which will check if defined
            self._tau = ebltau.OptDepth.readmodel(model=modelname)

        def _set_units(self, x_unit, y_unit):

            if not hasattr(x_unit, "physical_type") or x_unit.physical_type != 'energy':

                # x should be energy
                raise InvalidUsageForFunction("Unit for x is not an energy. The function "
                                              "EBLOptDepth calculates energy-dependent "
                                              "absorption.")

            # y should be dimensionless
            if not hasattr(y_unit, 'physical_type') or \
                    y_unit.physical_type != 'dimensionless':
                raise InvalidUsageForFunction(
                    "Unit for y is not dimensionless.")

            self.redshift.unit = astropy_units.dimensionless_unscaled

        def evaluate(self, x, redshift):

            if isinstance(x, astropy_units.Quantity):

                # ebltable expects TeV
                eTeV = x.to(astropy_units.TeV).value
                return np.exp(-self._tau.opt_depth(redshift.value, eTeV)) * astropy_units.dimensionless_unscaled

            else:

                # otherwise it's in keV
                eTeV = old_div(x, 1e9)
                return np.exp(-self._tau.opt_depth(redshift, eTeV))
