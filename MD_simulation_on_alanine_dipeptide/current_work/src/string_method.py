from ANN_simulation import *

class String_method_1(object):  # with autoencoder approach
    def __init__(self, num_iterations, num_images=None):
        self._num_iterations = num_iterations
        self._num_images = num_images
        return

    def get_images_and_write_into_a_pdb_file(self, folder_containing_data_in_previous_iteration,
                                             autoencoder_filename, num_images, new_pdb_file_name='temp_new.pdb',
                                             scaling_factor=CONFIG_49):
        _1 = coordinates_data_files_list([folder_containing_data_in_previous_iteration])
        _1 = _1.create_sub_coor_data_files_list_using_filter_conditional(lambda x: not 'aligned' in x)
        coor_data = Sutils.remove_translation(_1.get_coor_data(scaling_factor=scaling_factor))
        temp_autoencoder = autoencoder.load_from_pkl_file(autoencoder_filename)
        assert (isinstance(temp_autoencoder, autoencoder))
        PCs = temp_autoencoder.get_PCs(coor_data)
        image_params = np.linspace(PCs.min(), PCs.max(), num_images + 2)
        index_list_of_images = [(np.abs(PCs - temp_image_param)).argmin() for temp_image_param in image_params]
        print index_list_of_images, PCs[index_list_of_images].flatten(), image_params.flatten()
        if os.path.exists(new_pdb_file_name):
            subprocess.check_output(['rm', new_pdb_file_name])

        concat_pdb_file = 'temp_concat_pdb_file.pdb'  # this file is used to preserve order of pdb file frames based on index_list_of_images,
                                            # order cannot be preserved with write_some_frames_into_a_new_file_based_on_index_list_for_pdb_file_list()
                                            # so we use write_some_frames_into_a_new_file_based_on_index_list() instead
        _1.concat_all_pdb_files(concat_pdb_file)
        Sutils.write_some_frames_into_a_new_file_based_on_index_list(
            pdb_file_name=concat_pdb_file,index_list=index_list_of_images,
            new_pdb_file_name=new_pdb_file_name
        )
        # following is assertion part
        temp_coor_file = molecule_type.generate_coordinates_from_pdb_files(new_pdb_file_name)[0]
        _2 = coordinates_data_files_list([temp_coor_file])
        coor_data = Sutils.remove_translation(_2.get_coor_data(scaling_factor=scaling_factor))
        expected = PCs[index_list_of_images]; actual = temp_autoencoder.get_PCs(coor_data)
        print "actual = %s" % str(actual.flatten())
        assert_almost_equal(expected, actual, decimal=4)   # TODO: order is not preserved, fix this later
        return new_pdb_file_name

    def reparametrize(self, folder_containing_data_in_previous_iteration, index, num_images):
        iteration.preprocessing(target_folder=folder_containing_data_in_previous_iteration)  # structural alignment and generate coordinate files
        temp_output = subprocess.check_output(['python', '../src/train_network_and_save_for_iter.py', str(index),
                                 '--data_folder', folder_containing_data_in_previous_iteration,
                                 '--num_PCs', '1'
                                 ])
        print temp_output
        autoencoder_filename = temp_output.strip().split('\n')[-1]
        new_pdb_file_name = self.get_images_and_write_into_a_pdb_file(folder_containing_data_in_previous_iteration,
                                             autoencoder_filename, num_images)
        return new_pdb_file_name

    def relax_using_multiple_images_contained_in_a_pdb(self, output_folder, pdb_file):
        command_list = []
        for item in range(Universe(pdb_file).trajectory.n_frames):
            for temp_index in range(10):
                command = ['python', '../src/biased_simulation_general.py', '2src',
                             '1', '10', '0', output_folder, 'none', 'pc_0,%d' % item,
                             'explicit', 'NPT', '--platform', 'CUDA',
                             '--starting_pdb_file', pdb_file, '--starting_frame', str(item),
                             '--temperature', '0', '--equilibration_steps', '0',
                             '--minimize_energy', '0']
                command = ['python', '../src/biased_simulation.py',
                           '2', '50', '0', output_folder, 'none', 'pc_%d,%d' % (item, temp_index),
                           '--platform', 'CPU',
                           '--starting_pdb_file', pdb_file, '--starting_frame', str(item),
                           '--temperature', '0', '--equilibration_steps', '0',
                           '--minimize_energy', '0']
                print ' '.join(command)
                command_list.append(command)
                subprocess.check_output(command)
        return

    def run_iteration(self, data_folder, index, num_images, output_folder=None):
        new_pdb_file_name = self.reparametrize(data_folder, index=index, num_images=num_images)
        if output_folder is None:
            output_folder = '../target/' + CONFIG_30 + '/string_method_%04d' % (index)

        self.relax_using_multiple_images_contained_in_a_pdb(output_folder, new_pdb_file_name)
        molecule_type.generate_coordinates_from_pdb_files(output_folder)
        return output_folder

    def run_multiple_iterations(self, start_data_folder, start_index=1, num_iterations=None, num_images=None):
        if num_iterations is None:
            num_iterations = self._num_iterations
        if num_images is None:
            num_images = self._num_images

        current_data_folder = start_data_folder
        for item in range(start_index, num_iterations + start_index):
            current_data_folder = self.run_iteration(current_data_folder, item, num_images=num_images)
            print "iteration %d for string method done!" %(item)
        return


