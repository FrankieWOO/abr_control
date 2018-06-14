from abr_control.utils import PathErrorToIdeal
from abr_control.utils import PlotError

proc = PathErrorToIdeal()
plt = PlotError()

test_group = 'loihi2018/no_weight'
test_list = ['pd/pd_5pt_baseline',
             'pid/gradual_wear14',
             'nengo/1000_neurons_x_20/gradual_wear23',
             'nengo_ocl/1000_neurons_x_20/gradual_wear21',
             'chip/gradual_wear24'
             ]
# proc.process(test_group=test_group,
#              test_list=test_list[2:],
#              regenerate=False,
#              use_cache=True,
#              order_of_error=0,
#              upper_baseline_loc=test_list[1],
#              lower_baseline_loc=test_list[0])

plt.get_error_plot(test_group=test_group,
                   test_list=test_list,
                   show_plot=True,
                   save_figure=False)
