from abr_control.utils import DataHandler, make_gif
import numpy as np
import matplotlib
matplotlib.use("TKAgg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import axes3d
import subprocess
import os

def align_yaxis(ax1, v1, ax2, v2):
    """adjust ax2 ylimit so that v2 in ax2 is aligned to v1 in ax1"""
    _, y1 = ax1.transData.transform((0, v1))
    _, y2 = ax2.transData.transform((0, v2))
    inv = ax2.transData.inverted()
    _, dy = inv.transform((0, 0)) - inv.transform((0, y1-y2))
    miny, maxy = ax2.get_ylim()
    ax2.set_ylim(miny+dy, maxy+dy)

#TODO: turn into module
# remove old figures used for previous gif so we don't get overlap for tests of
# different lengths

# bashCommand = ("rm figures/gif_figs/*.png")
# print('Removing old figures from "gif_figs" folder...')
# process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)#,
# output, error = process.communicate()
only_final_frame = True
show_traj = True
use_cache=True
plot_extra = False
plot_friction = False
plot_u = False
# runs=[0,10,25,40,49, 0,10,25,40,49, 0,10,25,40,49]
# sessions=[0,0,0,0,0,1,1,1,1,1,2,2,2,2,2]
#runs=[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 49]
runs = range(0,49)
#runs = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]
#sessions=[0,0,0,0,0,0,0,0,0,0]
sessions = np.zeros(len(runs))
n_columns = 10
#db_name = 'jacoOSCdebug'
db_name = 'dewolf2018neuromorphic'
test_groups = [
                'friction_post_tuning',
                'friction_post_tuning',
                # 'weighted_reach_post_tuning',
                # 'weighted_reach_post_tuning',
                #'1lb_random_target',
                # 'weighted_reach_post_tuning',
              ]
tests = [
        'nengo_loihi_friction_31_0',
        # 'nengo_loihi_friction_28_0',
        # 'nengo_cpu_friction_50_0',
        'nengo_cpu_friction_49_0',
        # 'nengo_loihi_friction_19_0',
        #'nengo_cpu_friction_20_0',
        #'pd_no_friction_5_0',
        #'nengo_cpu_friction_12_0',
        #'pd_friction_11_0',
        ]
use_offset = False

label_name = '%s : %s'%(tests[0], tests[1])
if 'simulations' in test_groups[0]:
    if 'ur5' in tests[0]:
        from abr_control.arms import ur5 as arm
        rc = arm.Config(use_cython=True)
        print('Using UR5 sim config')
    elif 'jaco' in tests[0]:
        from abr_control.arms import jaco2 as arm
        rc = arm.Config(use_cython=True, hand_attached=True)
        print('Using jaco2 sim config')
    offset=[0,0,0]
else:
    import abr_jaco2
    # only the first test needs the transforms since the virtual arm is for
    # that test. The offset is based on the first test listed
    if use_offset:
        rc = abr_jaco2.ConfigOffset(use_cython=True, hand_attached=True, init_all=True,
                offset=None)
        print('using jaco2 config with offset')
    else:
        rc = abr_jaco2.Config(use_cython=True, hand_attached=True, init_all=True,
                offset=None)
        print('using jaco2 config without offset')
    offset = rc.OFFSET
    #offset=[0,0,0]
    rc.init_all()

q_t = []
error_t = []
ee_xyz_t = []
targets_t = []
filter_t = []
ee_xyz_0 = []
error_0 = []
time_t = []
u_base_t = []

if use_cache:
    from abr_control.utils.paths import figures_dir
    save_loc = figures_dir
else:
    save_loc = 'figures'

if not os.path.exists(save_loc):
    os.makedirs(save_loc)

if not os.path.exists('%s/gif_fig_cache'%save_loc):
    os.makedirs('%s/gif_fig_cache'%save_loc)

files = [f for f in os.listdir('%s/gif_fig_cache'%save_loc) if f.endswith(".png") ]
for ii, f in enumerate(files):
    if ii == 0:
        print('Deleting old temporary figures for gif creation...')
    os.remove(os.path.join('%s/gif_fig_cache'%save_loc, f))
    #print(os.path.join('%s/gif_fig_cache'%save_loc, f))

u_min = 0
u_max = 0
for ii, run in enumerate(runs):
    session = sessions[ii]
    dat = DataHandler(use_cache=use_cache, db_name=db_name)
    data = dat.load(params=['q', 'error', 'target', 'ee_xyz', 'filter', 'time',
        'u_base', 'u_friction'],
            save_location='%s/%s/session%03d/run%03d'%
            (test_groups[0], tests[0], session, run))
    q_t.append(data['q'])
    error_t.append(data['error'])
    ee_xyz_t.append(data['ee_xyz'])
    targets_t.append(data['target'])
    filter_t.append(data['filter'])
    time_t.append(data['time'])
    if plot_friction:
        u_base_t.append(data['u_friction'])
        for ss in range(0,len(data['u_friction'])):
            if np.min(data['u_friction'][ss]) < u_min:
                u_min = np.min(data['u_friction'][ss])
            if np.max(data['u_friction'][ss]) > u_max:
                u_max = np.max(data['u_friction'][ss])
    else:
        u_base_t.append(data['u_base'])
        for ss in range(0,len(data['u_base'])):
            if np.min(data['u_base'][ss]) < u_min:
                u_min = np.min(data['u_base'][ss])
            if np.max(data['u_base'][ss]) > u_max:
                u_max = np.max(data['u_base'][ss])

    data_0 = dat.load(params=['ee_xyz', 'error'],
            save_location='%s/%s/session%03d/run%03d'%
            (test_groups[1], tests[1], session, run))
    ee_xyz_0.append(data_0['ee_xyz'])
    error_0.append(data_0['error'])

q_t = np.array(q_t)
error_t = np.array(error_t)
ee_xyz_t = np.array(ee_xyz_t)
targets_t = np.array(targets_t)
filter_t = np.array(filter_t)

min_len = []
for nn, q in enumerate(q_t):
    min_len.append(len(q))
    #print('%i: %i'%(nn, len(q)))
length = np.min(min_len)


# 2d trajectory plots
# fig2 = plt.figure(figsize=(15, np.ceil(len(runs)/3)*5))
# ee_xyz_1 = np.array(ee_xyz_t)
# ee_xyz_2 = np.array(ee_xyz_0)
# for run in runs:
#     ax = fig2.add_subplot(np.ceil(len(runs)/3),3,run+1)
#     plt.title(run)
#     ax.plot(ee_xyz_1[run].T[0], 'r', label='%s X'%tests[0])
#     ax.plot(ee_xyz_1[run].T[1], 'b', label='%s Y'%tests[0])
#     ax.plot(ee_xyz_1[run].T[2], 'g', label='%s Z'%tests[0])
#     ax.plot(ee_xyz_2[run].T[0], 'y--', label='%s X'%tests[1])
#     ax.plot(ee_xyz_2[run].T[1], 'c--', label='%s Y'%tests[1])
#     ax.plot(ee_xyz_2[run].T[2], 'm--', label='%s Z'%tests[1])
#     plt.legend()
# plt.savefig('2d_trajectory')
# plt.show()

# EXTRA PLOTTING: plot dist to filter
if plot_extra:
    dist_to_filter = []
    extra_times = []
    min_dist = 0
    max_dist = 0
    for dd, run in enumerate(runs):
        targets = targets_t[dd]
        error = error_t[dd]
        filter_xyz = filter_t[dd][:, 0:3]
        filter_err = []
        extra_times.append(np.linspace(0,4, len(error)))
        for ii in range(0,len(filter_xyz)):
            err = np.sqrt(np.sum((filter_xyz[ii] - targets[ii])**2))
            filter_err.append(err)
        dist_f = (error - filter_err)
        dist_to_filter.append(dist_f)
        if np.min(dist_f) < min_dist:
            min_dist = np.min(dist_f)
        if np.max(dist_f) > max_dist:
            max_dist = np.max(dist_f)

for ii in range(0,length,10):
    if only_final_frame:
        ii = length-1
    scale = 3
    if plot_extra:
        fig = plt.figure(figsize=([scale*(n_columns*2),
            6*scale*np.ceil(len(runs)/(n_columns*2))]))
    else:
        fig = plt.figure(figsize=([1.5*scale*n_columns, scale*np.ceil(len(runs)/n_columns)]))
    print('%.2f%% complete'%(ii/length*100), end='\r')
    for jj, run in enumerate(runs):
        if plot_extra:
            ax = fig.add_subplot(2*np.ceil(len(runs)/n_columns),n_columns,(2*jj)+1,
                    projection='3d')#, figsize=(3,3))
            ax2 = fig.add_subplot(2*np.ceil(len(runs)/n_columns),n_columns,(2*jj)+2,)
                    #figsize=(3,3))
            ax3 = ax2.twinx()
        else:
            ax = fig.add_subplot(np.ceil(len(runs)/n_columns),n_columns,jj+1, projection='3d')
        q = q_t[jj][ii]
        targets = targets_t[jj][ii]
        error = error_t[jj][ii]
        ee_xyz = ee_xyz_t[jj][ii]
        filter_xyz = filter_t[jj][ii, 0:3]
        u_base = np.array(u_base_t[jj][:ii,:]).T

        joint0 = rc.Tx('joint0', q=q)#, x=offset)
        joint1 = rc.Tx('joint1', q=q)#, x=offset)
        joint2 = rc.Tx('joint2', q=q)#, x=offset)
        joint3 = rc.Tx('joint3', q=q)#, x=offset)
        joint4 = rc.Tx('joint4', q=q)#, x=offset)
        joint5 = rc.Tx('joint5', q=q)#, x=offset)
        ee_recalc = rc.Tx('EE', q=q, x=offset)


        link0 = np.array(rc.Tx('link0', q=q))#, x=offset)
        link1 = np.array(rc.Tx('link1', q=q))#, x=offset)
        link2 = np.array(rc.Tx('link2', q=q))#, x=offset)
        link3 = np.array(rc.Tx('link3', q=q))#, x=offset)
        link4 = np.array(rc.Tx('link4', q=q))#, x=offset)
        link5 = np.array(rc.Tx('link5', q=q))#, x=offset)
        link6 = np.array(rc.Tx('link6', q=q))#, x=offset)
        links = np.stack([link0, link1, link2, link3, link4, link5, link6])

        joint0 = np.array(joint0)
        joint1 = np.array(joint1)
        joint2 = np.array(joint2)
        joint3 = np.array(joint3)
        joint4 = np.array(joint4)
        joint5 = np.array(joint5)
        ee_recalc = np.array(ee_recalc)
        joints = [joint0, joint1, joint2, joint3, joint4, joint5, ee_xyz]
        joints = np.stack(joints)

        colors = ['k', 'k', 'k', 'k', 'k', 'k', 'k']
        marker_size = [2**5, 2**5, 2**5, 2**5, 2**5, 2**5, 2**5]
        marker = ['o', 'o', 'o', 'o', 'o', 'o', 'o']
        # if any joint drops below the origin, change its color to red
        for kk, j in enumerate(joints):
            # 0.04m == radius of elbow joint
            if j[2] < 0.04:
                colors[kk] = 'r'
                marker_size[kk] = 2**9
                marker[kk] = '*'
            else:
                colors[kk] = 'k'
                marker_size[kk] = 2**5
                marker[kk] = 'o'
        # plot target location
        ax.scatter(targets[0], targets[1], targets[2], c='r',marker='o', s=2**5)
        # plot COM locations
        ax.scatter(link0[0], link0[1], link0[2], c='y',
                marker='o', s=2**5, label='COM')
        ax.scatter(link1[0], link1[1], link1[2], c='y',
                marker='o', s=2**5)
        ax.scatter(link2[0], link2[1], link2[2], c='y',
                marker='o', s=2**5)
        ax.scatter(link3[0], link3[1], link3[2], c='y',
                marker='o', s=2**5)
        ax.scatter(link4[0], link4[1], link4[2], c='y',
                marker='o', s=2**5)
        ax.scatter(link5[0], link5[1], link5[2], c='y',
                marker='o', s=2**5)
        ax.scatter(link6[0], link6[1], link6[2], c='y',
                marker='o', s=2**5)

        # plot joint locations
        ax.scatter(joint0[0], joint0[1], joint0[2], c=colors[0],
                marker=marker[0], s=marker_size[0], label='Joint')
        ax.scatter(joint1[0], joint1[1], joint1[2], c=colors[1],
                marker=marker[1], s=marker_size[1])
        ax.scatter(joint2[0], joint2[1], joint2[2], c=colors[2],
                marker=marker[2], s=marker_size[2])
        ax.scatter(joint3[0], joint3[1], joint3[2], c=colors[3],
                marker=marker[3], s=marker_size[3])
        ax.scatter(joint4[0], joint4[1], joint4[2], c=colors[4],
                marker=marker[4], s=marker_size[4])
        ax.scatter(joint5[0], joint5[1], joint5[2], c=colors[5],
                marker=marker[5], s=marker_size[5])
        ax.scatter(ee_xyz[0], ee_xyz[1], ee_xyz[2], c=colors[6],
                marker=marker[6], s=marker_size[6])
        # plot current filtered path planner target
        ax.scatter(filter_xyz[0], filter_xyz[1], filter_xyz[2], c='g', marker='*')
        # plot lines joining joints
        points = [None]*(len(joints)+len(links))
        points[::2] = links
        points[1::2] = joints
        points = np.array(points)
        ax.plot(points.T[0], points.T[1], points.T[2], 'k')
        ax.set_xlim3d(-0.35,0.35)
        ax.set_ylim3d(-0.35,0.35)
        ax.set_zlim3d(0.5,1.2)
        plt.title('Session %i : Target %i\n%s \n'%(sessions[jj], run, label_name))
        # time_t = np.array(time_t)
        # print(time_t.shape)
        # print(time_t[run].shape)
        # print(ii)
        # print(np.squeeze(time_t[run])[:ii+1])
        plt.xlabel('Time: %.2f sec'%(np.sum(time_t[jj][:ii])))
        ax.text(-0.5, -0.5, 0.9, 'Avg: %.3f m'%np.mean(error_t[jj]), color='b')
        ax.text(-0.5, -0.5, 1.0, 'Final: %.3f m'%(error_t[jj][-1]), color='b')
        ax.text(-0.5, -0.5, 1.1, 'Error: %.3f m'%(error), color='b')
        ax.text(-0.5, -0.5, 1.2, tests[0], color='b')

        # plot the recalulated EE pos to see if it matches
        ax.scatter(ee_recalc[0], ee_recalc[1], ee_recalc[2], c='m', marker='*')

        if show_traj:
            # plot ee trajectory line
            ax.plot(ee_xyz_t[jj][:ii, 0], ee_xyz_t[jj][:ii,1], ee_xyz_t[jj][:ii,2],
                    color='b', label=tests[0])
            # plot filtered path planner trajectory line
            ax.plot(filter_t[jj][:ii, 0], filter_t[jj][:ii,1], filter_t[jj][:ii,2],
                    c='g', label='Path Planner')
            # plot ee trajectory line of starting run
            ax.plot(ee_xyz_0[jj][:ii, 0], ee_xyz_0[jj][:ii,1],
                    ee_xyz_0[jj][:ii, 2], c='tab:purple', linestyle='dashed',
                    label=tests[1])
            ax.text(-0.5, -0.5, 0.5, 'Avg: %.3f m'%np.mean(error_0[jj]),
                    color='tab:purple')
            ax.text(-0.5, -0.5, 0.6, 'Final: %.3f m'%(error_0[jj][-1]),
                    color='tab:purple')
            if ii >= len(error_0[jj]):
                iii = len(error_0[jj])-1
            else:
                iii = ii
            ax.text(-0.5, -0.5, 0.7, 'Error: %.3f m'%(error_0[jj][iii]),
                    color='tab:purple')
            ax.text(-0.5, -0.5, 0.8, tests[1], color='tab:purple')
            if jj == len(runs)-1:
                ax.legend(bbox_to_anchor=[1.15, 0.5], loc='center left')

        if plot_extra:
            extra_time = np.squeeze(extra_times[jj])[:ii]
            if plot_friction:
                ax2_label = 'friction'
            else:
                ax2_label = 'u'
            for ff, u_joint in enumerate(u_base):

                ax2.plot(extra_time[:ii], u_joint[:ii], label='%s%i'%(ax2_label, ff))
            ax3.plot(extra_time[:ii], dist_to_filter[jj][:ii],
                    'c--', linewidth=3, label='EE dist to filter')
            # align_yaxis(ax2, 0, ax3, 0)
            ax2.set_ylabel('Session %i: Nm'%sessions[jj])
            ax3.set_xlim(0,4)
            ax2.set_ylim(u_min, u_max)
            ax3.set_ylim(min_dist, max_dist)
            ax3.set_ylabel('m')

    #plt.tight_layout()
    plt.savefig('%s/gif_fig_cache/%05d.png'%(save_loc,ii))
    ax.clear()
    plt.close()
    if only_final_frame:
        break

if not only_final_frame:
    make_gif.create(fig_loc='%s/gif_fig_cache'%save_loc,
                    save_loc='%s/%s/virtual_arm'%(save_loc, db_name),
                    save_name='%s-%s'%(tests[0], tests[1]),
                    delay=5, res=[1920,1080])

