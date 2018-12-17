import subprocess
import os
#TODO update this to work with ubuntu16 using the following link
# http://blog.ahfr.org/2008/03/making-animated-gifs-with-free-software.html
def create(fig_loc, save_loc, save_name, delay=5, res=[1200,2000]):
    """
    Module that checks fig_loc location for png files and creates a gif

    PARAMETERS
    ----------
    fig_loc: string
        location where .png files are saved
        NOTE: it is recommended to use a %03d numbering system (or more if more
        figures are used) to have leading zeros, otherwise gif may not be in
        order
    save_loc: string
        location to save gif
    save_name: string
        name to use for gif
    delay: int
        changs the delay between images in the gif
    """
    if not os.path.exists(save_loc):
        os.makedirs(save_loc)
    bashCommand = ("convert -delay %i -loop 0 -resize %ix%i %s/*.png %s/%s.gif") %(
                    delay, res[0], res[1], fig_loc, save_loc, save_name)
    # bashCommand = ("convert -delay %i -loop 0 -deconstruct -quantize"%delay
    #                + " transparent -layers optimize -resize %ix%i"%(res[0],res[1])
    #                + " %s/*.png %s/%s.gif"
    #                %(fig_loc, save_loc, save_name))
    print('Creating gif...')
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    print('Finished')
