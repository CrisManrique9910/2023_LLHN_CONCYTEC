import sys
import matplotlib.pyplot as plt
import numpy as np
import re
import glob
import pandas as pd
from scipy.interpolate import interp1d
from my_funcs import isolation, get_mass_width

from pathlib import Path

mu_eff_pt = pd.read_csv('./data/muon_eff_pt.csv',header=0)
el_eff_pt = pd.read_csv('./data/electron_eff_pt.csv',header=0)
el_eff_eta = pd.read_csv('./data/electron_eff_eta.csv',header=0)
cutflow_path = "./data/clean/cutflow/"
el_normal_factor = 1/0.85
m_Z = 91.1876 #GeV

np.random.seed(0)
mu_func = interp1d(mu_eff_pt.pt,mu_eff_pt.eff, fill_value=tuple(mu_eff_pt.eff.iloc[[0,-1]]), bounds_error=False)
el_pt_func = interp1d(el_eff_pt.BinLeft,el_eff_pt.Efficiency, fill_value=tuple(el_eff_pt.Efficiency.iloc[[0,-1]]),
                      bounds_error=False,kind='zero')
el_eta_func = interp1d(el_eff_eta.BinLeft,el_eff_eta.Efficiency, fill_value=tuple(el_eff_eta.Efficiency.iloc[[0,-1]]),
                      bounds_error=False,kind='zero')

types = ['ZH', "WH", "TTH"]
tevs = [13]

