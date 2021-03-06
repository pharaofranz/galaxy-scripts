#!/usr/bin/python
import subprocess
import os
import sys
import glob
import time
import datetime
import distutils.spawn

def getmeta(service='obs', params=None):
    """
    Function to call a JSON web service and return a dictionary:
    Given a JSON web service ('obs', find, or 'con') and a set of parameters as
    a Python dictionary, return a Python dictionary containing the result.
    Taken verbatim from http://mwa-lfd.haystack.mit.edu/twiki/bin/view/Main/MetaDataWeb
    """
    import urllib
    import urllib2
    import json

    # Append the service name to this base URL, eg 'con', 'obs', etc.
    BASEURL = 'http://ngas01.ivec.org/metadata/'


    if params:
        data = urllib.urlencode(params)  # Turn the dictionary into a string with encoded 'name=value' pairs
    else:
        data = ''

    if service.strip().lower() in ['obs', 'find', 'con']:
        service = service.strip().lower()
    else:
        print "invalid service name: %s" % service
        return

    try:
        result = json.load(urllib2.urlopen(BASEURL + service + '?' + data))
    except urllib2.HTTPError as error:
        print "HTTP error from server: code=%d, response:\n %s" % (error.code, error.read())
        return
    except urllib2.URLError as error:
        print "URL or network error: %s" % error.reason
        return

    return result

