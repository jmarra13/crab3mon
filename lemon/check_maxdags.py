import os
import re
import json
import htcondor
import subprocess
from time import strftime
from sensorAPI import *
from urllib import urlopen

# Register package name and version
registerVersion("max_running_dags", "1-0")

# Example:
# registerMetric (
#     metric_class_name,
#     description,
#     sensor_script_name<without the .py>.class_that_collects_and_stores_metric_data)
###############
registerMetric(
   "check_max_dags.maxdags",
   "Publish the number of maximum running DAGs",
   "check_maxdags.check_maxdags")

class check_maxdags(Metric):
    '''
    This class will collect and store the metric data for the maximum number
    of running DAGs on CRAB3 schedd. 
    '''
    def sample(self):
        try:
            condor_config_val = 'condor_config_val START_SCHEDULER_UNIVERSE'
            CONDOR_MAXDAG = str(subprocess.Popen(condor_config_val, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.read())
            CONDOR_MAXDAG = CONDOR_MAXDAG.strip()
        except Exception, e:
            self.log(SENSOR_LOG_ERROR, "Failed to run condor_config_val: Reason: %s"%str(e))

        print(CONDOR_MAXDAG)
        maxDags = re.sub(r'.*TotalSchedulerJobsRunning < ([0-9]+).*',r'\1', CONDOR_MAXDAG)
        if maxDags:
            print(maxDags)
            self.storeSample01("%s"%maxDags)
        else:
            self.log(SENSOR_LOG_INFO,"Max running DAGs not found")

        return 0

