import os
import re
import json
import subprocess
from time import strftime
from sensorAPI import *
from urllib import urlopen

# Register package name and version
registerVersion("glexec-errors", "1-0")

# Example:
# registerMetric (
#     metric_class_name,
#     description,
#     sensor_script_name<without the .py>.class_that_collects_and_stores_metric_data)
###############
registerMetric(
   "glexec_errors.glexec-errors", 
   "Find for glexec errors at condor shadow logs",
   "glexec_errors.check_glexec")

def domainNameToSiteName(domainToFind):
        # T2_BR_UERJ dont have public IPs on WN, it use this pattern to name
	# it's WN, node-X-X.hepgrid.local
        pattern = '.hepgrid.local'
        p = re.compile(pattern)
        m = p.match(domainToFind)
        if m:
           return u'T2_BR_UERJ'

        # T2_BR_SPRACE dont have public IPs on WN, it use this pattern to name
        # it's WN, nodeXXX.local
        pattern = '.local'
        p = re.compile(pattern)
        m = p.match(domainToFind)
        if m:
           return u'T2_BR_SPRACE'


        phedexDataUrl = 'http://cmsweb.cern.ch/phedex/datasvc/json/prod/nodes'
        phedexAPI=urlopen(phedexDataUrl)
        jsonRAW=phedexAPI.readlines()
        jsonStr=''.join(jsonRAW)
        jsonList=json.loads(jsonStr)
        nodes = jsonList['phedex']['node']
        sites = [ [site['name'],site['se']] for site in nodes ]
        sites = filter(lambda a: a[1] != None, sites)
        sites = [ [x[0],x[1].split('.') ] for x in sites ]
        sitesPerDomain = [ [x[0],".".join(x[1][1:len(x[1])])] for x in sites ]
        for oneSite in sitesPerDomain:
                if oneSite[1] == domainToFind:
                        return oneSite[0]
        return "Domain not found"


class check_glexec(Metric):
    '''
    This class will collect and store the metric data for glExec errors 
    parsing the condor ShadowLog file. 
    '''
    def sample(self):
        # Look through the condor ShadowLog file, and return all glExec errors
        try:
            condor_config_val = 'condor_config_val SHADOW_LOG'
            CONDOR_SHADOWLOG = str(subprocess.Popen(condor_config_val, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.read())
            CONDOR_SHADOWLOG = CONDOR_SHADOWLOG.strip()
            #CONDOR_SHADOWLOG = '/tmp/ShadowLog'
        except Exception, e:
            self.log("SENSOR_ERROR", "Failed to run condor_config_val: Reason: %s"%str(e))

        if len(CONDOR_SHADOWLOG) == 0:
            self.log("SENSOR_ERROR", "condor ShadowLog file not found")
            return -1

        timeStamp = strftime("%m/%d/%y ")
        startM = str(int(strftime("%M")[0])-1)
        startH = str(int(strftime("%H")))

        if int(startM) < 0:
            startM='5'
            startH=str(int(startH) - 1)
            if int(startH) < 0:
                startH = '11'

        if int(startH) < 10:
            startH = '0'+startH

        timeStamp = timeStamp + startH + ":" + startM
        self.log(SENSOR_LOG_INFO, "Time used: %s"%(timeStamp))

        glexec_reg = '%s.*ERROR "Error from glidein.*@(.*): error changing sandbox ownership to the user: condor_glexec_setup exited with'%(timeStamp)

        reg = re.compile(glexec_reg)

        failedHosts = []
        errorCount = []
        try:
            self.log(SENSOR_LOG_DEBUG,"Trying to open log file")
            with open(CONDOR_SHADOWLOG) as f:
                for line in f:
                    match = re.search(reg, line)
                    if match:
                        failedHosts.append( match.group(1) )
            self.log(SENSOR_LOG_DEBUG,"log file opened")
        except Exception, e:
            self.log(SENSOR_LOG_ERROR, str(e))
            return -1
        
        if len(failedHosts) > 0:
            failedHosts.sort()
            offset = 0
            while True:
                occur = failedHosts.count(failedHosts[offset])
                errorCount.append( [ occur, failedHosts[offset] ])
                offset += occur
                if offset == len(failedHosts):
                    break
            
            errorCount = sorted(errorCount,reverse=True)
            if len(errorCount) > 20:
                errorCount = errorCount[0:19]

            for host in errorCount:
                domainToFind = host[1].split('.')
                domainToFind = '.'.join(domainToFind[1:len(domainToFind)])
                domainName = domainNameToSiteName(domainToFind)
                self.storeSample01("%d %s %s"%(host[0],host[1],domainName))

        else:
            self.log(SENSOR_LOG_INFO,"No glexec errors found")

        return 0







