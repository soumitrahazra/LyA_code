import trajectory_tail_cartesian_new as ttc
import do_transit_new as dt
import config as config
import numpy as np
import constants_new as const
import LyA_transit_datatypes_new as LyA
import matplotlib.pyplot as plt
import Observation_new_v2.chi2_gj436 as obs
import xsection_new as xs
import constants_new as const


def evaluate_log_prior(lp, constant_parameters):
    """
    Parameters
    --------------------


    Returns
    --------------------
    """
    #calculate energy limited mass loss rate

    F_XUV = 10**lp['L_EUV'] / (4 * np.pi * constant_parameters['semimajoraxis']**2)
    energy_limited_mlr = np.pi * F_XUV * constant_parameters['radius_p']**3 / (const.G * constant_parameters['mass_p'])
    #first check and calculate prior

    #uniform(and log uniform priors)
    if 5.2 <= lp['c_s_planet'] <= 6.5\
    and 8 <= lp['mdot_planet'] <= np.log10(energy_limited_mlr)\
    and 6.5 <= lp['v_stellar_wind'] <= 8\
    and 10.3 <= lp['mdot_star'] <= 13\
    and 26 <= lp['L_EUV'] <= 29\
    and np.pi/2 <= lp['angle'] <= np.pi:
    #and 0.01 <= lp['L_mix'] <= 0.1\
    #and 6.4 <= lp['u_ENA'] <= 8:

        #gaussian priors
        mu = 1.51
        sigma = 0.02
        lp_val = - 0.5 * ((lp['inclination'] - mu)**2 / sigma **2 + np.log(2 * np.pi * sigma**2))

        return lp_val

    else:

        return -np.inf


def convert_to_linspace(dic):
    new_dict = {}
    for key in dic:
        if key == 'angle' or key == 'inclination' or key == 'L_mix':
            new_dict[key] = dic[key]
        else:
            new_dict[key] = 10**dic[key]
    return new_dict


def make_log_posterior_fn(constant_parameters, only_blue = False, weight_fluxes = False):
    """
    Parameters
    ------------------
    constant_parameters :

    config:

    Returns
    ------------------
    evaluate_posterior : the
    """
    #make comparison to obs fnctn
    vgrid = np.concatenate((np.arange(-1e8, -4e7, 4e6), np.arange(-4e7, 4e7, 1e5), np.arange(4e7, 1.04e8, 4e6)))  #(-1000 km/s, 1000 km/s)                                               #-1000km/s to 1000km/s
    wavgrid = (1 + np.asarray(vgrid) / const.c) * 1215.67                           #IN ANGSTROMS! (Not CGS)
    wgrid = (1 - np.asarray(vgrid) / const.c) * const.LyA_linecenter_w              #IN

    tgrid = np.concatenate((np.linspace(0.8, 10, 23), np.linspace(25.2, 31.5, 18))) #IN HOURS
    phasegrid = tgrid * np.sqrt(constant_parameters['mass_s'] * const.G / constant_parameters['semimajoraxis']**3) * 3600 + np.pi/2

    oot_profile, oot_data, transit_data, simulate_spectra, get_lightcurves, compute_chi2, compute_logL = obs.make_transit_chi2_tools(wavgrid, tgrid)

    #make transit fnct
    do_transit = dt.make_transit_tools(constant_parameters['radius_s'], 15)
    #stellar r cells is 15
    #z cells variable

    def evaluate_posterior(mcmc_log_parameters):

        ###
        parameters = {**constant_parameters, **convert_to_linspace(mcmc_log_parameters)}
        star = LyA.Star(mass = parameters['mass_s'], radius = parameters['radius_s'])
        planet = LyA.Planet(mass = parameters['mass_p'], radius = parameters['radius_p'], semimajoraxis = parameters['semimajoraxis'], inclination = parameters['inclination'])
        model_parameters = LyA.ModelParameters(c_s_planet = parameters['c_s_planet'], mdot_planet = parameters['mdot_planet'], v_stellar_wind = parameters['v_stellar_wind'], mdot_star = parameters['mdot_star'], T_stellar_wind = parameters['T_stellar_wind'], L_EUV = parameters['L_EUV'], angle = parameters['angle'])

        #make_density_structure
        rho_struc = config.make_rho_struc(parameters)

        #make_ENA_structure
        #ENA = config.make_ENA(parameters)

        #evaluate prior
        logP = evaluate_log_prior(mcmc_log_parameters, constant_parameters)

        if logP == -np.inf:
            return -np.inf

        else:
            try:
                tail_solution_cartesian = ttc.trajectory_solution_cartesian(star, planet, model_parameters, rho_struc)
            except (ValueError, RuntimeWarning):
                logging.exception(f"the parameters are {str(model_parameters)}")
                return -np.inf
            else:
                if tail_solution_cartesian.success == False: #if solution no found assume parameters unreasonable
                    return -np.inf
                elif tail_solution_cartesian.t_events[1].size: #check if stopped by epicycle event
                    return -np.inf
                else:
                    tail = ttc.trajectory_solution_polar(star, planet, model_parameters, rho_struc)
                    phase, model_intensity = do_transit(tail, phasegrid, wgrid, rho_struc, parameters['inclination'])
                    logL = compute_logL(1 - model_intensity, only_blue = only_blue, weight_fluxes = weight_fluxes)
                    logPosterior = logL + logP
                    return logPosterior


    return evaluate_posterior