def is_number(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def sfreq(freqs):

    if len(freqs) != 24:
        print "There are not 24 coarse chans defined for this obs. Got: %s" % freqs
        return

    freqs.sort()   # It should already be sorted, but just in case...
    lowchans = [f for f in freqs if f <= 128]
    highchans = [f for f in freqs if f > 128]
    highchans.reverse()
    freqs = lowchans + highchans
    return freqs


def get_frequencies(metafits):
    hdulist = pyfits.open(metafits)
    freq_array = hdulist[0].header['CHANNELS']
    return sfreq(freq_array.split(','))


def options (options): # TODO reformat this to print properly

    print "\noptions:\n"
    print "--mode {0}".format(options.mode)
    print "-B [1/0]\t Submit download jobs to the copyq - at the moment this mode will only download and will perform <NO> subsequent processing [%d] \n" % (opts['batch_download'])
    print "-b:\t GPS/UNIX time of the beginning [%d]]\n" % (opts['begin'])
    print "-c:\t Coarse channel count (how many to process) [%d]\n" % (opts['ncoarse_chan'])
    print "-d:\t Number of parallel downloads to envoke if using '-g' [%d]\n" % (opts['parallel_dl'])
    print "-e:\t GPS/UNIX time of the end [%d]\n" % (opts['end'])
 #   print "-g:\t Get the data? (True/False) add this to get fresh data from the archive [%s]\n" % (opts['get_data'])
    print "-i:\t Increment in seconds (how much we process at once) [%d]\n" % (opts['inc'])
    print "-j:\t [corrdir] Use Jones matrices from the RTS [%s,%s]\n" % (opts['useJones'],opts['corrdir'])
    print "-m:\t Beam forming mode (0 == NO BEAMFORMING 1==PSRFITS, 2==VDIF) [%d]\n" % (opts['mode'])
    print "-n:\t Number of fine channels per coarse channel [%d]\n" % (opts['nchan'])
    print "-o:\t obsid [%s]\n" % opts['obsid']
    print "-p:\t beam pointing [%s]\n" % opts['pointing']
    print "-s:\t single step (only process one increment and this is it (-1 == do them all) [%d]\n" % opts['single_step']
#    print "-r:\t [corrdir] Run the offline correlator - this will submit a job to process the .dat files into visibility sets into the specified directory. These are needed if you want an RTS calibration solution [%s]\n" % opts['corrdir']
    print "-G:\t Submit the beamformer/correlator job [Do it = %s]\n" % opts['Go']
#   print "-R:\t New VCS mode - requires the recombine operation [runRECOMBINE = %s]\n" % opts['runRECOMBINE']
    print "-w:\t Working root directory [%s]\n" % opts['root']
#    print "-z:\t Add to switch off PFB formation/testing [runPFB = %s]\n" % opts['runPFB']


def vcs_download(obsid, start_time, stop_time, increment, copyq, format, working_dir, parallel):
    print "Downloading files from archive"
#    voltdownload = distutils.spawn.find_executable("voltdownload.py")
    voltdownload = "/group/mwaops/stremblay/MWA_CoreUtils/voltage/scripts/voltdownload.py"
    raw_dir = "{0}/raw".format(working_dir)
    make_dir = "mkdir {0}".format(raw_dir)
    subprocess.call(make_dir,shell=True)
    for time_to_get in range(start_time,stop_time,increment):
        get_data = "{0} --obs={1} --type={2} --from={3} --duration={4} --parallel={5} --dir={6}".format(voltdownload,obsid, format, time_to_get,(increment-1),parallel, raw_dir)
        if copyq:
            voltdownload_batch = "{0}/batch/volt_{1}.batch".format(working_dir,time_to_get)
            secs_to_run = datetime.timedelta(seconds=300*increment)
            with open(voltdownload_batch,'w') as batch_file:

                batch_line = "#!/bin/bash -l\n#SBATCH --export=NONE\n#SBATCH --output={0}/batch/volt_{1}.out\n".format(working_dir,time_to_get)
                batch_file.write(batch_line)
                batch_line = "%s\n" % (get_data)
                batch_file.write(batch_line)

            submit_line = "sbatch --time={0} --workdir={1} -M zeus --partition=copyq {2}\n".format(secs_to_run,raw_dir,voltdownload_batch)
            submit_cmd = subprocess.Popen(submit_line,shell=True,stdout=subprocess.PIPE)
            continue
        else:
            log_name="{0}/voltdownload_{1}.log".format(working_dir,time_to_get)
            with open(log_name, 'w') as log:
                subprocess.call(get_data, shell=True, stdout=log, stderr=log)


        try:
            os.chdir(working_dir)
        except:
            print "cannot open working dir:{0}".format(working_dir)
            sys.exit()


def vcs_recombine(obsid, start_time, stop_time, increment, working_dir):
    print "Running recombine on files"
    jobs_per_node = 8
#    recombine = distutils.spawn.find_executable("recombine.py")
    recombine = "/group/mwaops/stremblay/galaxy-scripts/scripts/recombine.py"
    for time_to_get in range(start_time,stop_time,increment):

        recombine_batch = "{0}/batch/recombine_{1}.batch".format(working_dir,time_to_get)
        with open(recombine_batch,'w') as batch_file:

            nodes = (increment+(-increment%jobs_per_node))//jobs_per_node + 1 # Integer division with ceiling result plus 1 for master node

            batch_line = "#!/bin/bash -l\n#SBATCH --time=06:00:00\n#SBATCH \n#SBATCH --output={0}/batch/recombine_{1}.out\n#SBATCH --export=NONE\n#SBATCH --nodes={2}\n".format(working_dir, time_to_get, nodes)

            batch_file.write(batch_line)
            batch_line = "module load mpi4py\n"
            batch_file.write(batch_line)
            batch_line = "module load cfitsio\n"
            batch_file.write(batch_line)

            if (stop_time - time_to_get) < increment:       # Trying to stop jobs from running over if they aren't perfectly divisible by increment
                increment = stop_time - time_to_get + 1

            if (jobs_per_node > increment):
                jobs_per_node = increment

            recombine_line = "aprun -n {0} -N {1} python {2} -o {3} -s {4} -w {5}\n".format(increment,jobs_per_node,recombine,obsid,time_to_get,working_dir)
            batch_file.write(recombine_line)

        submit_line = "sbatch --partition=gpuq --workdir={0} {1}\n".format(working_dir,recombine_batch)

        submit_cmd = subprocess.Popen(submit_line,shell=True,stdout=subprocess.PIPE)
        jobid=""
        for line in submit_cmd.stdout:

            if "Submitted" in line:
                (word1,word2,word3,jobid) = line.split()
#                if (is_number(jobid)):
#                    submitted_jobs.append(jobid)
#                    submitted_times.append(time_to_get)



def vcs_correlate(obsid,start,stop,increment,working_dir):
    print "Correlating files"
    import os
    import astropy
    from astropy.time import Time
    import datetime

    corrdir = "%s/corr" % working_dir

    try:
        os.mkdir(corrdir)
    except:
        if (os.path.exists(corrdir)):
            print "Correlator product directory Already exists\n"
        else:
            sys.exit()

    chan_list = get_frequencies(metafits_file)

    for time_to_get in range(start,stop,increment):
        inc_start = time_to_get
        inc_stop = time_to_get+increment

        for index,channel in enumerate(chan_list):
            gpubox_label = (index+1)
            f=[]
            for time_to_corr in range(inc_start,inc_stop,1):
                file_to_process = "{0}/combined/{1}_{2}_ch{3:0>2}.dat".format(working_dir,obsid,time_to_corr,channel)
                #check the file exists
                if (os.path.isfile(file_to_process) == True):
                    f.append(file_to_process)

            #now have a full list of files
            #for this increment 
            #and this channel
            if (len(f) > 0):
                corr_batch = "{0}/batch/correlator_{1}_gpubox{3:0>2}.batch".format(working_dir,inc_start,gpubox_label)

                with open(corr_batch, 'w') as batch_file:
                    batch_file.write("#!/bin/bash -l\n#SBATCH --nodes=1\n#SBATCH --export=NONE\n")
                    batch_file.write("module load cudatoolkit\nmodule load cfitsio\n")
                
                to_corr = 0
                for file in f:
                    corr_line = ""
                    (current_time,ext) = os.path.splitext(os.path.basename(file))
                    (obsid,gpstime,chan) = string.split(current_time,'_')
                    t = Time(int(gpstime), format='gps', scale='utc')
                    time_str =  t.datetime.strftime('%Y-%m-%d %H:%M:%S')

                    current_time = time.strptime(time_str, "%Y-%m-%d  %H:%M:%S")
                    unix_time = calendar.timegm(current_time)

                    corr_line = " aprun -n 1 -N 1 %s -o %s/%s -s %d -r 1 -i 100 -f 128 -n 4 -c %02d -d %s\n" % (mwac_offline,corrdir,unix_time,gpubox_label,file)
                    
                    with open(corr_batch, 'a') as batch_file:
                        batch_file.write(corr_line)
                        to_corr = to_corr+1

                secs_to_run = datetime.timedelta(seconds=5*to_corr)
                batch_submit_line = "sbatch --workdir=%s --time=%s --partition=gpuq %s\n" % (corrdir,str(secs_to_run),corr_batch)
                submit_cmd = subprocess.Popen(batch_submit_line,shell=True,stdout=subprocess.PIPE)
                jobid=""
                for line in submit_cmd.stdout:
                    if "Submitted" in line:
                        (word1,word2,word3,jobid) = line.split()



def make_pfb_files():
    print "Creating PFB files"


def coherent_beam():
    print "Forming coherent beam"



if __name__ == '__main__':

    modes=['download','recombine','correlate','make_pfb','beamform']
    jobs_per_node = 8
    chan_list_full=["ch01","ch02","ch03","ch04","ch05","ch06","ch07","ch08","ch09","ch10","ch11","ch12","ch13","ch14","ch15","ch16","ch17","ch18","ch19","ch20","ch21","ch22","ch23","ch24"]
    chan_list = []


    from optparse import OptionParser, OptionGroup

 #   parser=OptionParser(description="process_vcs.py is a script of scripts that downloads prepares and submits jobs to Galaxy. It can be run with just a pointing (-p \"xx:xx:xx xx:xx:xx.x\") and an obsid (\"-o <obsid>\") and it will process all the data in the obs. It will call prepare.py which will attempt to build the phase and calibration information - which will only exist if a calibration obs has already been run. So it will only move past the data prepa stage if the \"-r\" (for run) is used\n"

    parser=OptionParser(description="process_vcs.py is a script for processing the MWA VCS data on Galaxy in steps. It can download data from the archive, call on recombine to form course channels, run the offline correlator, make tile re-ordered and bit promoted PFB files or for a coherent beam for a given pointing.")
    group_download = OptionGroup(parser, 'Download Options')
    group_download.add_option("-B", "--copyq", action="store_true", default=False, help="Submit download jobs to the copyq [default=%default]")
    group_download.add_option("--format", type="choice", choices=['11','12'], default='11', help="Voltage data type (Raw = 11, Recombined Raw = 12) [default=%default]")
    group_download.add_option("-d", "--parallel_dl", type="int", default=3, help="Number of parallel downloads to envoke [default=%default]")

    group_recombine = OptionGroup(parser, 'Recombine Options')

    group_correlate = OptionGroup(parser, 'Correlator Options')
    group_correlate.add_option("--ft_res", metavar="FREQ RES,TIME RES", type="int", nargs=2, default=(40,1), help="Frequency (kHz) and Time (s) resolution to run correlator at. [default=%default]")

    group_pfb = OptionGroup(parser, 'PFB Creation Options')

    group_beamform = OptionGroup(parser, 'Beamforming Options')
    group_beamform.add_option("-p", "--pointing", nargs=2, help="R.A. and Dec. of pointing")
    group_beamform.add_option("--bf_mode", type="choice", choices=['0','1','2'], help="Beam forming mode (0 == NO BEAMFORMING 1==PSRFITS, 2==VDIF)")
    group_beamform.add_option("-j", "--useJones", action="store_true", default=False, help="Use Jones matrices from the RTS [default=%default]")

    parser.add_option("-m", "--mode", type="choice", choices=['download','recombine','correlate','make_pfb','beamform'], help="Mode you want to run. {0}".format(modes))
    parser.add_option("-o", "--obs", metavar="OBS ID", type="int", help="Observation ID you want to process [no default]")
    parser.add_option("-b", "--begin", type="int", help="First GPS time to process [no default]")
    parser.add_option("-e", "--end", type="int", help="Last GPS time to process [no default]")
    parser.add_option("-i", "--increment", type="int", default=200, help="Increment in seconds (how much we process at once) [default=%default]")
    parser.add_option("-s", action="store_true", default=False, help="Single step (only process one increment and this is it (False == do them all) [default=%default]")
    parser.add_option("-w", "--work_dir", metavar="DIR", default="/scratch/mwaops/vcs/", help="Base directory you want to run from. This will create a folder for the Obs. ID if it doesn't exist [default=%default]")
    parser.add_option("-c", "--ncoarse_chan", type="int", default=24, help="Coarse channel count (how many to process) [default=%default]")
    parser.add_option("-n", "--nfine_chan", type="int", default=128, help="Number of fine channels per coarse channel [default=%default]")
    parser.add_option("-G", "--Go", action="store_true", default=False, help="Include this option to run script [default=%default]")
    parser.add_option_group(group_download)
#    parser.add_option_group(group_recombine)
    parser.add_option_group(group_correlate)
#   parser.add_option_group(group_pfb)
    parser.add_option_group(group_beamform)

    (opts, args) = parser.parse_args()

    if not opts.mode:
      print "Mode required {0}. Please specify with -m or --mode.".format(modes)
      quit()

    if not opts.obs:
        print "Observation ID required, please put in with -o or --obs"
        quit()

    if opts.begin > opts.end:
        print "Starting time is after end time"
        quit()


    make_dir = "mkdir {0}".format(opts.work_dir)
    subprocess.call(make_dir,shell=True)
    working_dir = "{0}/{1}".format(opts.work_dir,opts.obs)
    make_dir = "mkdir {0}".format(working_dir)
    subprocess.call(make_dir,shell=True)
    batch_dir = "{0}/batch".format(working_dir)
    make_batch_dir="mkdir {0}".format(batch_dir)
    subprocess.call(make_batch_dir,shell=True)
    metafits_file = "{0}/{1}.metafits".format(working_dir,opts.obs)

 #   options(opts)

    if opts.mode == 'download':
        print opts.mode
        vcs_download(opts.obs, opts.begin, opts.end, opts.increment, opts.copyq, opts.format, working_dir, opts.parallel_dl)
    elif opts.mode == 'recombine':
        print opts.mode
        if (os.path.isfile(metafits_file) == False):
            metafile_line = "wget  http://ngas01.ivec.org/metadata/fits?obs_id=%d -O %s\n" % (opts.obs,metafits_file)
            subprocess.call(metafile_line,shell=True)

        make_combined = "mkdir {0}/combined".format(working_dir)
        subprocess.call(make_combined,shell=True)

        vcs_recombine(opts.obs, opts.begin, opts.end, opts.increment, working_dir)
    elif opts.mode == 'correlate':
        print opts.mode 
        if (os.path.isfile(metafits_file) == False):
            metafile_line = "wget  http://ngas01.ivec.org/metadata/fits?obs_id=%d -O %s\n" % (opts.obs,metafits_file)
            subprocess.call(metafile_line,shell=True)


        vcs_correlate()
    elif opts.mode == 'make_pfb':
        print opts.mode
        make_pfb_files()
    elif opts.mode == 'beamformer':
        print opts.mode
        coherent_beam()
    else:
        print "Somehow your non-standard mode snuck through. Try again with one of {0}".format(modes)
        quit()