class String_method(object):
    def __init__(self, selected_atom_indices, ref_pdb,
                 num_of_simulations_for_each_image,
                 num_steps_of_unbiased_MD,
                 num_steps_of_restrained_MD,
                 num_steps_of_equilibration,
                 step_interval,
                 num_snapshots_for_calculating_average_positions,
                 smooth_coeff=0.5):
        """
        :param selected_atom_indices: atoms used to define configuration and apply restrained MD
        :param ref_pdb: reference pdb file for structural alignment
        """
        self._selected_atom_indices = selected_atom_indices  # index start from 1
        self._ref_pdb = ref_pdb
        self._num_steps_of_unbiased_MD = num_steps_of_unbiased_MD
        self._num_steps_of_equilibration = num_steps_of_equilibration
        self._num_steps_of_restrained_MD = num_steps_of_restrained_MD
        self._num_of_simulations_for_each_image = num_of_simulations_for_each_image
        self._num_snapshots_for_calculating_average_positions = num_snapshots_for_calculating_average_positions
        self._step_interval = step_interval
        self._smooth_coeff = smooth_coeff
        return

    def reparametrize_and_get_images_using_interpolation(self, positions_list,
                                                         smooth_coeff = None):
        # smoothing
        if smooth_coeff is None:
            smooth_coeff = self._smooth_coeff
        temp_positions_list = (1 - smooth_coeff) * positions_list[1:-1]\
                    + smooth_coeff / 2 * (positions_list[:-2] + positions_list[2:])
        positions_list[1:-1] = temp_positions_list
        # re-parametrization
        temp_cumsum = np.cumsum([np.linalg.norm(positions_list[item + 1] - positions_list[item])
                   for item in range(len(positions_list) - 1)])
        temp_cumsum = np.insert(temp_cumsum, 0, 0)
        arc_length_interval = temp_cumsum[-1] / (len(positions_list) - 1)
        current_image_param = 0
        positions_of_images = []
        for item in range(len(positions_list) - 1):
            while current_image_param < temp_cumsum[item + 1]:
                temp_arc_length = temp_cumsum[item + 1] - temp_cumsum[item]
                weight_0 = (temp_cumsum[item + 1] - current_image_param) / temp_arc_length
                weight_1 = (current_image_param - temp_cumsum[item]) / temp_arc_length
                positions_of_images.append(positions_list[item] * weight_0
                                           + positions_list[item + 1] * weight_1)
                current_image_param += arc_length_interval

        if len(positions_of_images) == len(positions_list) - 1:  # deal with rounding error at end point
            positions_of_images.append(positions_list[-1])

        assert (len(positions_of_images) == len(positions_list)), (len(positions_of_images), len(positions_list))
        return np.array(positions_of_images), temp_cumsum

    def get_aligned_positions_of_selected_atoms_from_pdb_file(self, pdb_file):
        if not '_aligned.pdb' in pdb_file:
            pdb_file_aligned = pdb_file.replace('.pdb', '_aligned.pdb')
        else:
            pdb_file_aligned = pdb_file

        temp_sample = Universe(pdb_file_aligned)
        temp_positions = [temp_sample.atoms.positions[np.array(self._selected_atom_indices) - 1].flatten()
                          for _ in temp_sample.trajectory]
        return temp_positions

    def get_node_positions_from_initial_string(self, pdb_file, num_intervals):
        """note number of images = num_intervals + 1"""
        temp_positions = self.get_aligned_positions_of_selected_atoms_from_pdb_file(pdb_file)
        step_interval = len(temp_positions) / num_intervals
        result = temp_positions[::step_interval]
        if len(result) == num_intervals:
            result.append(temp_positions[-1])
        assert (len(result) == num_intervals + 1)
        return np.array(result)

    def get_aligned_pdb_list_list_of_nodes_from_a_folder(self, folder):
        result = []
        item = 0
        while True:
            temp_result = subprocess.check_output(
                ['find', folder, '-name', 'temp_string_%04d*_aligned.pdb' % item]).strip().split()
            if len(temp_result) == 0: break
            else:
                result.append(temp_result)
                item += 1
        return result

    def generate_pdb_list_list_from_a_single_pdb_file_containing_string(self, pdb_file, num_intervals,
                                                                        output_file_folder):
        """this is used when the string is stored in a single pdb file, it generates pdb files for different nodes.
        Note that nodes are different from images, nodes are used to generate positions list, which is then used
        to reparametrize and generate corresponding images,
        :param output_file_folder: used to store generated files
        """
        if not os.path.exists(output_file_folder):
            subprocess.check_output(['mkdir', output_file_folder])

        num_frames = Universe(pdb_file).trajectory.n_frames
        num_frames_per_pdb = num_frames / num_intervals
        temp_new_pdb_file_names = [output_file_folder + '/temp_string_%04d_%04d.pdb' % (index, 0)
                                   for index in range(num_intervals + 1)]
        for index in range(1, num_intervals + 1):
            Sutils.write_some_frames_into_a_new_file_based_on_index_list(pdb_file_name=pdb_file,
                    index_list=range((index - 1) * num_frames_per_pdb, index * num_frames_per_pdb),
                    new_pdb_file_name=temp_new_pdb_file_names[index], overwrite=True)
        Sutils.write_some_frames_into_a_new_file_based_on_index_list(pdb_file_name=pdb_file,
                                             index_list=range(10),  # pick first few frames
                                             new_pdb_file_name=temp_new_pdb_file_names[0],
                                             overwrite=True
                                             )
        print [Universe(item).trajectory.n_frames for item in temp_new_pdb_file_names]
        self.remove_water_and_align('../target/' + CONFIG_30)
        return temp_new_pdb_file_names

    def get_average_node_positions_of_string(self, pdb_file_list_list, num_snapshots):
        average_positions_list = []
        for item_pdb_file_list in pdb_file_list_list:
            temp_average = [np.average(
                self.get_aligned_positions_of_selected_atoms_from_pdb_file(item_pdb_file)[-num_snapshots:],
                axis=0) for item_pdb_file in item_pdb_file_list]
            temp_average = np.average(temp_average, axis=0)
            assert (temp_average.shape[0] == 3 * len(self._selected_atom_indices)), temp_average.shape[0]
            average_positions_list.append(temp_average)
        return np.array(average_positions_list)

    def remove_water_and_align(self, target_folder, machine_to_run_simulations=CONFIG_24):
        Sutils.remove_water_mol_and_Cl_from_pdb_file(target_folder, preserve_original_file=False)
        temp_command_list = ['python', '../src/structural_alignment.py',
                             target_folder, '--ref', self._ref_pdb,
                             '--atom_selection', 'backbone'  # TODO: is it good to use backbone?
                             ]
        # TODO: refactor following into a function later and include remove water
        if machine_to_run_simulations == 'local':
            subprocess.check_output(temp_command_list)
        elif machine_to_run_simulations == 'cluster':
            temp_command = ' '.join(['"%s"' % item for item in
                                     temp_command_list]) + ' 2> /dev/null '
            cluster_management.run_a_command_and_wait_on_cluster(command=temp_command)
        else:
            raise Exception('machine type error')

    def get_plumed_script_for_restrained_MD_and_relax(self, item_positions, force_constant,
                                                      ref_pdb_for_restrained,
                                                      num_steps_of_restrained_MD,
                                                      num_steps_of_equilibration):
        # write reference pdb file first
        Sutils.mark_and_modify_pdb_for_calculating_RMSD_for_plumed(self._ref_pdb, ref_pdb_for_restrained,
                                              self._selected_atom_indices, item_positions)

        plumed_string = """rmsd: RMSD REFERENCE=%s TYPE=OPTIMAL
restraint: MOVINGRESTRAINT ARG=rmsd AT0=0 STEP0=0 KAPPA0=%f STEP1=%d KAPPA1=%f STEP2=%d KAPPA2=%s
        """ % (ref_pdb_for_restrained, force_constant,
               num_steps_of_equilibration + num_steps_of_restrained_MD, force_constant,
               num_steps_of_equilibration + num_steps_of_restrained_MD + 1, '0')

        # plumed_string = "rmsd: RMSD REFERENCE=../resources/alanine_ref_1_TMD.pdb TYPE=OPTIMAL\n"
        # for item, index in enumerate(self._selected_atom_indices):
        #     plumed_string += "p_%d: POSITION ATOM=%d\n" % (item, index)
        # # item_positions /= 10.0 # is this needed?
        # position_string = str(item_positions.flatten().tolist())[1:-1].replace(' ', '')
        # force_constant_string_1 = ','.join([str(force_constant)] * (3 * len(self._selected_atom_indices)))
        # force_constant_string_2 = ','.join(['0'] * (3 * len(self._selected_atom_indices)))
        # argument_string = ','.join(["p_%d.%s" % (_1, _2) for _1 in range(len(self._selected_atom_indices))
        #                             for _2 in ('x','y','z')])
        # plumed_string += "restraint: MOVINGRESTRAINT ARG=%s AT0=%s STEP0=0 KAPPA0=%s AT1=%s STEP1=%d KAPPA1=%s\n"\
        #             % (argument_string, position_string,force_constant_string_1,
        #                position_string, num_steps_of_restrained_MD + num_steps_of_equilibration,
        #                force_constant_string_2)

        return plumed_string

    def restrained_MD_with_positions_and_relax(self, iter_index, positions_list, force_constant,
                                               output_folder=None,
                                               num_of_simulations_for_each_image=None,
                                               num_steps_of_restrained_MD=None,
                                               num_steps_of_unbiased_MD=None,
                                               num_steps_of_equilibration=None
                                               ):
        if num_of_simulations_for_each_image is None:
            num_of_simulations_for_each_image = self._num_of_simulations_for_each_image
        if num_steps_of_restrained_MD is None:
            num_steps_of_restrained_MD = self._num_steps_of_restrained_MD
        if num_steps_of_unbiased_MD is None:
            num_steps_of_unbiased_MD = self._num_steps_of_unbiased_MD
        if num_steps_of_equilibration is None:
            num_steps_of_equilibration = self._num_steps_of_equilibration
        temp_root_target_folder = '../target/' + CONFIG_30
        temp_root_resources_folder = '../resources/' + CONFIG_30
        print len(positions_list)
        output_pdb_file_list_list = []
        command_list = []
        folder_to_store_plumed_related_files = temp_root_resources_folder + '/string_method_%04d' % iter_index
        if not os.path.exists(folder_to_store_plumed_related_files):
            subprocess.check_output(['mkdir', folder_to_store_plumed_related_files])
        for index, item_positions in enumerate(positions_list):
            plumed_string = self.get_plumed_script_for_restrained_MD_and_relax(
                item_positions=item_positions, force_constant=force_constant,
                ref_pdb_for_restrained=folder_to_store_plumed_related_files + '/temp_plumed_ref_%04d.pdb' % index,
                num_steps_of_restrained_MD=num_steps_of_restrained_MD,
                num_steps_of_equilibration=num_steps_of_equilibration
            )
            plumed_script_file = folder_to_store_plumed_related_files + '/temp_plumed_script_%04d.txt' % index
            with open(plumed_script_file, 'w') as f_out:
                f_out.write(plumed_string)
            output_pdb_file_list = [output_folder + '/temp_string_%04d_%04d.pdb' % (index, item)
                                    for item in range(num_of_simulations_for_each_image)]
            output_pdb_file_list_list.append(output_pdb_file_list)
            for _1, item_out_pdb in enumerate(output_pdb_file_list):
                if isinstance(molecule_type, Alanine_dipeptide):
                    command = ['python', '../src/biased_simulation.py',
                               str(self._step_interval), str(num_steps_of_restrained_MD + num_steps_of_unbiased_MD), '0',
                               output_folder, 'none', 'pc_0',
                               '--output_pdb', item_out_pdb,
                               '--platform', 'CPU', '--bias_method', 'plumed_other',
                               '--equilibration_steps', str(num_steps_of_equilibration),
                               '--plumed_file', plumed_script_file]
                elif isinstance(molecule_type, Src_kinase):
                    command = ['python', '../src/biased_simulation_general.py', '2src',
                               str(self._step_interval), str(num_steps_of_restrained_MD + num_steps_of_unbiased_MD), '0',
                               output_folder, 'none', 'pc_0', 'explicit', 'NPT',
                               '--output_pdb', item_out_pdb,
                                 '--platform', 'CUDA', '--bias_method', 'plumed_other',
                                '--device', str(_1 % 2),
                                 '--equilibration_steps', str(num_steps_of_equilibration),
                                 '--plumed_file', plumed_script_file]
                elif isinstance(molecule_type, BetaHairpin):
                    command = ['python', '../src/biased_simulation_general.py', 'BetaHairpin',
                               str(self._step_interval), str(num_steps_of_restrained_MD + num_steps_of_unbiased_MD), '0',
                               output_folder, 'none', 'pc_0', 'implicit', 'NPT',
                               '--output_pdb', item_out_pdb,
                                 '--platform', 'CUDA', '--bias_method', 'plumed_other',
                                '--device', str(_1 % 2),
                                 '--equilibration_steps', str(num_steps_of_equilibration),
                                 '--plumed_file', plumed_script_file]
                else:
                    raise Exception('molecule type error')
                print ' '.join(command)
                command_list.append(' '.join(command))

        temp_iteration_object = iteration(index=1447)
        temp_iteration_object.run_simulation(commands=command_list)
        self.remove_water_and_align(temp_root_target_folder)
        assert len(output_pdb_file_list_list) == len(positions_list), (len(output_pdb_file_list_list), len(positions_list))
        assert len(output_pdb_file_list_list[0]) == num_of_simulations_for_each_image, len(output_pdb_file_list_list[0])
        return output_pdb_file_list_list

    def run_iteration(self, index, starting_target_folder=None):
        root_target = '../target/' + CONFIG_30
        if starting_target_folder is None:
            starting_target_folder = root_target + '/string_method_%04d' % (index - 1)
        pdb_file_list = self.get_aligned_pdb_list_list_of_nodes_from_a_folder(starting_target_folder)
        positions_list = self.get_average_node_positions_of_string(
            pdb_file_list_list=pdb_file_list, num_snapshots=self._num_snapshots_for_calculating_average_positions)
        positions_list, _ = self.reparametrize_and_get_images_using_interpolation(positions_list, 0.5)
        np.savetxt('temp_images_%04d.txt' % index, positions_list)
        output_pdb_list = self.restrained_MD_with_positions_and_relax(
            index, positions_list, 1000000,
            output_folder='../target/' + CONFIG_30 + '/string_method_%04d' % index)
        return output_pdb_list

    def run_multi_iterations(self, start_index, num_iterations, starting_target_folder=None):
        for item in range(start_index, start_index + num_iterations):
            pdb_file_list = self.run_iteration(item, starting_target_folder=starting_target_folder)
        return


