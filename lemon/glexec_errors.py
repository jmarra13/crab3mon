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

def sanitize(sites):
  # sites that share the same domain
  # name with other sites(v.g. in2p3 sites)
  siteRegx = [
               ["T2_FR_IPHC", "sbgwn.*.in2p3.fr"],
               ["T2_FR_GRIF_LLR","(polgrid|llrgrwn).*.in2p3.fr" ],
               ["T2_FR_GRIF_IRFU","wn.*.datagrid.cea.fr"],
               ["T3_FR_IPNL","lyowork.*.in2p3.fr"],
               ["T2_FR_CCIN2P3","ccwsge.*.in2p3.fr"],
               ["T2_CH_CERN",".*.cern.ch"],
               ["T1_UK_RAL","lcg.*.gridpp.rl.ac.uk"]
             ]


  # remove all sites without a SE defined
  sites = filter(lambda a: a[1] != '', sites)

  # remove all _DISK, _BUFFER, _MSS instances
  sites = filter(lambda a: "DISK" not in a[0].upper(), sites)
  sites = filter(lambda a: "BUFFER" not in a[0].upper(), sites)
  sites = filter(lambda a: "MSS" not in a[0].upper(), sites)

  idx = 0
  for site in sites:
    for reg in siteRegx:
      if reg[0] == site[0]:
        sites[idx] = reg
    idx += 1

  # sites defined at phedex api but removed because they only have _DISK, _BUFFER and _MSS 
  # instances
  sites.append(["T1_DE_KIT","c.*.gridka.de"])
  return sites

def condorStatus(glideInName):
    condorSt = "UNKNOWN_SITE"
    try:
        condorStatusCmd = "condor_status -const 'GLIDEIN_MASTER_NAME == \"%s\"' -af glidein_cmssite"%glideInName
        condorSt = str(subprocess.Popen(condorStatusCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.read())
        condorSt = condorSt.strip()
    except:
        pass

    if len(condorSt) == 0:
       condorSt = "UNKNOWN_SITE"

    return condorSt

def domainNameToSiteName(domainToFind,glideInName):
    phedexDataUrl = 'http://cmsweb.cern.ch/phedex/datasvc/json/prod/nodes'
    phedexAPI=urlopen(phedexDataUrl)
    jsonRAW=phedexAPI.readlines()
    jsonStr=''.join(jsonRAW)
    jsonList=json.loads(jsonStr)
    nodes = jsonList['phedex']['node']

    sites = [ [str(site['name']).encode('string-escape'),str(site['se']).encode('string-escape')] for site in nodes ]
    sites = [ [x[0],x[1].split('.') ] for x in sites ]
    sitesPerDomain = [ [x[0],".".join(x[1][1:len(x[1])])] for x in sites ]
    sitesPerDomain = sanitize(sitesPerDomain)

    for oneSite in sitesPerDomain:
       reg = re.compile(oneSite[1])
       match = re.search(reg, domainToFind)
       if match:
           return oneSite[0]

    # if site was not found in phedex api try to fetch from collector using the glideinName
    # condor_status -const 'GLIDEIN_MASTER_NAME == "glidein_3215_231573213@lnxfarm263.colorado.edu"' -af glidein_cmssite
    return condorStatus(glideInName)


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

        glexec_reg = '%s.*ERROR "Error from (.*): error changing sandbox ownership to the user: condor_glexec_setup exited with'%(timeStamp)

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
                domainName = domainNameToSiteName(domainToFind,host[1])
                self.storeSample01("%d %s %s"%(host[0],host[1],domainName))

        else:
            self.log(SENSOR_LOG_INFO,"No glexec errors found")

        return 0







