from abr_control.utils import PathErrorToIdeal
from abr_control.utils import PlotError

proc = PathErrorToIdeal()
plt = PlotError()
db_name='dewolf2018neuromorphic'
regen = False
plot_only = False
orders_of_error = [
                   0,
                   # 1,
                   # 3
                   ]
title = [
         'abs-pos-error',
         # 'abs-vel-error',
         # 'abs-jerk-error'
        ]
y_label = [
           'm*s',
           # 'm',
           # 'm/s^2'
           ]

test_group = 'friction_post_tuning'
test_list = [
              'pd_no_friction_5_0',
              'pd_no_friction_5_0',
              # 'pd_friction_11_0',
              # #'nengo_cpu_friction_12_0',
              # #'nengo_cpu_friction_19_0',
              # 'nengo_loihi_friction_6_0',
              # 'nengo_loihi_friction_7_0',
              # 'nengo_loihi_friction_8_0',
              ]

if not plot_only:
    print('Processing Data...')
    for order in orders_of_error:
        proc.process(test_group=test_group,
                     test_list=test_list,
                     regenerate=regen,
                     use_cache=True,
                     order_of_error=order,
                     # upper_baseline_loc=test_list[1],
                     # lower_baseline_loc=test_list[0],
                     db_name=db_name,
                     path_planner_as_ideal=True,
                     n_sessions=[1,1],#[15, 15, 5, 5, 5, 5],
                     n_runs=50)
        #TODO: if have incomplete session and run is not
        # specified, the next module will take the smallest
        # set of runs and use that for each session, should
        # check if incompelte and use the previous sessions
        # number of runs

print('Plotting Data...')
for ii, entry in enumerate(title):
    plt.get_error_plot(test_group=test_group,
                       test_list=test_list,
                       show_plot=False,
                       save_figure=True,
                       use_cache=True,
                       db_name=db_name,
                       order_of_error=[orders_of_error[ii]],
                       sum_errors=False,
                       scaling_factor=1,
                       colors=['k', 'b', 'g', 'r', 'y', 'm'],
                       y_label=y_label[ii],
                       fig_title=entry,
                       clear_plot=True,
                       legend_loc=0)