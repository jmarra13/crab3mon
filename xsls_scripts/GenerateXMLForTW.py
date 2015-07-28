import os
import sys
import time
import json
import urllib
import logging
import classad
import htcondor
import traceback
import subprocess
from datetime import datetime
from httplib import HTTPException
from RESTInteractions import HTTPRequests
from socket import gethostname
from pprint import pprint
from TaskWorker.__init__ import __version__ as __tw__version__

fmt = "%Y-%m-%dT%H:%M:%S%z"


class CRAB3CreateXML(object):

    def __init__(self, resthost, xmllocation, logger=None):
        if not logger:
            self.logger = logging.getLogger(__name__)
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(module)s %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger = logger

        self.xmllocation = xmllocation
        self.resthost = resthost
        self.pool = ''
        self.schedds = []
        self.resthost = "cmsweb.cern.ch"

    def getCountTasksByStatus(self):
        try:
            resturi = "/crabserver/prod/task"
            configreq = { 'minutes': "120", 'subresource': "counttasksbystatus" }
            server = HTTPRequests(self.resthost, "/data/certs/servicecert.pem", "/data/certs/servicekey.pem", retry = 2)
            result = server.get(resturi, data = configreq)
            return dict(result[0]['result'])
        except Exception, e:
            self.logger.debug("Error in getCountTasksByStatus: %s"%str(e))
            return []

    def getCountTaskByStatusAbs(self):
        try:
            resturi = "/crabserver/prod/task"
            configreq = { 'minutes': "1000000000", 'subresource': "counttasksbystatus" }
            server = HTTPRequests(self.resthost, "/data/certs/servicecert.pem", "/data/certs/servicekey.pem", retry = 2)
            result = server.get(resturi, data = configreq)
            return dict(result[0]['result'])
        except Exception, e:
            self.logger.debug("Error in getCountTasksByStatusAbs: %s"%str(e))
            return []

    def getShadowsRunning(self):
        #collName = "cmssrv221.fnal.gov"
        collName = "vocms099.cern.ch,cmssrv221.fnal.gov"
        data = []
        try:
            coll=htcondor.Collector(collName)                                               
            result = coll.query(htcondor.AdTypes.Schedd,'CMSGWMS_Type=?="crabschedd"',['Name','ShadowsRunning','TotalSchedulerJobsRunning','TotalIdleJobs','TotalRunningJobs','TotalHeldJobs'])
            for schedd in result:  # oneshadow[0].split('@')[1].split('.')[0]
                data.append([schedd['Name'],schedd['ShadowsRunning'],schedd['TotalSchedulerJobsRunning'],schedd['TotalIdleJobs'],schedd['TotalRunningJobs'],schedd['TotalHeldJobs']])
        except  Exception, e:
            self.logger.debug("Error in getShadowsRunning: %s"%str(e))
        return data

    def execute(self):
        from xml.etree.ElementTree import Element, SubElement, tostring
        root = Element('serviceupdate')
        root.set( "xmlns",  "http://sls.cern.ch/SLS/XML/update")
        child = SubElement(root, "id")
        child.text = gethostname().split('.')[0]

        subprocesses_config = 6 #  In this case 5 + 1 MasterWorker process
        sub_grep_command="ps -ef | grep MasterWorker | grep -v 'grep' | wc -l"
        # If any subproccess is dead or not working, modify percentage of availability
        # If subprocesses are not working - service availability 0%
        proccess_count = int(subprocess.Popen(sub_grep_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.read())

        # Get current time
        now_utc = datetime.now().strftime(fmt)
        child_timestamp = SubElement(root, "timestamp")
        child_timestamp.text = str(now_utc)
        child_availability = SubElement(root, "availability")
        if subprocesses_config == proccess_count:
            # This means that everything is fine
            child_availability.text = "100"
        else:
            child_availability.text = str((100/subprocesses_config)*proccess_count)


        # print "TaskWorker version: %s "%__tw__version__ # does not work yet

        # Get the number of tasks per status
        twStatus = self.getCountTasksByStatus()
        data = SubElement(root, "data")

        if len(twStatus) > 0:
            for name in ['SUBMITTED', 'FAILED', 'QUEUED', 'NEW', 'KILLED']:
                numericval = SubElement(data, "numericvalue")
                numericval.set("name","number_of_%s_tasks_in_the_last_minute"%(name))
                if twStatus.has_key(name):
                    numericval.text = str(twStatus[name])
                else:
                    numericval.text = '0'
        else:
            for name in ['SUBMITTED', 'FAILED', 'QUEUED', 'NEW', 'KILLED']:
                numericval = SubElement(data, "numericvalue")
                numericval.set("name","number_of_%s_tasks_in_the_last_minute"%(name))
                numericval.text = 'n/a'
 

        # get the absolut number of tasks per status
        twStatus = self.getCountTasksByStatus()

        if len(twStatus) > 0:
            for name in ['KILL', 'RESUBMIT', 'NEW']:
                numericval = SubElement(data, "numericvalue")
                numericval.set("name","numberOfTasksIn_%s_State"%(name))
                if twStatus.has_key(name):
                    numericval.text = str(twStatus[name])
                else:
                    numericval.text = '0'
        else:
            for name in ['KILL', 'RESUBMIT', 'NEW']:
                numericval = SubElement(data, "numericvalue")
                numericval.set("name","numberOfTasksIn_%s_State"%(name))
                numericval.text = 'n/a'

        # get the number of condor_shadown process per schedd
        numberOfShadows = self.getShadowsRunning()
        if len(numberOfShadows) > 0:
            #group= SubElement(data, "grp")
            #group.set("name", "Number of shadows per crab3 schedd")
            for oneShadow in numberOfShadows:
                numericval = SubElement(data,"numericvalue")
                numericval.set("name","number_of_shadows_process_for_%s"%(oneShadow[0]))
                numericval.text = str(oneShadow[1])

            #group= SubElement(data, "grp")
            #group.set("name", "Number of schedulers jobs running")
            for oneShadow in numberOfShadows:
                numericval = SubElement(data,"numericvalue")
                numericval.set("name","number_of_schedulers_jobs_running_for_%s"%(oneShadow[0]))
                numericval.text = str(oneShadow[2])

            #group= SubElement(data, "grp")
            #group.set("name", "Number of idle jobs per schedd")
            for oneShadow in numberOfShadows:
                numericval = SubElement(data,"numericvalue")
                numericval.set("name","number_of_idle_jobs_for_at_%s"%(oneShadow[0]))
                numericval.text = str(oneShadow[3])

            #group= SubElement(data, "grp")
            #group.set("name", "Number of running jobs per schedd")
            for oneShadow in numberOfShadows:
                numericval = SubElement(data,"numericvalue")
                numericval.set("name","number_of_running_jobs_running_for_at_%s"%(oneShadow[0]))
                numericval.text = str(oneShadow[4])
                 
            #group= SubElement(data, "grp")
            #group.set("name", "Number of held jobs per schedd")
            for oneShadow in numberOfShadows:
                numericval = SubElement(data,"numericvalue")
                numericval.set("name","number_of_held_jobs_for_at_%s"%(oneShadow[0]))
                numericval.text = str(oneShadow[5])

        # Write all this information to a temp file and move to correct location
        temp_xmllocation = self.xmllocation + ".temp"
        try:
            with open(temp_xmllocation, 'w') as f:
                f.write(tostring(root))
            os.system('mv %s %s' % (temp_xmllocation, self.xmllocation))
        except Exception, e:
            self.logger.debug(str(e))

if __name__ == '__main__':
    """ Simple main to execute the action standalon. You just need to set the task worker environment.
        The main is set up to work with the production task worker. If you want to use it on your own
        instance you need to change resthost, resturi, and twconfig.
        If you want to monitor your own machine, you have to enable it in puppet configuration.
    """
    resthost = 'cmsweb.cern.ch'
    #xmllocation = 'teste.xml'
    xmllocation = '/home/crab3/CRAB3_SCHEDD_XML_Report2.xml'
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(module)s %(message)s", datefmt="%a, %d %b %Y %H:%M:%S %Z(%z)")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    from WMCore.Configuration import loadConfigurationFile

    pr = CRAB3CreateXML( resthost, xmllocation, logger)
    pr.execute()

    # push the XML to elasticSearch 
    cmd = "curl -i -F file=@/home/crab3/CRAB3_SCHEDD_XML_Report2.xml xsls.cern.ch"
    try:
        pu = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #logger.debug("Runned pretty well")
    except Exception, e:
        logger.debug(str(e))

