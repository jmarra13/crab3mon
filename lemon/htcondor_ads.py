import os
import re
import htcondor
import subprocess
from sensorAPI import *

# Register package name and version
registerVersion("htcondor_ads", "1-0")

# Example:
# registerMetric (
#     metric_class_name,
#     description,
#     sensor_script_name<without the .py>.class_that_collects_and_stores_metric_data)
###############
registerMetric(
   "htcondor_ads.classads", 
   "publish some htcondor classAds",
   "htcondor_ads.check_Ads")

class check_Ads(Metric):
    '''
    This class will collect and store the metric data for HTCondor classAds
    '''
    def getClassAds(self,ads, constraint ):
        onlyMatters = []
        try:
            schedd = htcondor.Schedd()
            result = schedd.query(constraint,[ads])
            for line in result:
                self.log(SENSOR_LOG_DEBUG,("%s : %s"%(ads,line[ads])))

            onlyMatters = [ [ads, int(x[ads])] for x in result]
        except  Exception, e:
            self.log(SENSOR_LOG_ERROR,str(e))

        return sorted(onlyMatters)

    def sample(self):
        # query all DAG_NodesReady which TaskType =?= 'ROOT'
        try:
           result = self.getClassAds('DAG_NodesReady', 'CRAB_ReqName isnt null && TaskType =?= "ROOT" && JobStatus=?=2 && DAG_NodesReady > 0')
           sumOfDAGS = 0
           for ads in result:
	       sumOfDAGS += int(ads[1])
           self.storeSample01('%s %d %d'%('DAG_NodesReady',sumOfDAGS,len(result)))
        except Exception, e:
           self.log(SENSOR_LOG_ERROR,str(e))

        # fetch all jobs which would take more than 2 days to run
        try:
           result = self.getClassAds('MaxWallTimeMins', 'MaxWallTimeMins > 2880')
           offSet = 0
           while True:
              occur = result.count([result[offSet][0],result[offSet][1]])
              self.storeSample01('%s %d %d'%('MaxWallTimeMins',result[offSet][1],occur))
              offSet += occur
              if offSet == len(result):
                 break
        except IndexError:
              # means that there is no class ad returned
              self.storeSample01('%s %d %d'%('MaxWallTimeMins',0,0))
              self.log(SENSOR_LOG_INFO,'No MaxWallTimeMins > 2880 returned')
              pass
        except Exception, e:
           self.log(SENSOR_LOG_ERROR,str(e))

        # fetch all jobs which request more than 2000Gb of memory 
        try:
           result = self.getClassAds('RequestMemory', 'RequestMemory > 2000')
           offSet = 0
           while True:
                 occur = result.count([result[offSet][0],result[offSet][1]])
                 self.storeSample01('%s %d %d'%('RequestMemory',result[offSet][1],occur))
                 offSet += occur
                 if offSet == len(result):
                    break
        except IndexError:
              # means that there is no class ad returned
              self.storeSample01('%s %d %d'%('RequestMemory',0,0))
              self.log(SENSOR_LOG_INFO,'No RequestMemory > 2000 returned')
              pass
        except Exception, e:
           self.log(SENSOR_LOG_ERROR,str(e))

        return 0

