"""
Move the jaco2 to a target position with an adaptive controller
that will account for a 2lb weight in its hand
"""
import numpy as np
import os
import timeit
import time
import traceback
import scipy
import redis

from abr_control.controllers import OSC, signals, path_planners
from abr_control.utils import DataHandler
import abr_jaco2
import nengo

class Training:

    def __init__(self,
            test_group='testing', test_name="joint_space_training", session=None,
            run=None, offset=None, kp=20, kv=6, ki=0,
            integrated_error=np.array([0.0, 0.0, 0.0]),
            avoid_limits=True, db_name=None, vmax=1, SCALES=None, MEANS=None,
            friction_gain=[0.0]):

        """
        The test script used to collect data for training. The use of the
        adaptive controller and the type of backend can be specified. The
        script is also automated to create new and load the most recent weights
        files for continuous learning.

        We refere to 'runs' as the consecutive tests where the previous learned
        weights are used.  A set of runs are a single 'session'. Multiple
        sessions of these runs can then be used for averaging and analysis.

        The adaptive controller uses a 6 dimensional input and returns a 3
        dimensional output. The base, shoulder and elbow joints' positions and
        velocities are used as the input, and the control signal for the
        corresponding joints gets returned.

        Parameters
        ----------
        test_group: string, Optional (Default: 'testing')
        test_name: string, Optional (Default: 'joint_space_training')
            folder name where data is saved
        session: int, Optional (Default: None)
            The current session number, if left to None then it will be automatically
            updated based on the current session. If the next session is desired then
            this will need to be updated.
        run: int, Optional (Default: None)
            The current nth run that specifies to use the weights from the n-1 run.
            If set to None if will automatically increment based off the last saved
            weights.
        time_limit: float, Optional (Default: 30)
            the time limit for each run in seconds
        offset: float array, Optional (Default: None)
            Set the offset to the end effector if something other than the default
            is desired. Use the form [x_offset, y_offset, z_offset]
        kp: float, Optional (Default: 20)
            proportional gain term
        kv: float, Optional (Default: 6)
            derivative gain term
        ki: float, Optional (Default: 0)
            integral gain term
        avoid_limits: Boolean Optional (Default: True)
            Adds joint avoidance controller to prevent the arm from colliding
            with the floor and itself
            NOTE: this is only for joints1 and 2, it may still be possible for
            the gripper to collide with the arm in certain configurations
        db_name: String, Optional (Default: None)
            the database to use for saving/loading, when set to None the
            default will be used (abr_control_db.h5)
        MEANS : list of floats, Optional (Default: None)
            expected mean of joint angles and velocities in [rad] and [rad/sec]
            respectively. Expected value for each joint. Only used for adaptation
        SCALES : list of floats, Optional (Default: None)
            expected variance of joint angles and velocities. Expected value for
            each joint. Only used for adaptation
        friction_gain: list of floats, Optional (Default:[0])
            list of gains used to scale friction signal to each joint

        Attributes
        ----------
        target_xyz: array of floats
            the goal target, used for calculating error
        target: array of floats [x, y, z, vx, vy, vz]
            the filtered target, used for calculating error for figure8
            test since following trajectory and not moving to a single final
            point
        """

        self.remove_arm = False
        self.use_adapt = False
        self.friction_gain = np.array(friction_gain)
        self.params = {'source': 'training',
                  'test_group': test_group,
                  'test_name': test_name,
                  'session': session,
                  'run': run,
                  'offset': offset,
                  'kp': kp,
                  'kv': kv,
                  'ki': ki,
                  'avoid_limits': avoid_limits,
                  'db_name': db_name,
                  'vmax': vmax,
                  'friction_gain': self.friction_gain}

        if SCALES is not None:
            self.params['SCALES_q'] = SCALES['q']
            self.params['SCALES_dq'] = SCALES['dq']
        else:
            self.params['SCALES_q'] = 'None'
            self.params['SCALES_dq'] = 'None'

        if MEANS is not None:
            self.params['MEANS_q'] = MEANS['q']
            self.params['MEANS_dq'] = MEANS['dq']
        else:
            self.params['MEANS_q'] = 'None'
            self.params['MEANS_dq'] = 'None'

        self.run = run
        self.session = session
        self.test_group = test_group
        self.test_name = test_name
        self.avoid_limits = avoid_limits

        # instantiate our data handler for saving and load
        self.data_handler = DataHandler(use_cache=True, db_name=db_name)

        if self.run is None or self.session is None:
            # Get the last saved location in the database
            [run, session, location] = self.data_handler.last_save_location(
                session=self.session, run=self.run, test_name=self.test_name,
                test_group=self.test_group, create=True)
            if run is None:
                run = 0

            if self.run is None:
                self.run = run
            if self.session is None:
                self.session = session

        print('RUN: ', self.run)
        print('SESSION: ', self.session)

        print('--Instantiate robot_config--')
        # instantiate our robot config
        self.robot_config = abr_jaco2.Config(use_cython=True, hand_attached=True,
                SCALES=SCALES, MEANS=MEANS, init_all=True, offset=offset)

        if offset is None:
            self.OFFSET = self.robot_config.OFFSET
        else:
            self.OFFSET = offset
        print('--Generate / load transforms--')
        self.robot_config.init_all()

        print('--Instantiate OSC controller--')
        # if using I term, load previous integrated errors if applicable
        if ki != 0 and run != 0:
                integrated_error = self.data_handler.load_data(params=['integrated_error'],
                        session=self.session,
                        run=self.run-1, test_group=self.test_group,
                        test_name=self.test_name,
                        create=True)['integrated_error']
                print('Integrated Error: ', integrated_error)

        # instantiate operational space controller
        self.ctrlr = OSC(robot_config=self.robot_config, kp=kp, kv=kv, ki=ki,
                vmax=vmax, null_control=True,
                integrated_error=integrated_error, use_C=False)

        print('--Instantiate path planner--')
        # instantiate our filter to smooth out trajectory to final target
        # self.path = path_planners.SecondOrder(robot_config=self.robot_config,
        #         n_timesteps=3000, w=1e4, zeta=3, threshold=0.0)
        self.dt = 0.004

        self.path = path_planners.dmpFilter()

        if self.avoid_limits:
            print('--Instantiate joint avoidance--')
            self.avoid = signals.AvoidJointLimits(
                self.robot_config,
                min_joint_angles=[None, 1.3, 0.61, None, None, None],
                max_joint_angles=[None, 4.99, 5.5, None, None, None],
                # min_joint_angles=[0.8, None, None, None, None, None],
                # max_joint_angles=[4.75, None, None, None, None, None],
                max_torque=[10]*self.robot_config.N_JOINTS,
                cross_zero=[True, False, False, False, True, False],
                gradient = [False, False, False, False, False, False])

        if np.any(self.friction_gain):
            print('--Instantiate joint friction--')
            self.friction = signals.Friction(
                   Fn=4, uk=0.42, us=0.74, vs=0.1, Fv=1.2)


        print('--Instantiate interface--')
        # instantiate our interface
        if not self.remove_arm:
            self.interface = abr_jaco2.Interface(robot_config=self.robot_config)

        # set up lists for tracking data
        self.data = {'q': [], 'dq': [], 'u_base': [], 'u_adapt': [],
                     'error':[], 'training_signal': [], 'target': [],
                     'ee_xyz': [], 'input_signal': [], 'filter': [],
                     'time': [], 'weights': [], 'u_avoid': [], 'osc_dx': [],
                     'q_torque': [], 'M_inv_singular': [], 'u_kp': [],
                     'u_kv': [], 'u_friction': [], 'u_task': []}
        self.count = 0
        print('MAIN CLASS INSTANTIATED')

    def __init_network__(self, adapt_input, adapt_output, n_neurons=1000, n_ensembles=1,
            weights=None, pes_learning_rate=1e-6, backend=None, seed=None,
            probe_weights=True, neuron_type='lif', use_spherical=False,
            trig_q=False, trig_dq=False, autoload_weights=True):
        """
        Instantiate the adpative controller

        Parameters
        ----------
        n_neurons: int, Optional (Default: 1000)
            the number of neurons in the adaptive population
        n_ensembles: int, Optional (Default: 1)
            the number of ensembles of n_neurons number of neurons
        weights: string, Optional (Default: None)
            the path to the desired saved weights to use. If None will
            automatically take the most recent weights saved in the 'test_name'
            directory
        pes_learning_rate: float, Optional (Default: 1e-6)
            the learning rate for the adaptive population
        backend: string
            None: non adaptive control, Optional (Default: None)
            'nengo': use nengo as the backend for the adaptive population
            'nengo_spinnaker': use spinnaker as the adaptive population
        seed: int Optional, (Default: None)
            seed used for random number generation in adaptive population
        adapt_input : list of booleans
            a boolean list of which joint information to pass in to the
            adaptive population
            Ex: to use joint 1 and 2 information for a 6DOF arm
            (starting from base 0)
            adapt_input = [False, True, True, False, False, False]
        adapt_output : list of booleans
            a boolean list of which joints to apply the adaptive signal to
            Ex: to adapt joint 1 and 2 for a 6DOF arm (starting from base 0)
            adapt_input = [False, True, True, False, False, False]
        trig_q: boolean, Optional (Default: False)
            True to scale joint angle input to network by sin and cos (doubles
            dimensionality for angles since both sin and cos are used to conver
            the entire sin cos space
        trig_dq: boolean, Optional (Default: False)
            True to scale joint velocity input to network by sin and cos (doubles
            dimensionality for angles since both sin and cos are used to conver
            the entire sin cos space
        autoload_weights: boolean, Optional (Default: True)
            If true then weights will be loaded from the previous run
        *NOTE: adapt_output DOES NOT have to be the same as adapt_input*
            probe_weights: Boolean Optional (Default: False)
                True to probe adaptive population for decoders
        """
        self.use_spherical = use_spherical
        self.use_adapt = True
        self.trig_q = trig_q
        self.trig_dq = trig_dq

        self.adapt_input = np.array(adapt_input)
        self.in_index = np.arange(self.robot_config.N_JOINTS)[self.adapt_input]
        self.adapt_output = np.array(adapt_output)
        self.out_index = np.arange(self.robot_config.N_JOINTS)[self.adapt_output]

        # hdf5 has no type None so an error is raised for runs where None
        # weights are passed in. This get's handled on the dynamics adaptation
        # side, but at this point they will be None. This is added to avoid the
        # hdf5 error
        if weights is None:
            saved_input_weights = 'None'
        else:
            saved_input_weights = weights

        if self.use_spherical:
            extra_dim = 1
        else:
            extra_dim = 0

        n_input = sum(adapt_input*2) + extra_dim


        print('EXTRA DIM: ', extra_dim)
        print('Using spherical: ', self.use_spherical)
        print('j in cossin space: ', self.trig_q)
        print('dj in cossin space: ', self.trig_dq)

        encoders = self.generate_encoders(input_signal=None,
                n_neurons=n_neurons*n_ensembles, use_spherical=use_spherical,
                run=self.run)
        encoders = encoders.reshape(n_ensembles, n_neurons, n_input)

        self.params['adapt_input'] = adapt_input
        self.params['adapt_output'] = adapt_output
        self.params['n_neurons'] = n_neurons
        self.params['n_ensembles'] = n_ensembles
        self.params['weights'] = saved_input_weights
        self.params['pes_learning_rate'] = pes_learning_rate
        self.params['backend'] = backend
        self.params['seed'] = seed
        self.params['probe_weights'] = probe_weights
        self.params['neuron_type'] = neuron_type
        self.params['use_spherical'] = self.use_spherical
        self.params['trig_q'] = self.trig_q
        self.params['trig_dq'] = self.trig_dq
        self.params['extra_dim'] = extra_dim

        # load previous weights if they exist is None passed in
        if weights is None:
            if self.run == 0:
                weights = None
            elif autoload_weights:
                weights = self.data_handler.load_data(params=['weights'], session=self.session,
                        run=self.run-1, test_group=self.test_group,
                        test_name=self.test_name, create=True)

        intercepts = signals.AreaIntercepts(
            dimensions=n_input,
            base=signals.Triangular(-0.9, -0.9, 0.0))

        rng = np.random.RandomState(seed)
        intercepts = intercepts.sample(n_neurons, rng=rng)
        intercepts = np.array(intercepts)
        print('--Instantiate adapt controller--')
        # instantiate our adaptive controller
        self.adapt = signals.DynamicsAdaptation(
            n_input=sum(adapt_input*2) + extra_dim,
            n_output=sum(adapt_output),
            n_neurons=n_neurons,
            n_ensembles=n_ensembles,
            pes_learning_rate=pes_learning_rate,
            intercepts=intercepts,
            intercepts_mode=-0.5,
            weights_file=weights,
            backend=backend,
            probe_weights=probe_weights,
            seed=seed,
            neuron_type=neuron_type,
            encoders=encoders)

        # self.adapt.params['encoders'] = encoders
        #
    def connect_to_arm(self):
        # connect to and initialize the arm
        if not self.remove_arm:
            print('--Connect to arm--')
            self.interface.connect()
            self.interface.init_position_mode()
            self.interface.send_target_angles(self.robot_config.INIT_TORQUE_POSITION)
            print('--Initialize force mode--')
            self.interface.init_force_mode()

    def reach_to_target(self, target_xyz, reaching_time):
        # TODO: ADD NOTE ABOUT USING BASH FOR MULTIPLE RUNS INSTEAD OF JUST
        # CALLING RUN, MENTION PERFORMANCE EFFECTS ETC
        """

        Parameters
        ----------
        target_xyz: numpy array of floats
            x,y,z position of target [meters]
        reaching_time: float
            time [seconds] to reach to target
        """
        # track loop_time for stopping test
        loop_time = 0

        # get joint angle and velocity feedback to reset starting point to
        # current end-effector position
        if not self.remove_arm:
            feedback = self.interface.get_feedback()
        else:
            feedback = {'q': np.zeros(6), 'dq': np.zeros(6)}
        self.q = feedback['q']
        self.dq = feedback['dq']
        #self.dq[abs(self.dq) < 0.05] = 0
        # calculate end-effector position
        ee_xyz = self.robot_config.Tx('EE', q=self.q, x= self.OFFSET)

        # # last three terms used as started point for target EE velocity
        # self.target = np.concatenate((ee_xyz, np.array([0, 0, 0])), axis=0)

        print('--Starting main control loop--')
        print('Target: ', target_xyz)
        # M A I N   C O N T R O L   L O O P
        while loop_time < reaching_time:
            start = timeit.default_timer()
            # prev_xyz = ee_xyz

            # use our filter to get the next point along the trajectory to our
            # final target location
            # self.target = self.path.step(state=self.target, target_pos=target_xyz,
            #         dt=self.dt)

            # self.target = self.path.next_timestep(t=loop_time)


            # calculate euclidean distance to target
            # error = np.sqrt(np.sum((ee_xyz - target_xyz)**2))

            # get joint angle and velocity feedback
            #if not self.remove_arm:
            feedback = self.interface.get_feedback()
            #else:
            #    feedback = {'q': np.zeros(6), 'dq': np.zeros(6)}
            self.q = feedback['q']
            self.dq = feedback['dq']
            #self.dq[abs(self.dq) < 0.05] = 0

            # calculate end-effector position
            ee_xyz = self.robot_config.Tx('EE', q=self.q, x= self.OFFSET)

            # step through our path planner based on the current runtime
            self.target = self.path.next_timestep(t=loop_time)

            # Calculate the control signal and the adaptive signal
            u = self.generate_u()

            # send forces
            #if not self.remove_arm:
            self.interface.send_forces(np.array(u, dtype='float32'))

            # track data
            self.data['q'].append(np.copy(self.q))
            self.data['dq'].append(np.copy(self.dq))
            self.data['u_base'].append(np.copy(self.u_base))
            if self.use_adapt:
                self.data['u_adapt'].append(np.copy(self.u_adapt))
                self.data['training_signal'].append(np.copy(self.training_signal))
                self.data['input_signal'].append(np.copy(self.adapt_input))
            if self.avoid_limits:
                self.data['u_avoid'].append(np.copy(self.u_avoid))
            #self.data['error'].append(np.copy(error))
            self.data['target'].append(np.copy(target_xyz))
            #self.data['ee_xyz'].append(np.copy(ee_xyz))
            self.data['filter'].append(np.copy(self.target))
            # self.data['osc_dx'].append(np.copy(self.ctrlr.dx))
            # q_T = self.interface.get_torque_load()
            # self.data['q_torque'].append(np.copy(q_T))
            self.data['u_friction'].append(np.copy(self.u_friction))
            # self.data['u_task'].append(np.copy(self.ctrlr.u_task))
            # self.data['u_kp'].append(np.copy(self.ctrlr.u_kp))
            # self.data['u_kv'].append(np.copy(self.ctrlr.u_kv))

            end = timeit.default_timer() - start
            # if self.count % 600 == 0:
            #     #print('error: ', error)
            #     print('dt: ', end)
            #     print('friction: ', self.u_friction)
            #     print('adapt: ', self.u_adapt)
            #     #print('torque: ', q_T)

            self.data['time'].append(np.copy(end))

            loop_time += end
            self.count += 1

        print('*~~~~FINAL~~~~*')
        # print('error: ', error)
        print('dt: ', end)
        print('friction: ', self.u_friction)
        print('adapt: ', self.u_adapt)
        print('*~~~~~~~~~~~~~*')


    #@profile
    def generate_u(self):
            # calculate the base operation space control signal
            self.u_base = self.ctrlr.generate(
                q=self.q,
                dq=self.dq ,
                target_pos=self.target[:3],
                #target_vel=self.target[3:],
                ref_frame='EE',
                offset = self.OFFSET)

            self.data['M_inv_singular'].append(np.copy(self.ctrlr.Mx_non_singular))

            u = self.u_base

            if self.use_adapt:
                # calculate the adaptive control signal
                training_signal = []
                adapt_input_q = []
                adapt_input_dq = []

                for ii in self.in_index:
                    training_signal.append(self.ctrlr.training_signal[ii])
                    # adapt_input_q.append(self.robot_config.scaledown('q',self.q)[ii])
                    # adapt_input_dq.append(self.robot_config.scaledown('dq',self.dq)[ii])

                [adapt_input_q, adapt_input_dq] = self.generate_scaled_inputs(
                        q=np.copy(self.q), dq=np.copy(self.dq))

                def convert_to_sin_cos(input_signal):
                    """
                    Takes in inputs from the range of -1 to 1 and scales them
                    to sin-cos space
                    """
                    x0 = input_signal[0]
                    x1 = input_signal[1]
                    sincos = [np.cos(np.pi*x0), np.sin(np.pi*x0), np.cos(np.pi*x1),
                            np.sin(np.pi*x1)]
                    return sincos

                self.training_signal = np.array(training_signal)
                if self.trig_q:
                    adapt_input_q = (convert_to_sin_cos(adapt_input_q))
                if self.trig_dq:
                    adapt_input_dq = (convert_to_sin_cos(adapt_input_dq))

                self.adapt_input = np.hstack((adapt_input_q, adapt_input_dq))
                if self.use_spherical:
                    self.adapt_input = self.convert_to_spherical(self.adapt_input)

                u_adapt = self.adapt.generate(input_signal=self.adapt_input,
                                         training_signal=self.training_signal)

                # create array of zeros, we will change the adaptive joints with
                # their respective outputs. This just puts the adaptive output into
                # the same shape as our base control
                self.u_adapt = np.zeros(self.robot_config.N_JOINTS)
                count = 0
                for ii in self.out_index:
                    self.u_adapt[ii] = u_adapt[count]
                    count += 1

                # add adaptive signal to base controller
                u = self.u_base + self.u_adapt
            else:
                self.u_adapt = None
                self.training_signal = None

            if self.avoid_limits:
                # add in joint limit avoidance
                self.u_avoid = self.avoid.generate(self.q)
                u += self.u_avoid
            else:
                self.u_avoid = None

            self.u_friction = np.zeros(self.robot_config.N_JOINTS)
            if np.any(self.friction_gain):
                for dd, k_friction in enumerate(self.friction_gain):
                    if k_friction > 0:
                        self.u_friction[dd] = (k_friction *
                            self.friction.generate(self.dq[dd]))
                u += self.u_friction

            return u

    def stop(self):
        print('--Disconnecting--')
        # close the connection to the arm
        if not self.remove_arm:
            self.interface.init_position_mode()
            self.interface.send_target_angles(self.robot_config.INIT_TORQUE_POSITION)
            self.interface.disconnect()

        print('**** RUN STATS ****')
        print('Number of steps: ', self.count)
        # print('Average loop speed: ',
        #       sum(self.data['time'])/len(self.data['time']))
        # print('Average Error/Step: ',
        #       sum(self.data['error'])/len(self.data['error']))
        print('Run number ', self.run)
        print('*******************')

    def save_data(self, overwrite=True):
        print('--Saving run data--')
        print('Saving tracked data to %s/%s/session%03d/run%03d'%(self.test_group, self.test_name,
            self.session, self.run))

        # Save integrated error at the end of the run, we are only interested
        # in the final value
        self.data['integrated_error'] = self.ctrlr.integrated_error

        # Save test data
        self.data_handler.save_data(tracked_data=self.data, session=self.session,
            run=self.run, test_name=self.test_name, test_group=self.test_group,
            overwrite=overwrite)

    def save_parameters(self, overwrite=True, create=True, custom_params=None):
        print('--Saving test parameters--')
        loc = '%s/%s/parameters/'%(self.test_group, self.test_name)
        if np.any(self.friction_gain):
            # Save friction parameters
            self.data_handler.save(data=self.friction.params,
                    save_location=loc + self.friction.params['source'], overwrite=overwrite, create=create)

        # Save OSC parameters
        self.data_handler.save(data=self.ctrlr.params,
                save_location=loc + self.ctrlr.params['source'], overwrite=overwrite, create=create)

        # Save robot_config parameters
        self.data_handler.save(data=self.robot_config.params,
                save_location=loc + self.robot_config.params['source'], overwrite=overwrite, create=create)

        # Save path planner parameters
        self.data_handler.save(data=self.path.params,
                save_location=loc + self.path.params['source'], overwrite=overwrite, create=create)

        # Save training parameters
        self.data_handler.save(data=self.params,
                save_location=loc + self.params['source'], overwrite=overwrite, create=create)

        # Save any extra parameters the user wants kept for the test at hand
        if custom_params is not None:
            self.data_handler.save(data=custom_params,
                    save_location=loc + 'test_parameters', overwrite=overwrite,
                    create=create)

    def save_adaptive(self, overwrite=True, create=True):
        print('--Saving run and adaptive data--')
        print('Saving tracked data to %s/%s/session%03d/run%03d'%(self.test_group, self.test_name,
            self.session, self.run))
        loc = '%s/%s/parameters/'%(self.test_group, self.test_name)
        #TODO: weights are saved in save_data, but since the adaptive
        """saving is now separated, we have to either save this again, or make
        sure that save_adaptive is run first to add weights to the dictionary
        before the rest of the tracked data is saved in save data. For now it is added here
        to make sure it is saved, in case the user forgets to run this first"""

        # Get weight from adaptive population
        self.data['weights'] = self.adapt.get_weights()
        # Save test data
        self.data_handler.save_data(tracked_data=self.data, session=self.session,
            run=self.run, test_name=self.test_name, test_group=self.test_group,
            overwrite=overwrite)

        # Save dynamics_adaptation parameters
        self.data_handler.save(data=self.adapt.params,
                save_location=loc + self.adapt.params['source'], overwrite=overwrite, create=create)

    def convert_to_spherical(self, input_signal):
        """
        converts an input signal of shape time x N_joints and converts to
        spherical
        """
        #print('IN: ', input_signal.shape)
        x = input_signal.T
        pi = np.pi
        spherical = []

        def scale(input_signal):
            #TODO: does it make more sense to pass in the range and have the script
            # handle the division, so we go from 0-factor instead of 0-2*factor?
            """
            Takes inputs in the range of -1 to 1 and scales them to the range of
            0-2*factor

            ex: if factor == pi the inputs will be in the range of 0-2pi
            """
            signal = np.copy(input_signal)
            factor = pi
            for ii, dim in enumerate(input_signal):
                if ii == len(input_signal)-1:
                    factor = 2*pi
                signal[ii] = dim * factor# + factor
            return signal

        def sin_product(input_signal, count):
            """
            Handles the sin terms in the conversion to spherical coordinates where
            we multiple by sin(x_i) n-1 times
            """
            tmp = 1
            for jj in range(0, count):
                tmp *= np.sin(input_signal[jj])
            return tmp

        # nth input scaled to 0-2pi range, remainder from 0-pi
        # cycle through each input
        x_rad = scale(input_signal=x)

        for ss in range(0, len(x)):
            sphr = sin_product(input_signal=x_rad, count=ss)
            sphr*= np.cos(x_rad[ss])
            spherical.append(sphr)
        spherical.append(sin_product(input_signal=x_rad, count=len(x)))
        spherical = np.array(spherical).T
        #print('OUT: ', np.array(spherical).shape)
        return(spherical)

    def generate_encoders(self, input_signal=None, n_neurons=1000, thresh=0.008,
            use_spherical=True, run=0):
        """
        Accepts inputs signal in the shape of time X dim and outputs encoders
        for the specified number of neurons by sampling from the input

        *NOTE* the input must be passed in prior to spherical conversion, if
        any is being done
        """
        #TODO: scale thresh based on dimensionality of input, 0.008 for 2DOF
        # and 10k neurons, 10DOF 10k use 0.08, for 10DOF 100 went up to 0.708 by end
        # 0.3 works well for 1000
        # first run so we need to generate encoders for the sessions
        thresh = 0.3
        debug = False
        if debug:
            print('\n\n\nDEBUG LOAD ENCODERS\n\n\n')
            encoders = np.load('encoders-backup.npz')['encoders']
        elif run == 0:
            print('First run of session, generating encoders...')
            if input_signal is None:
                print('No input signal passed in for sampling, using recorded data')
                data = np.load('input_signal.npz')
                qs = data['q']
                dqs = data['dq']
                [qs, dqs] = self.generate_scaled_inputs(q=qs, dq=dqs)
                input_signal = np.hstack((qs, dqs))
                self.input_signal_len = len(input_signal)
                print('input_signal_length: ', self.input_signal_len)
            ii = 0
            same_count = 0
            prev_index = 0
            while (input_signal.shape[0] > n_neurons):
                if ii%1000 == 0:
                    print(input_signal.shape)
                    print('thresh: ', thresh)
                # choose a random set of indices
                n_indices = input_signal.shape[0]
                # make sure we're dealing with an even number
                n_indices -= 0 if ((n_indices % 2) == 0) else 1
                n_half = int(n_indices / 2)

                randomized_indices = np.random.permutation(range(n_indices))
                a = randomized_indices[:n_half]
                b = randomized_indices[n_half:]

                data1 = input_signal[a]
                data2 = input_signal[b]

                distances = np.linalg.norm(data1 - data2, axis=1)

                under_thresh = distances > thresh

                input_signal = np.vstack([data1, data2[under_thresh]])
                ii += 1
                if prev_index == n_indices:
                    same_count += 1
                else:
                    same_count = 0

                if same_count == 50:
                    same_count = 0
                    thresh += 0.001
                    print('All values are within threshold, but not at target size.')
                    print('Increasing threshold to %.4f' %thresh)
                prev_index = n_indices

            first_time = True
            while (input_signal.shape[0] != n_neurons):
                if first_time:
                    print('Too many indices removed, appending random entries to'
                            + ' match dimensionality')
                    print('shape: ', input_signal.shape)
                first_time = False
                row = np.random.randint(input_signal.shape[0])
                input_signal = np.vstack((input_signal, input_signal[row]))

            print(input_signal.shape)
            print('thresh: ', thresh)
            if use_spherical:
                encoders = self.convert_to_spherical(input_signal)
            else:
                encoders = np.array(input_signal)

        # seccessive run so load the encoders used for run 0
        else:
            print('Loading encoders used for run 0...')
            encoders = self.data_handler.load(params=['encoders'],
                    save_location='%s/%s/parameters/dynamics_adaptation/'
                                   %(self.test_group, self.test_name))['encoders']
        np.savez_compressed('encoders-backup.npz', encoders=encoders)
        encoders = np.array(encoders)
        print(encoders.shape)
        return encoders

    def generate_scaled_inputs(self, q, dq, in_index=None):
        '''
        pass q dq in as time x dim shape
        accepts the 6 joint positions and velocities of the jaco2 and does the
        mean subtraction and scaling. Can set which joints are of interest with
        in_index, if it is not passed in the self.in_index instantiated in
        __init_network__ will be used

        returns two n x 6 lists scaled, one for q and one for dq
        '''
        # check if we received a 1D input (one timestep) or a 2D input (list of
        # inputs over time)
        # if np.squeeze(q)[0] > 1 and np.squeeze(q)[1] > 1:
        #     print('Scaling list of inputs')
        if in_index is None:
            in_index = self.in_index
        qs = q.T
        dqs = dq.T
        #print('raw q: ', np.array(qs).T.shape)

        # add bias to joints 0 and 4 so that the input signal doesn't keep
        # bouncing back and forth over the 0 to 2*pi line
        qs[0] = (qs[0] + np.pi) % (2*np.pi)
        qs[4] = (qs[4] + np.pi) % (2*np.pi)

        MEANS = {  # expected mean of joint angles / velocities
            # shift from 0-2pi to -pi to pi
            'q': np.array([3.20, 2.14, 1.52, 4.68, 3.00, 3.00]),
            'dq': np.array([0.002, -0.117, -0.200, 0.002, -0.021, 0.002]),
            }
        SCALES = {  # expected variance of joint angles / velocities
            'q': np.array([0.2, 1.14, 1.06, 1.0, 2.8, 0.01]),
            'dq': np.array([0.06, 0.45, 0.7, 0.25, 0.4, 0.01]),
            }

        for pp in range(0, 6):
            qs[pp] = (qs[pp] - MEANS['q'][pp]) / SCALES['q'][pp]
            dqs[pp] = (dqs[pp] - MEANS['dq'][pp]) / SCALES['dq'][pp]

        qs = qs
        dqs = dqs
        scaled_q = []
        scaled_dq = []
        #print(in_index)
        for ii in in_index:
            scaled_q.append(qs[ii])
            scaled_dq.append(dqs[ii])
        scaled_q = np.array(scaled_q).T
        scaled_dq = np.array(scaled_dq).T
        #print('scaled q: ', np.array(scaled_q).shape)

        return [scaled_q, scaled_dq]

    def generate_path(self, target_xyz, start_xyz, time_limit):
        self.path.generate_path_function(
                target_xyz=target_xyz,
                start_xyz=start_xyz,
                time_limit=4)