for tev in tevs[:]:
    mismatches1 = []
    mismatches2 = []
    for type in types[:]:
        origin = f"./data/bins/{tev}/{type}/"
        destiny = f"./data/bins/{tev}/{type}/"
        files_in = glob.glob(origin + f"*{type}*{tev}*photons.pickle")
        bases = sorted(list(set([re.search(f'/.*({type}.+)-df', x).group(1) for x in files_in])))
        cutflows = dict()

        for base_out in bases[:]:

            destiny_info = f'./data/clean/'
            folder_txt = f"./cases/{tev}/{type}/"
            mismatch_data = {'1_total': 0, '1_to_2+': 0,'2+_total': 0, '2+_to_1': 0,
                             '1_to_2+-survived': 0, '2+_to_1-survived': 0}
            dfs = {'1': '','2+': ''}
            scale = 1.

            print(f'RUNNING: {base_out}')

            for input_file in sorted(glob.glob(origin + f'*{base_out}*_photons.pickle'))[:]:
                photons = pd.read_pickle(input_file)
                leptons = pd.read_pickle(input_file.replace('photons', 'leptons'))
                jets = pd.read_pickle(input_file.replace('photons', 'jets'))
                #print(photons)

                if leptons.size == 0:
                    continue

                ### Applying efficiencies
                leptons.loc[(leptons.pdg==11),'eff_value'] = \
                    leptons[leptons.pdg==11].apply(lambda row:
                                                   el_normal_factor*el_pt_func(row.pt)*el_eta_func(row.eta), axis=1)

                leptons.loc[(leptons.pdg == 13), 'eff_value'] = \
                    leptons[leptons.pdg == 13].apply(lambda row: mu_func(row.pt), axis=1)

                leptons['detected'] = leptons.apply(lambda row: np.random.random_sample() < row['eff_value'], axis=1)

                leptons = leptons[leptons.detected]
                #print(leptons)

                ## Overlapping
                ### Primero electrones
                leptons.loc[(leptons.pdg==11),'el_iso_ph'] = isolation(leptons[leptons.pdg==11],photons,'pt',same=False,dR=0.4)
                leptons = leptons[(leptons.pdg==13)|(leptons['el_iso_ph']==0)]

                ## Luego jets
                jets['jet_iso_ph'] = isolation(jets,photons,'pt',same=False,dR=0.4)
                jets['jet_iso_e'] = isolation(jets, leptons[leptons.pdg==11], 'pt', same=False, dR=0.2)
                jets = jets[jets['jet_iso_e'] + jets['jet_iso_ph']==0]

                ## Electrones de nuevo
                leptons.loc[(leptons.pdg == 11), 'el_iso_j'] = isolation(leptons[leptons.pdg == 11], jets, 'pt', same=False,
                                                                          dR=0.4)
                leptons = leptons[(leptons.pdg == 13) | (leptons['el_iso_j'] == 0)]

                ## Finalmente, muones
                jets['jet_iso_mu'] = isolation(jets, leptons[leptons.pdg == 13], 'pt', same=False, dR=0.01)
                jets = jets[jets['jet_iso_mu'] == 0]

                leptons.loc[(leptons.pdg == 13), 'mu_iso_j'] = isolation(leptons[leptons.pdg == 13], jets, 'pt', same=False,
                                                                         dR=0.4)
                leptons.loc[(leptons.pdg == 13), 'mu_iso_ph'] = isolation(leptons[leptons.pdg == 13], photons, 'pt', same=False,
                                                                         dR=0.4)
                leptons = leptons[(leptons.pdg == 11) | ((leptons['mu_iso_j'] + leptons['mu_iso_ph']) == 0)]

                ##### De ahí leptones con pt > 27
                leptons = leptons[leptons.pt > 27]
                #print(leptons)

                ### Invariant mass
                photons0 = photons.groupby(['N']).nth(0)
                photons0['px'] = photons0.pt * np.cos(photons0.phi)
                photons0['py'] = photons0.pt * np.sin(photons0.phi)
                photons0['pz'] = photons0.pt / np.tan(2 * np.arctan(np.exp(photons0.eta)))
                photons0 = photons0[['E', 'px', 'py', 'pz']]

                leptons0 = leptons.groupby(['N']).nth(0)
                leptons0['px'] = leptons0.pt * np.cos(leptons0.phi)
                leptons0['py'] = leptons0.pt * np.sin(leptons0.phi)
                leptons0['pz'] = leptons0.pt / np.tan(2 * np.arctan(np.exp(leptons0.eta)))
                leptons0['E'] = np.sqrt(leptons0.mass**2 + leptons0.pt**2 + leptons0.pz**2)
                leptons0 = leptons0[['E','px','py','pz','pdg']]

                final_particles = photons0.join(leptons0,how='inner',lsuffix='_ph',rsuffix='_l')
                final_particles['M_eg'] = np.sqrt((final_particles.E_ph + final_particles.E_l) ** 2 -
                                ((final_particles.px_ph + final_particles.px_l) ** 2 +
                                 (final_particles.py_ph + final_particles.py_l) ** 2 +
                                 (final_particles.pz_ph + final_particles.pz_l) ** 2))
                final_particles = final_particles[(final_particles.pdg == 13) | (np.abs(final_particles.M_eg - m_Z) > 15)]
                #print(len(photons))
                if 'All' not in input_file:
                    photons = photons[photons.index.get_level_values(0).isin(
                        list(final_particles.index.get_level_values(0)))]

                    name_base = re.search(f'/.*({type}.+)-df', input_file).group(1)
                    dataset = re.search(f'/.*df(.+?)_', input_file).group(1)
                    tsign = re.search(f'/.*_(.+?)_photons', input_file).group(1)
                    z = re.search(f'/.*_z(.+?)_', input_file).group(1)
                    t = re.search(f'/.*_t(.+?)_', input_file).group(1)
                    preDelphes_file = f'./data/clean/df_photon_smeared_{dataset}-{name_base}_{tsign}.pickle'
                    preDelphes = pd.read_pickle(preDelphes_file)
                    preDelphes = preDelphes[(preDelphes.z_binned == int(z)) & (preDelphes.t_binned == int(t))]
                    preDelphes = preDelphes.groupby(['Event']).nth(0)


                    ### ver cuales no cumplen con su label
                    if 'df1' in input_file:
                        nums = photons.groupby(['N']).size()
                        mismatch_data['1_total'] += nums.shape[0]
                        mismatch_data['1_to_2+'] += nums[nums > 1].shape[0]
                        #if nums[nums > 1].shape[0] == 0:
                        #    continue
                        outliers = photons.groupby(['N']).nth(0)[nums > 1]
                        outliers = outliers[['pt']].join(preDelphes[['pt']], how='inner', lsuffix='_AD', rsuffix='_BD')
                        outliers = outliers[np.isclose(outliers.pt_AD,outliers.pt_BD,rtol=0.1,atol=0.)]
                        #print(outliers.shape[0])
                        mismatch_data['1_to_2+-survived'] += outliers.shape[0]
                    elif 'df2+' in input_file:
                        nums = photons.groupby(['N']).size()
                        mismatch_data['2+_total'] += nums.shape[0]
                        mismatch_data['2+_to_1'] += nums[nums == 1].shape[0]
                        #if nums[nums == 1].shape[0] == 0:
                        #    continue
                        outliers = photons.groupby(['N']).nth(0)[nums == 1]
                        outliers = outliers[['pt']].join(preDelphes[['pt']], how='inner', lsuffix='_AD', rsuffix='_BD')
                        outliers = outliers[np.isclose(outliers.pt_AD,outliers.pt_BD,rtol=0.1,atol=0.)]
                        #print(outliers.shape[0])
                        mismatch_data['2+_to_1-survived'] += outliers.shape[0]
                    #print()
                    #print(len(photons))
                    #sys.exit()

            stats = get_mass_width(base_out)
            mismatches1.append({'type':type, 'mass': stats['M'], 'width': stats['W'],
                '1_total': mismatch_data['1_total'],
                '1_to_2+_%': np.around(100*mismatch_data['1_to_2+']/mismatch_data['1_total'],2),
                '1_to_2+': mismatch_data['1_to_2+'],
                '1_to_2+_survived_%': np.around(100 * np.divide(mismatch_data['1_to_2+-survived'],mismatch_data['1_to_2+']), 2),
                '1_to_2+_survived': mismatch_data['1_to_2+-survived']})

            mismatches2.append({'type': type, 'mass': stats['M'], 'width': stats['W'],
                                '2+_total': mismatch_data['2+_total'],
                                '2+_to_1_%': np.around(100 * mismatch_data['2+_to_1'] / mismatch_data['2+_total'], 2),
                                '2+_to_1': mismatch_data['2+_to_1'],
                                '2+_to_1_survived_%': np.around(
                                    100 * np.divide(mismatch_data['2+_to_1-survived'], mismatch_data['2+_to_1']), 2),
                                '2+_to_1_survived': mismatch_data['2+_to_1-survived']})

            #print(mismatches)
            #sys.exit()

    with pd.ExcelWriter(cutflow_path + 'photon_df_mismataches.xlsx') as writer:
        pd.DataFrame(mismatches1).to_excel(writer, sheet_name="1 to 2+")
        pd.DataFrame(mismatches2).to_excel(writer, sheet_name="2+ to 1")