if __name__ == '__main__':
    # a = String_method([2,5,7,9,15,17,19], '../resources/alanine_dipeptide.pdb',
    #                   num_of_simulations_for_each_image=10,
    #                   num_steps_of_equilibration=5000,
    #                   num_steps_of_restrained_MD=0, num_steps_of_unbiased_MD=20,
    #                   smooth_coeff=0.5)
    # a.remove_water_and_align('../target/' + CONFIG_30)

    # atom_index = get_index_list_with_selection_statement('../resources/2src.pdb',
    #                                      '(resid 144:170 or resid 44:58) and not name H*')
    # a = String_method(atom_index, '../resources/2src.pdb',
    #                   num_of_simulations_for_each_image=3,
    #                   num_steps_of_equilibration=5000,
    #                   num_steps_of_restrained_MD=0, num_steps_of_unbiased_MD=100,
    #                   step_interval=2,
    #                   num_snapshots_for_calculating_average_positions=10,
    #                   smooth_coeff=0.5)

    atom_index = get_index_list_with_selection_statement('../resources/BetaHairpin.pdb', 'backbone')
    a = String_method(atom_index, '../resources/BetaHairpin.pdb',
                      num_of_simulations_for_each_image=10,
                      num_steps_of_equilibration=5000,
                      num_steps_of_restrained_MD=0, num_steps_of_unbiased_MD=20,
                      step_interval=1,
                      num_snapshots_for_calculating_average_positions=10,
                      smooth_coeff=0.5)

    a.run_multi_iterations(1, 10)
